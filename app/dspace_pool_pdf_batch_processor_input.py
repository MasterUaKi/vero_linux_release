# ==============================================================================
# Script Name: dspace_pool_pdf_batch_processor_input.py
# Version:     4.5.0
# Date:        2026-08-13
# Author:      Oleh Riabtsev / AI Assistant
# Description: Continuous Daemon Mode with i18n and UUID extraction from authority.
#              FIXED: Added 'kostenstelle_vergeben' as a valid final approval status
#              for Funding workflows, alongside 'praesidium_ja'.
# ==============================================================================

import json
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import time

from config_loader import (
    DSPACE_BASE_URL,
    BOT_EMAIL,
    BOT_PASSWORD,
    D3_URL,
    D3_API_KEY,
    D3_REPO_ID,
    D3_FOLDER_APPLICATION,
    D3_FOLDER_FUNDING,
    T_DRIVE_DIR,
    POLL_INTERVAL_SECONDS,
    LOG_DIR,
    LOG_FILENAME,
    LOG_BACKUP_COUNT,
)

from i18n import t
from dspace_scan_pool_details import DSpacePoolScanner
from dspace_to_d3_mapper import DSpaceToD3Mapper
from generate_pdf_report import VeROPDFGenerator
from d3_api_client import D3DMSClient
from d3_dspace_status_checker import search_antrag_files_in_d3


def setup_logging():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    log_filepath = os.path.join(LOG_DIR, LOG_FILENAME)
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

    file_handler = TimedRotatingFileHandler(
        log_filepath,
        when="midnight",
        interval=1,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_linked_application_uuid(wf_details: dict) -> str:
    metadata_raw = wf_details.get("metadata_raw", {})
    fields_to_check = ["veroFU.application", "dc.relation.project", "oairecerif.fundingParent"]

    for field in fields_to_check:
        entries = metadata_raw.get(field, [])
        for entry in entries:
            if isinstance(entry, dict):
                authority = entry.get("authority")
                if authority and len(str(authority)) >= 36:
                    return str(authority)

                val = entry.get("value")
                if val and len(str(val)) >= 36 and "-" in str(val):
                    return str(val)

    metadata = wf_details.get("metadata", {})
    app_uuid_list = metadata.get("veroFU.application") or metadata.get("dc.relation.project") or metadata.get(
        "oairecerif.fundingParent") or []
    if app_uuid_list:
        val = app_uuid_list[0]
        if val and len(str(val)) >= 36 and "-" in str(val):
            return str(val)

    return ""


def is_final_approved(status_string: str) -> bool:
    """Check if the status is a final approval (either Praesidium or Kostenstelle)."""
    status_clean = str(status_string).strip().lower()
    return "praesidium_ja" in status_clean or "kostenstelle_vergeben" in status_clean


def process_live_workflow():
    if not os.path.exists(T_DRIVE_DIR):
        os.makedirs(T_DRIVE_DIR)

    scanner = DSpacePoolScanner(DSPACE_BASE_URL)
    if not scanner.login(BOT_EMAIL, BOT_PASSWORD):
        logging.error(t("AUTH_DSPACE_ERROR"))
        return

    d3_client = D3DMSClient(D3_URL, D3_API_KEY, D3_REPO_ID)
    d3_authenticated = d3_client.login()

    # =========================================================================
    # ФАЗА 1: ОБРАБОТКА НОВЫХ ЗАДАЧ ИЗ ПУЛА (POOLTASKS) -> В d.3 -> CLAIM
    # =========================================================================
    logging.info("\n==============================================================")
    logging.info(t("PHASE_1_TITLE"))
    logging.info("==============================================================")

    pool_summary = scanner.scan_full_pool()
    pool_tasks = pool_summary.get("pool_tasks", []) if pool_summary else []

    if pool_tasks:
        logging.info(t("FOUND_POOL_TASKS", count=len(pool_tasks)))
        for idx, task in enumerate(pool_tasks, start=1):
            pooltask_id = str(task.get("pooltask_id"))
            wf_details = task.get("workflow_item_details")
            if not wf_details:
                continue

            item_info = wf_details.get("item_info", {})
            vero_id = item_info.get("uuid") or str(wf_details.get("workflow_item_id"))

            metadata = wf_details.get("metadata", {})
            title_list = metadata.get("dc.title", ["Unbenannter_Eintrag"])
            project_title = title_list[0] if title_list else "Unbenannter_Eintrag"

            is_funding = "veroFU.application" in metadata or "oairecerif.funding.identifier" in metadata

            entity_type = "Funding" if is_funding else "Application"
            folder_code = D3_FOLDER_FUNDING if is_funding else D3_FOLDER_APPLICATION
            folder_name = "Bewilligung, Änderung, Bescheid" if is_funding else "Antragsunterlagen / Meldebogen"

            logging.info(
                "\n" + t("POOL_TASK_INFO", idx=idx, total=len(pool_tasks), task_id=pooltask_id, entity_type=entity_type,
                         vero_id=vero_id))
            logging.info(t("TASK_TITLE", title=project_title))
            logging.info(t("TARGET_FOLDER", folder_name=folder_name, folder_code=folder_code))

            location_url = None
            if is_funding:
                linked_app_uuid = get_linked_application_uuid(wf_details)
                logging.info(t("SEARCH_PARENT_AKTE", app_uuid=linked_app_uuid))

                if not linked_app_uuid:
                    logging.warning(t("MISSING_LINKED_APP"))
                    continue

                location_url = d3_client.find_akte_by_vero_id(linked_app_uuid)
                if not location_url:
                    logging.info(t("WAITING_PARENT_AKTE", app_uuid=linked_app_uuid))
                    continue

                app_akte_id = location_url.split("/")[-1].split("?")[0]
                app_aktenzeichen = d3_client.get_aktenzeichen(location_url)
                app_status_in_d3 = "UNBEKANNT"

                if app_aktenzeichen != "UNBEKANNT":
                    app_files = search_antrag_files_in_d3(d3_client, app_aktenzeichen, app_akte_id)
                    if app_files:
                        # УМНЫЙ ПОИСК СТАТУСА (Фаза 1) - добавили kostenstelle_vergeben
                        statuses = [f.get("vero_status_515", "UNBEKANNT") for f in app_files]
                        active = [s for s in statuses if s and s != "UNBEKANNT"]
                        if active:
                            decision = next((s for s in active if
                                             "praesidium_ja" in s.lower() or "praesidium_nein" in s.lower() or "kostenstelle_vergeben" in s.lower()),
                                            None)
                            app_status_in_d3 = decision if decision else active[0]

                logging.info(t("PARENT_STATUS", status=app_status_in_d3))

                if not is_final_approved(app_status_in_d3):
                    logging.info(t("WAITING_PRAESIDIUM", app_uuid=linked_app_uuid, status=app_status_in_d3))
                    continue

                logging.info(t("APPROVED_PRAESIDIUM"))
            else:
                location_url = d3_client.find_akte_by_vero_id(vero_id)
                if not location_url:
                    logging.info(t("CREATE_NEW_AKTE"))
                    d3_akte_payload = DSpaceToD3Mapper.map_dspace_item_to_d3_akte_payload(
                        dspace_item_details=wf_details,
                        repo_id=D3_REPO_ID
                    )
                    location_url = d3_client.create_akte(d3_akte_payload)

            pdf_filename = f"Meldebogen_{entity_type}_{vero_id}.pdf"
            pdf_filepath = os.path.join(T_DRIVE_DIR, pdf_filename)
            pdf_groups_structure = DSpaceToD3Mapper.get_pdf_report_data(wf_details)
            pdf_created = VeROPDFGenerator.generate_pdf(
                pdf_groups_data=pdf_groups_structure,
                output_filepath=pdf_filepath,
                vero_id=vero_id,
                title=project_title
            )

            # ФЛАГ УСПЕШНОЙ ЗАГРУЗКИ
            upload_success = False

            if pdf_created and d3_authenticated and location_url:
                akte_id = location_url.split("/")[-1].split("?")[0]
                aktenzeichen = d3_client.get_aktenzeichen(location_url)
                if aktenzeichen != "UNBEKANNT":
                    vorgangszeichen = f"{aktenzeichen}/{folder_code}"
                    if d3_client.check_document_exists(vorgangszeichen, akte_id=akte_id):
                        logging.info(t("DOC_EXISTS", folder_name=folder_name, vorgangszeichen=vorgangszeichen))
                        upload_success = True
                    else:
                        logging.info(t("UPLOADING_PDF", entity_type=entity_type, aktenzeichen=aktenzeichen,
                                       folder_name=folder_name, folder_code=folder_code))
                        doc_location = d3_client.upload_pdf_document(
                            pdf_filepath=pdf_filepath,
                            aktenzeichen=aktenzeichen,
                            project_title=project_title,
                            folder_code=folder_code
                        )
                        if doc_location:
                            upload_success = True

            # ПРИНЯТИЕ ЗАДАЧИ БОТОМ
            if upload_success:
                scanner.claim_pool_task(pooltask_id)
            else:
                logging.warning(
                    f"⚠️ Ошибка при обработке {entity_type} (Vero_ID={vero_id}). Загрузка не удалась, задача оставлена в пуле.")
    else:
        logging.info(t("NO_POOL_TASKS"))

    # =========================================================================
    # ФАЗА 2: МОНИТОРИНГ ПРИНЯТЫХ БОТОМ ЗАДАЧ (CLAIMEDTASKS) И СТАТУСА В d.3
    # =========================================================================
    logging.info("\n==============================================================")
    logging.info(t("PHASE_2_TITLE"))
    logging.info("==============================================================")

    claimed_tasks = scanner.scan_claimed_tasks()

    if claimed_tasks:
        logging.info(t("FOUND_CLAIMED_TASKS", count=len(claimed_tasks)))
        for idx, task in enumerate(claimed_tasks, start=1):
            claimedtask_id = str(task.get("claimedtask_id"))
            wf_details = task.get("workflow_item_details")
            if not wf_details:
                continue

            item_info = wf_details.get("item_info", {})
            vero_id = item_info.get("uuid") or str(wf_details.get("workflow_item_id"))

            metadata = wf_details.get("metadata", {})
            project_title = metadata.get("dc.title", ["Unbenannter_Eintrag"])[0]
            is_funding = "veroFU.application" in metadata or "oairecerif.funding.identifier" in metadata
            entity_type = "Funding" if is_funding else "Application"

            logging.info("\n" + t("CLAIMED_TASK_INFO", idx=idx, total=len(claimed_tasks), task_id=claimedtask_id,
                                  entity_type=entity_type, vero_id=vero_id))
            logging.info(t("TASK_TITLE", title=project_title))

            target_uuid_for_akte = vero_id
            if is_funding:
                linked_app_uuid = get_linked_application_uuid(wf_details)
                if linked_app_uuid:
                    target_uuid_for_akte = linked_app_uuid

            location_url = d3_client.find_akte_by_vero_id(target_uuid_for_akte)
            doc_status_in_d3 = "UNBEKANNT"

            if location_url:
                akte_id = location_url.split("/")[-1].split("?")[0]
                aktenzeichen = d3_client.get_aktenzeichen(location_url)
                if aktenzeichen != "UNBEKANNT":
                    files = search_antrag_files_in_d3(d3_client, aktenzeichen, akte_id)

                    target_folder_code = D3_FOLDER_FUNDING if is_funding else D3_FOLDER_APPLICATION
                    matching_files = [
                        f for f in files
                        if f.get("vorgangszeichen", "").endswith(f"/{target_folder_code}")
                    ]

                    # 🔥 УМНЫЙ ПОИСК СТАТУСА - добавили kostenstelle_vergeben
                    if matching_files:
                        all_statuses = [f.get("vero_status_515", "UNBEKANNT") for f in matching_files]
                        active_statuses = [s for s in all_statuses if s and s != "UNBEKANNT"]

                        if active_statuses:
                            # 1 приоритет: Ищем, есть ли финальное решение
                            decision = next((s for s in active_statuses if
                                             "praesidium_ja" in s.lower() or "praesidium_nein" in s.lower() or "kostenstelle_vergeben" in s.lower()),
                                            None)
                            if decision:
                                doc_status_in_d3 = decision
                            else:
                                # 2 приоритет: Берем любой активный промежуточный статус
                                doc_status_in_d3 = active_statuses[0]

            status_clean = doc_status_in_d3.strip().lower()
            logging.info(t("DOC_STATUS_IN_D3", entity_type=entity_type,
                           folder_code=(D3_FOLDER_FUNDING if is_funding else D3_FOLDER_APPLICATION),
                           status=doc_status_in_d3))

            # Обработка успешных финальных статусов
            if "praesidium_ja" in status_clean or "kostenstelle_vergeben" in status_clean:
                if "kommentar" in status_clean or "auflagen" in status_clean:
                    logging.info(t("APPROVED_WITH_COMMENT", entity_type=entity_type))
                else:
                    logging.info(t("APPROVED_SIMPLE", entity_type=entity_type))

                scanner.approve_claimed_task(claimedtask_id)

            # Обработка отклонения
            elif "praesidium_nein" in status_clean:
                logging.info(t("REJECTED", entity_type=entity_type))
                scanner.reject_claimed_task(claimedtask_id, reason=t("REJECT_REASON"))

            else:
                logging.info(t("IN_PROGRESS", entity_type=entity_type, status=doc_status_in_d3))
    else:
        logging.info(t("NO_CLAIMED_TASKS"))

    logging.info("\n==============================================================")
    logging.info(t("CYCLE_COMPLETE"))
    logging.info("==============================================================\n")


def main():
    setup_logging()
    logging.info("==============================================================")
    logging.info(t("START_SERVICE", seconds=POLL_INTERVAL_SECONDS))
    logging.info(t("LOGGING_CONFIGURED", path=f"{LOG_DIR}/{LOG_FILENAME}"))
    logging.info("==============================================================")

    cycle_count = 1
    try:
        while True:
            logging.info("\n" + t("CYCLE_START", count=cycle_count))
            try:
                process_live_workflow()
            except Exception as e:
                logging.error(t("CYCLE_EXCEPTION", count=cycle_count, e=e), exc_info=True)

            logging.info(t("SLEEPING", seconds=POLL_INTERVAL_SECONDS, next_count=cycle_count + 1))
            time.sleep(POLL_INTERVAL_SECONDS)
            cycle_count += 1

    except KeyboardInterrupt:
        logging.info("\n" + t("SERVICE_STOPPED"))


if __name__ == "__main__":
    main()
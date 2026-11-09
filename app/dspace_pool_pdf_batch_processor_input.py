# ==============================================================================
# Script Name: dspace_pool_pdf_batch_processor_input.py
# Version:     4.22.0
# Date:        2026-11-02
# Author:      Oleh Riabtsev / AI Assistant
# Description: Continuous Daemon Mode with dual-level status resolution:
#              - Preserves all legacy logic, workflows, mappings, and fallbacks.
#              - Integrated item_uuid forwarding into search_antrag_files_in_d3
#                across Phase 1 and Phase 2, ensuring Meldebogen PDF (T000054276)
#                is reliably retrieved and matched by UUID.
#              - Prioritizes specific document status in folder /009 (Praesidium_Ja)
#                for Application with graceful Akte-level fallback.
#              - Funding status (Kostenstelle_vergeben, Fonds, Finanzstelle) is
#                resolved from the specific document inside folder /002.
#              - Parallel extraction and recording of both 'Fonds' and 'Finanzstelle'
#                into repeatable DSpace-CRIS CERIF field 'oairecerif.internalid'.
#              - Automatic JSON-Patch append (/metadata/<field>/-) ensuring
#                persistence of place 0 and place 1 in PostgreSQL.
# ==============================================================================

import json
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import re
import time
import requests

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
from d3_dspace_status_checker import (
    search_antrag_files_in_d3,
    is_valid_kostenstelle,
    is_explicit_rejection_value,
    get_details_from_d3_object
)

# Официальное повторяющееся поле CERIF / DSpace-CRIS для Fonds и Finanzstelle SAP
TARGET_DSPACE_INTERNALID_FIELD = "oairecerif.internalid"


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


def build_dspace_url(base_url: str, endpoint: str) -> str:
    """Формирует корректный URL эндпоинта DSpace REST API без дублирования /server/api."""
    b = str(base_url).rstrip("/")
    ep = str(endpoint).strip("/")

    if "/server/api" in b:
        root = b[:b.find("/server/api") + len("/server/api")]
        if ep.startswith("server/api/"):
            ep = ep[len("server/api/"):]
        elif ep == "server/api":
            ep = ""
        return f"{root}/{ep}" if ep else root
    elif "/server" in b:
        root = b[:b.find("/server") + len("/server")]
        if ep.startswith("server/"):
            ep = ep[len("server/"):]
        if not ep.startswith("api/"):
            ep = f"api/{ep}"
        return f"{root}/{ep}"
    else:
        if not ep.startswith("server/api/"):
            ep = f"server/api/{ep}"
        return f"{b}/{ep}"


def get_akte_status_in_d3(d3_client: D3DMSClient, location_url: str) -> str:
    """
    Извлекает статус согласования (поле 515) непосредственно с уровня Акты (Drittmittelakte).
    Используется как запасной вариант для сущности Application, если статус на документе не найден.
    """
    if not location_url:
        return "UNBEKANNT"

    akte_id = location_url.split("/")[-1].split("?")[0]

    # Шаг 1: Попытка через штатный модуль парсинга свойств объекта d.3
    try:
        details = get_details_from_d3_object(d3_client, akte_id)
        if details and isinstance(details, dict):
            st = details.get("status_515", "")
            if st and st != "UNBEKANNT":
                return st
            raw_dump = details.get("raw_text_dump", "").lower()
            if "praesidium_ja" in raw_dump:
                return "Praesidium_Ja"
            elif "praesidium_nein" in raw_dump:
                return "Praesidium_Nein"
            elif "pdf_zu_allris_hochgeladen" in raw_dump:
                return "PDF_zu_ALLRIS_hochgeladen"
    except Exception as e:
        logging.debug(f"get_details_from_d3_object для Акты {akte_id} вернул ошибку: {e}")

    # Шаг 2: Прямой HTTP-запрос с нормализацией URL (добавление схемы D3_URL)
    base = str(D3_URL).rstrip("/")
    loc_str = str(location_url).strip()
    full_url = loc_str if loc_str.startswith(("http://", "https://")) else f"{base}/{loc_str.lstrip('/')}"

    headers = {}
    if hasattr(d3_client, "headers") and isinstance(d3_client.headers, dict):
        headers.update(d3_client.headers)
    elif hasattr(d3_client, "_headers") and isinstance(d3_client._headers, dict):
        headers.update(d3_client._headers)

    api_key = getattr(d3_client, "api_key", None) or D3_API_KEY
    if api_key:
        if "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"
        if "X-Api-Key" not in headers:
            headers["X-Api-Key"] = str(api_key)
    if "Accept" not in headers:
        headers["Accept"] = "application/json"

    try:
        sess = (
            getattr(d3_client, "_session", None)
            or getattr(d3_client, "session", None)
            or getattr(d3_client, "s", None)
            or getattr(d3_client, "http", None)
        )

        if sess and hasattr(sess, "get"):
            resp = sess.get(full_url, headers=headers, timeout=10)
        else:
            resp = requests.get(full_url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            properties = data.get("properties", []) or data.get("objectProperties", [])
            for p in properties:
                k = str(p.get("key", "") or p.get("id", "")).strip().lower()
                if k == "515" or k.endswith(".515") or "status" in k:
                    vals = p.get("values", []) or [p.get("value")]
                    if vals and vals[0]:
                        val_str = str(vals[0]).strip()
                        if val_str:
                            return val_str

            raw_dump = json.dumps(data, ensure_ascii=False).lower()
            if "praesidium_ja" in raw_dump:
                return "Praesidium_Ja"
            elif "praesidium_nein" in raw_dump:
                return "Praesidium_Nein"
            elif "pdf_zu_allris_hochgeladen" in raw_dump:
                return "PDF_zu_ALLRIS_hochgeladen"

    except Exception as e:
        logging.warning(f"⚠️ Ошибка при запросе статуса Акты ({full_url}): {e}")

    return "UNBEKANNT"


def update_dspace_internal_ids(scanner: DSpacePoolScanner, item_uuid: str, id_values: list) -> bool:
    """
    Записывает параллельные значения (Fonds и Finanzstelle) в повторяющееся поле
    oairecerif.internalid через RFC 6902 JSON-Patch (remove + append /-).
    """
    if not id_values:
        return False

    url = build_dspace_url(scanner.base_url, f"core/items/{item_uuid}")
    headers = {
        "Content-Type": "application/json-patch+json"
    }

    xsrf_token = scanner.session.cookies.get("DSPACE-XSRF-COOKIE")
    if xsrf_token:
        headers["X-XSRF-TOKEN"] = xsrf_token

    # 1. Очистка старых записей
    try:
        patch_remove = [
            {
                "op": "remove",
                "path": f"/metadata/{TARGET_DSPACE_INTERNALID_FIELD}"
            }
        ]
        scanner.session.patch(url, json=patch_remove, headers=headers, timeout=10)
    except Exception:
        pass

    # 2. Добавление каждого значения отдельной операцией через путь /- (append)
    patch_add_ops = [
        {
            "op": "add",
            "path": f"/metadata/{TARGET_DSPACE_INTERNALID_FIELD}/-",
            "value": {
                "value": str(val).strip(),
                "language": None,
                "authority": None,
                "confidence": -1
            }
        }
        for val in id_values
        if str(val).strip()
    ]

    try:
        resp = scanner.session.patch(url, json=patch_add_ops, headers=headers, timeout=10)
        if resp.status_code in [200, 204]:
            logging.info(f"✅ Успешно записаны значения {id_values} в {TARGET_DSPACE_INTERNALID_FIELD} (UUID: {item_uuid})")
            return True
        else:
            logging.error(f"[-] Ошибка PATCH add DSpace ({resp.status_code}): {resp.text}")
    except Exception as e:
        logging.error(f"[-] Исключение при обновлении internalid: {e}")

    return False


def get_linked_application_uuid(wf_details: dict) -> str:
    """Извлекает UUID родительской заявки (Application)."""
    extracted = DSpaceToD3Mapper.extract_parent_application_uuid(wf_details)
    if extracted and len(extracted) >= 36:
        return extracted

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
    app_uuid_list = (
        metadata.get("veroFU.application")
        or metadata.get("dc.relation.project")
        or metadata.get("oairecerif.fundingParent")
        or []
    )
    if app_uuid_list:
        val = app_uuid_list[0]
        if isinstance(val, dict):
            if val.get("authority") and len(str(val.get("authority"))) >= 36:
                return str(val.get("authority")).strip()
            if val.get("value") and len(str(val.get("value"))) >= 36:
                return str(val.get("value")).strip()
        elif val and len(str(val)) >= 36 and "-" in str(val):
            return str(val)

    return ""


def is_rejection_status(status_string: str) -> bool:
    """Проверяет, содержит ли статус маркеры отклонения (включая VPPF_abgelehnt)."""
    s = str(status_string).strip().lower()
    rejection_keywords = [
        "vppf_abgelehnt",
        "praesidium_nein",
        "abgelehnt",
        "verworfen",
        "abbruch",
        "kostenstelle_abgelehnt",
        "nein",
        "rejected"
    ]
    return any(k in s for k in rejection_keywords)


def is_approval_status(status_string: str) -> bool:
    """Проверяет, содержит ли статус маркеры положительного решения."""
    s = str(status_string).strip().lower()
    if is_rejection_status(s):
        return False
    return "praesidium_ja" in s or "kostenstelle_vergeben" in s


def _extract_doc_number(doc: dict) -> int:
    """Извлекает числовую часть ID документа d.3 для сортировки по хронологии."""
    doc_id = str(doc.get("doc_id", ""))
    digits = re.sub(r"\D", "", doc_id)
    return int(digits) if digits else 0


def find_specific_task_document(docs: list, target_folder_code: str, item_uuid: str, task_title: str = "") -> dict:
    if not docs:
        return {}

    folder_docs = [d for d in docs if d.get("vorgangszeichen", "").endswith(f"/{target_folder_code}")]
    if not folder_docs:
        return {}

    uuid_clean = item_uuid.strip().lower() if item_uuid else ""
    title_clean = task_title.strip().lower() if task_title else ""

    logging.info(f"🔍 Сканирование папки {target_folder_code} (Найдено документов: {len(folder_docs)}) для UUID=[{item_uuid}]:")

    for doc in folder_docs:
        doc_id = doc.get("doc_id", "")
        doc_title = str(doc.get("title", "")).strip()
        doc_filename = str(doc.get("filename", "")).strip()
        doc_vero_id = str(doc.get("vero_id", "")).strip()
        raw_dump = doc.get("raw_text_dump", "")

        logging.info(
            f"   • Doc ID={doc_id} | Titel='{doc_title}' | Fonds='{doc.get('fonds')}' | "
            f"Finanzstelle='{doc.get('finanzstelle')}' | Status={doc.get('vero_status_515')}"
        )

        if uuid_clean and (
            uuid_clean in doc_vero_id.lower() or
            uuid_clean in doc_filename.lower() or
            uuid_clean in doc_title.lower() or
            uuid_clean in raw_dump
        ):
            logging.info(f"🎯 [MATCH BY UUID] Документ ID={doc_id} однозначно идентифицирован по UUID {item_uuid}")
            return doc

    if title_clean:
        for doc in folder_docs:
            doc_id = doc.get("doc_id", "")
            doc_title = str(doc.get("title", "")).strip().lower()
            if title_clean in doc_title or doc_title in title_clean:
                logging.info(f"🎯 [MATCH BY TITLE] Документ ID={doc_id} сопоставлен по названию '{task_title}'")
                return doc

    if len(folder_docs) == 1:
        single_doc = folder_docs[0]
        logging.info(f"🎯 [SINGLE DOC] В папке {target_folder_code} найден единственный документ ID={single_doc.get('doc_id')}")
        return single_doc

    folder_docs_sorted = sorted(folder_docs, key=_extract_doc_number, reverse=True)

    newest_doc = folder_docs_sorted[0]
    newest_status = newest_doc.get("vero_status_515", "")
    if newest_status and newest_status != "UNBEKANNT":
        logging.info(
            f"🎯 [MATCH BY LATEST] В папке {target_folder_code} выбран новейший документ ID={newest_doc.get('doc_id')} (Status={newest_status})"
        )
        return newest_doc

    for doc in folder_docs_sorted:
        st = doc.get("vero_status_515", "")
        if is_approval_status(st):
            logging.info(
                f"🎯 [MATCH BY APPROVAL] В папке {target_folder_code} найден одобренный документ ID={doc.get('doc_id')} (Status={st})"
            )
            return doc

    for doc in folder_docs_sorted:
        st = doc.get("vero_status_515", "")
        if st and st != "UNBEKANNT":
            logging.info(
                f"🎯 [MATCH BY KNOWN STATUS] В папке {target_folder_code} выбран документ ID={doc.get('doc_id')} со статусом '{st}'"
            )
            return doc

    logging.info(
        f"🎯 [MATCH BY FALLBACK] В папке {target_folder_code} выбран новейший документ ID={newest_doc.get('doc_id')}"
    )
    return newest_doc


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

                # Шаг 1: Проверяем документ заявки в папке /009 с поиском по UUID
                if app_aktenzeichen != "UNBEKANNT":
                    app_files = search_antrag_files_in_d3(
                        d3_client,
                        app_aktenzeichen,
                        app_akte_id,
                        item_uuid=linked_app_uuid
                    )
                    parent_app_doc = find_specific_task_document(
                        docs=app_files,
                        target_folder_code=D3_FOLDER_APPLICATION,
                        item_uuid=linked_app_uuid
                    )
                    if parent_app_doc:
                        app_status_in_d3 = parent_app_doc.get("vero_status_515", "UNBEKANNT")

                # Шаг 2: Фоллбэк на статус родительской Акты, если в документе UNBEKANNT
                if app_status_in_d3 == "UNBEKANNT":
                    app_status_in_d3 = get_akte_status_in_d3(d3_client, location_url)

                logging.info(t("PARENT_STATUS", status=app_status_in_d3))

                if not is_approval_status(app_status_in_d3):
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
                title=project_title,
                is_funding=is_funding
            )

            upload_success = False

            if pdf_created and d3_authenticated and location_url:
                akte_id = location_url.split("/")[-1].split("?")[0]
                aktenzeichen = d3_client.get_aktenzeichen(location_url)
                if aktenzeichen != "UNBEKANNT":
                    logging.info(t("UPLOADING_PDF", entity_type=entity_type, aktenzeichen=aktenzeichen,
                                   folder_name=folder_name, folder_code=folder_code))
                    doc_location = d3_client.upload_pdf_document(
                        pdf_filepath=pdf_filepath,
                        aktenzeichen=aktenzeichen,
                        project_title=f"{project_title} [{vero_id}]",
                        folder_code=folder_code
                    )
                    if doc_location:
                        upload_success = True

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
            fonds_val = ""
            finanzstelle_val = ""

            if location_url:
                akte_id = location_url.split("/")[-1].split("?")[0]
                aktenzeichen = d3_client.get_aktenzeichen(location_url)

                # ==============================================================
                # РАЗДЕЛЕНИЕ ЛОГИКИ: APPLICATION VS FUNDING
                # ==============================================================
                if not is_funding:
                    # ДЛЯ APPLICATION:
                    # Шаг 1: Ищем конкретный документ Meldebogen в папке /009 по UUID
                    if aktenzeichen != "UNBEKANNT":
                        files = search_antrag_files_in_d3(
                            d3_client,
                            aktenzeichen,
                            akte_id,
                            item_uuid=vero_id
                        )
                        target_doc = find_specific_task_document(
                            docs=files,
                            target_folder_code=D3_FOLDER_APPLICATION,
                            item_uuid=vero_id,
                            task_title=project_title
                        )
                        if target_doc:
                            doc_status_in_d3 = target_doc.get("vero_status_515", "UNBEKANNT")
                            logging.info(
                                f"📄 Zugeordnetes d.3-Dokument: ID={target_doc.get('doc_id')} (Titel: '{target_doc.get('title')}', "
                                f"Status={doc_status_in_d3})"
                            )

                    # Шаг 2: Фоллбэк на уровень Акты, если в документе статус UNBEKANNT
                    if doc_status_in_d3 == "UNBEKANNT":
                        doc_status_in_d3 = get_akte_status_in_d3(d3_client, location_url)
                        logging.info(f"📊 Aktueller Aktenstatus [Application] in d.3 (Akte-Ebene, Feld 515): >>> {doc_status_in_d3} <<<")

                else:
                    # ДЛЯ FUNDING: Статус и реквизиты живут на уровне документа в /002!
                    if aktenzeichen != "UNBEKANNT":
                        files = search_antrag_files_in_d3(
                            d3_client,
                            aktenzeichen,
                            akte_id,
                            item_uuid=vero_id
                        )
                        target_doc = find_specific_task_document(
                            docs=files,
                            target_folder_code=D3_FOLDER_FUNDING,
                            item_uuid=vero_id,
                            task_title=project_title
                        )

                        if target_doc:
                            doc_status_in_d3 = target_doc.get("vero_status_515", "UNBEKANNT")
                            fonds_val = target_doc.get("fonds", "") or target_doc.get("kostenstelle", "")
                            finanzstelle_val = target_doc.get("finanzstelle", "")
                            logging.info(
                                f"📄 Zugeordnetes d.3-Dokument: ID={target_doc.get('doc_id')} (Titel: '{target_doc.get('title')}', "
                                f"Fonds='{fonds_val}', Finanzstelle='{finanzstelle_val}')"
                            )
                        else:
                            logging.warning(f"⚠️ d.3-Dokument für Funding (Vero_ID={vero_id}) im Ordner {D3_FOLDER_FUNDING} noch nicht gefunden.")

            logging.info(t("DOC_STATUS_IN_D3", entity_type=entity_type,
                           folder_code=(D3_FOLDER_FUNDING if is_funding else D3_FOLDER_APPLICATION),
                           status=doc_status_in_d3))

            # ------------------------------------------------------------------
            # 1. ОБРАБОТКА ЯВНОГО СТАТУСНОГО ОТКЛОНЕНИЯ В d.3 (ВКЛЮЧАЯ VPPF_abgelehnt)
            # ------------------------------------------------------------------
            if is_rejection_status(doc_status_in_d3):
                logging.info(f"🚫 [ABGELEHNT] {entity_type} in d.3 DMS abgelehnt (Status: {doc_status_in_d3}).")
                scanner.reject_claimed_task(
                    claimedtask_id,
                    reason=f"In d.3 DMS abgelehnt (Status: {doc_status_in_d3})."
                )

            # ------------------------------------------------------------------
            # 2. ОБРАБОТКА ЗАВЕРШЕНИЯ / ОДОБРЕНИЯ
            # ------------------------------------------------------------------
            elif is_approval_status(doc_status_in_d3):
                if is_funding:
                    valid_fonds = is_valid_kostenstelle(fonds_val)
                    valid_finanzstelle = is_valid_kostenstelle(finanzstelle_val)

                    if valid_fonds or valid_finanzstelle:
                        sap_identifiers = []
                        if valid_fonds:
                            sap_identifiers.append(fonds_val)
                        if valid_finanzstelle and finanzstelle_val not in sap_identifiers:
                            sap_identifiers.append(finanzstelle_val)

                        logging.info(f"🎉 [GENEHMIGT] Funding genehmigt mit SAP-Kennungen (Fonds/Finanzstelle): {sap_identifiers}")
                        item_target_uuid = item_info.get("uuid") or vero_id

                        update_ok = update_dspace_internal_ids(
                            scanner=scanner,
                            item_uuid=item_target_uuid,
                            id_values=sap_identifiers
                        )

                        if update_ok:
                            scanner.approve_claimed_task(claimedtask_id)
                        else:
                            logging.error(f"❌ Не удалось записать SAP-идентификаторы в DSpace. Задача {claimedtask_id} не утверждена.")

                    elif is_explicit_rejection_value(fonds_val) or is_explicit_rejection_value(finanzstelle_val):
                        logging.warning(
                            f"🚫 [ABGELEHNT] Finanzdaten wurden in d.3 abgelehnt (Fonds: '{fonds_val}', Finanzstelle: '{finanzstelle_val}'). "
                            f"Aufgabe wird in DSpace abgelehnt."
                        )
                        scanner.reject_claimed_task(
                            claimedtask_id,
                            reason=f"Abgelehnt: Finanzdaten in d.3 abgelehnt (Fonds: '{fonds_val}', Finanzstelle: '{finanzstelle_val}')."
                        )

                    else:
                        logging.info(
                            f"⏳ [WARTEN / IN BEARBEITUNG] Funding-Status in d.3 ist bereits '{doc_status_in_d3}', "
                            f"jedoch sind Fonds ('{fonds_val}') und Finanzstelle ('{finanzstelle_val}') noch leer. "
                            f"Warte auf Formularabschluss im d.3 DMS..."
                        )
                else:
                    logging.info(f"🎉 [GENEHMIGT] Application erfolgreich vom Präsidium genehmigt!")
                    scanner.approve_claimed_task(claimedtask_id)

            # ------------------------------------------------------------------
            # 3. В ПРОЦЕССЕ СОГЛАСОВАНИЯ
            # ------------------------------------------------------------------
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
            except requests.exceptions.ConnectionError as err:
                err_str = str(err).lower()
                if "nameresolutionerror" in err_str or "getaddrinfo failed" in err_str:
                    logging.error(
                        f"❌ Netzwerkfehler im Zyklus #{cycle_count}: Keine Internetverbindung "
                        f"oder DNS-Auflösung fehlgeschlagen (Host nicht erreichbar)."
                    )
                else:
                    logging.error(
                        f"❌ Verbindungsfehler im Zyklus #{cycle_count}: Serververbindung getrennt ({err})."
                    )
            except Exception as e:
                logging.error(t("CYCLE_EXCEPTION", count=cycle_count, e=e), exc_info=True)

            logging.info(t("SLEEPING", seconds=POLL_INTERVAL_SECONDS, next_count=cycle_count + 1))
            time.sleep(POLL_INTERVAL_SECONDS)
            cycle_count += 1

    except KeyboardInterrupt:
        logging.info("\n" + t("SERVICE_STOPPED"))


if __name__ == "__main__":
    main()
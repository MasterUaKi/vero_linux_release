# ==============================================================================
# Script Name: d3_dspace_status_checker.py
# Version:     1.1.0
# Date:        2026-07-27
# Author:      Oleh Riabtsev / AI Assistant
# Description: Read-Only Audit Tool with strict DDRIT document filtering.
#              Excludes parent Akte objects from search results.
# ==============================================================================

import json
import logging
import requests

from dspace_scan_pool_details import DSpacePoolScanner
from d3_api_client import D3DMSClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# === КОНФИГУРАЦИЯ ===
DSPACE_BASE_URL = "http://vero-test.uni-vechta.de/server/api"
BOT_EMAIL = "riabtsev.olehde@gmail.com"
BOT_PASSWORD = "12345abc"

D3_URL = "https://ecm-apps-test.uni-vechta.de"
D3_API_KEY = "ngjRHFXyGGhh+YOeJHswye5bFoMWIC7xvA4fXWIoSHTW4A6PPiV8gujh3u+9KMP2nEGP9Gp7pGE9FoL2HBvDlQweJ2pfQYYLPim96yJnCUYhqD8fFft+jNhqOvH7nGHM&_z_A0V5ayCTQmI1n_IMf365T7Q2iMpfY2OJqTNz9myIfoSF-EHOGlm6yxBq86pcJLAa_41Clh72ASKNancMaat9HVxN1gbxC"
D3_REPO_ID = "f1e1b294-5602-5d8e-8985-e6d0c944b113"


def get_field_515_from_d3_object(d3_client: D3DMSClient, doc_id: str) -> dict:
    """Извлекает значение поля 515 (Vero_Status) и категорию объекта d.3."""
    url = f"{d3_client.base_url}/dms/r/{d3_client.repo_id}/o2/{doc_id}"
    result = {"status_515": "Не найдено", "category": "Неизвестно"}

    try:
        resp = requests.get(url, headers=d3_client.headers)
        if resp.status_code == 200:
            data = resp.json()

            # Извлекаем категорию объекта
            result["category"] = data.get("sourceCategory") or data.get("objectDefinitionId") or "Неизвестно"

            props = data.get("objectProperties", []) or data.get("properties", [])
            for p in props:
                p_id = str(p.get("id") or p.get("key"))
                if p_id == "515":
                    vals = p.get("values")
                    if vals and isinstance(vals, list) and len(vals) > 0:
                        result["status_515"] = vals[0]
                    elif p.get("value"):
                        result["status_515"] = p.get("value")
                    break
    except Exception as e:
        result["status_515"] = f"Ошибка: {str(e)}"

    return result


def search_antrag_files_in_d3(d3_client: D3DMSClient, aktenzeichen: str, akte_id: str) -> list:
    """
    Ищет файлы в папке 'Antrag' (/009) по Vorgangszeichen = [Aktenzeichen]/009.
    Исключает саму Акту и фильтрует только документы категории DDRIT.
    """
    vorgangszeichen = f"{aktenzeichen}/009"
    url = f"{d3_client.base_url}/dms/r/{d3_client.repo_id}/sr/"
    params = {"fulltext": vorgangszeichen}

    found_documents = []

    try:
        resp = requests.get(url, headers=d3_client.headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("_embedded", {}).get("items", []) or data.get("items", [])

            for item in items:
                doc_href = item.get("_links", {}).get("self", {}).get("href", "")
                doc_id = item.get("id") or doc_href.split("/")[-1]

                # Игнорируем саму Акту
                if doc_id == akte_id:
                    continue

                # Получаем детали и поле 515
                doc_info = get_field_515_from_d3_object(d3_client, doc_id)

                found_documents.append({
                    "doc_id": doc_id,
                    "doc_name": item.get("displayName") or item.get("title") or "Meldebogen PDF",
                    "category": doc_info["category"],
                    "vero_status_515": doc_info["status_515"]
                })
    except Exception as e:
        logging.error(f"[-] Ошибка поиска файлов в папке Antrag: {str(e)}")

    return found_documents


def run_full_dspace_d3_audit():
    print("\n==========================================================================")
    print("🔍 ИНСПЕКЦИЯ: ПРОВЕРКА СТАТУСОВ ДОКУМЕНТОВ VERO (ПОЛЕ 515) В d.3 DMS")
    print("==========================================================================")

    # 1. Логин в DSpace
    scanner = DSpacePoolScanner(DSPACE_BASE_URL)
    if not scanner.login(BOT_EMAIL, BOT_PASSWORD):
        logging.error("Не удалось авторизоваться в DSpace!")
        return

    # 2. Сканирование пула DSpace
    pool_summary = scanner.scan_full_pool()
    if not pool_summary or pool_summary.get("total_tasks_in_pool", 0) == 0:
        logging.warning("В пуле DSpace нет активных задач.")
        return

    pool_tasks = pool_summary.get("pool_tasks", [])
    print(f"\n📊 Найдено {len(pool_tasks)} активных заявок в пуле DSpace.\n")

    # 3. Логин в d.3 DMS
    d3_client = D3DMSClient(D3_URL, D3_API_KEY, D3_REPO_ID)
    if not d3_client.login():
        logging.error("Не удалось авторизоваться в d.3 DMS!")
        return

    print("-" * 80)

    # 4. Проход по всем заявкам пула
    for idx, task in enumerate(pool_tasks, start=1):
        wf_details = task.get("workflow_item_details", {})
        item_info = wf_details.get("item_info", {})
        vero_id = item_info.get("uuid") or str(wf_details.get("workflow_item_id"))

        metadata = wf_details.get("metadata", {})
        project_title = metadata.get("dc.title", ["Без названия"])[0]

        print(f"\n[{idx}/{len(pool_tasks)}] 📋 Заявка DSpace: '{project_title}'")
        print(f"    🆔 Vero_ID (UUID): {vero_id}")

        # Поиск Акты в d.3 DMS
        location_url = d3_client.find_akte_by_vero_id(vero_id)

        if not location_url:
            print(f"    ❌ Акта в d.3 DMS: НЕ НАЙДЕНА")
            continue

        # Извлекаем чистое ID Акты
        akte_id = location_url.split("/")[-1].split("?")[0]
        print(f"    ✅ Акта в d.3 DMS: СУЩЕСТВУЕТ (ID Акты: {akte_id})")

        # Получаем Aktenzeichen
        aktenzeichen = d3_client.get_aktenzeichen(location_url)
        print(f"    🔑 Aktenzeichen: {aktenzeichen}")

        if aktenzeichen == "UNBEKANNT":
            print(f"    ⚠️ Не удалось извлечь Aktenzeichen.")
            continue

        # Проверяем папку "Antrag" (/009)
        antrag_vorgangszeichen = f"{aktenzeichen}/009"
        print(f"    📂 Проверка папки 'Antrag' ({antrag_vorgangszeichen})...")

        files = search_antrag_files_in_d3(d3_client, aktenzeichen, akte_id)

        if not files:
            print(f"    📭 Файлы в папке 'Antrag': ОТСУТСТВУЮТ")
        else:
            print(f"    📄 Найдено документов (DDRIT) в папке 'Antrag': {len(files)}")
            for f_idx, doc in enumerate(files, start=1):
                print(f"       [{f_idx}] ID Документа : {doc['doc_id']}")
                print(f"           Категория   : {doc['category']}")
                print(f"           Название    : {doc['doc_name']}")
                print(f"           🎯 ПОЛЕ 515 (Vero_Status): >>> {doc['vero_status_515']} <<<")

    print("\n==========================================================================")
    print("🏁 ИНСПЕКЦИЯ ЗАВЕРШЕНА")
    print("==========================================================================\n")


if __name__ == "__main__":
    run_full_dspace_d3_audit()
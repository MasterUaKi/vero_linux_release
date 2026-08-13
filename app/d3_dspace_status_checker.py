# ==============================================================================
# Script Name: d3_dspace_status_checker.py
# Version:     2.1.0
# Date:        2026-08-13
# Author:      Oleh Riabtsev / AI Assistant
# Description: Helper module to search and check document status in d.3 DMS.
#              FIXED: Removed artificial request delay on GET queries to speed up
#              in-cycle dossier scanning from 32s down to 1-2s per task.
# ==============================================================================

import json
import logging
import requests

from d3_api_client import D3DMSClient


def get_all_properties(data_dict: dict) -> list:
    """Агрессивно собирает все свойства из разных структур d.3 JSON"""
    props = []
    if isinstance(data_dict.get("properties"), list):
        props.extend(data_dict["properties"])
    if isinstance(data_dict.get("objectProperties"), list):
        props.extend(data_dict["objectProperties"])

    source_props = data_dict.get("sourceProperties")
    if isinstance(source_props, dict):
        sp = source_props.get("properties")
        if isinstance(sp, list):
            props.extend(sp)

    return props


def extract_status_515_from_props(props: list) -> str:
    """Извлекает значение поля 515 (verostat / Vero_Status)."""
    if not props: return ""
    target_keys = {"515", "verostat", "vero_status", "verostatus"}

    for p in props:
        if not isinstance(p, dict): continue

        p_id = str(p.get("id", "")).strip().lower()
        p_key = str(p.get("key", "")).strip().lower()
        p_name = str(p.get("name", "")).strip().lower()

        if p_id in target_keys or p_key in target_keys or p_name in target_keys:
            vals = p.get("values")
            if vals and isinstance(vals, list) and len(vals) > 0 and vals[0]:
                return str(vals[0]).strip()
            val = p.get("value")
            if val:
                return str(val).strip()
    return ""


def get_details_from_d3_object(d3_client: D3DMSClient, doc_id: str) -> dict:
    """Точечный запрос свойств объекта без искусственных задержек."""
    url = f"{d3_client.base_url}/dms/r/{d3_client.repo_id}/o2/{doc_id}"
    result = {"status_515": "", "vorgangszeichen": ""}

    try:
        # Без time.sleep: быстрый GET-запрос
        resp = requests.get(url, headers=d3_client.headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            props = get_all_properties(data)

            for p in props:
                p_id = str(p.get("id") or p.get("key") or p.get("name")).strip().lower()
                if p_id in ["12", "vorgangszeichen"]:
                    vals = p.get("values") or [p.get("value")]
                    if vals and vals[0]:
                        result["vorgangszeichen"] = str(vals[0])

            result["status_515"] = extract_status_515_from_props(props)

    except Exception as e:
        logging.debug(f"Ошибка получения деталей объекта {doc_id}: {e}")

    return result


def search_antrag_files_in_d3(d3_client: D3DMSClient, aktenzeichen: str, akte_id: str) -> list:
    """Ищет документы в целевых папках (/009 и /002) Акты."""
    if not aktenzeichen or aktenzeichen == "UNBEKANNT": return []

    url = f"{d3_client.base_url}/dms/r/{d3_client.repo_id}/sr/"
    params = {"fulltext": aktenzeichen}
    found_documents = []

    try:
        resp = requests.get(url, headers=d3_client.headers, params=params, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("_embedded", {}).get("items", []) or data.get("items", [])

            for item in items:
                doc_href = item.get("_links", {}).get("self", {}).get("href", "")
                doc_id = item.get("id") or doc_href.split("/")[-1].split("?")[0]

                if akte_id and doc_id == akte_id:
                    continue  # Пропускаем саму Акту

                props = get_all_properties(item)
                status_515 = extract_status_515_from_props(props)

                vorgangszeichen = ""
                for p in props:
                    p_id = str(p.get("id") or p.get("key") or p.get("name")).strip().lower()
                    if p_id in ["12", "vorgangszeichen"]:
                        vals = p.get("values") or [p.get("value")]
                        if vals and vals[0]:
                            vorgangszeichen = str(vals[0])

                # Запрашиваем детали, только если в краткой карточке не хватило полей
                if not status_515 or not vorgangszeichen:
                    doc_info = get_details_from_d3_object(d3_client, doc_id)
                    if not status_515: status_515 = doc_info["status_515"]
                    if not vorgangszeichen: vorgangszeichen = doc_info["vorgangszeichen"]

                # Фильтруем объекты только из папок /009 и /002
                if vorgangszeichen and (vorgangszeichen.endswith("/009") or vorgangszeichen.endswith("/002")):
                    found_documents.append({
                        "doc_id": doc_id,
                        "vorgangszeichen": vorgangszeichen,
                        "vero_status_515": status_515 or "UNBEKANNT"
                    })

    except Exception as e:
        logging.error(f"[-] Ошибка поиска файлов в d.3 DMS: {str(e)}")

    return found_documents
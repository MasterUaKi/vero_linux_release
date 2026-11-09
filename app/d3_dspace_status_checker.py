# ==============================================================================
# Script Name: d3_dspace_status_checker.py
# Version:     2.15.0
# Date:        2026-11-02
# Author:      Oleh Riabtsev / AI Assistant
# Description: Helper module to search and check document status in d.3 DMS:
#              - Preserves all legacy parsing logic, fallbacks, and validations.
#              - Enhanced search_antrag_files_in_d3: accepts optional item_uuid
#                to reliably locate documents matching either Aktenzeichen or UUID.
#              - Enhanced get_details_from_d3_object: supports 'caption', Betreff
#                property ID 10, and multivalueProperties extraction.
#              - Robust extraction of status 515 (including 'VPPF_abgelehnt' and
#                'Praesidium_Ja').
#              - Dedicated extraction of 'Fonds' (formerly Kostenstelle, key 498).
#              - Dedicated extraction of 'Finanzstelle' (field ID 517 /
#                UUID c154bee5-7f4d-4437-bd1f-8420a368639b).
#              - Strictly document-level extraction without parent Akte fallback.
# ==============================================================================

import json
import logging
import re
import requests

from d3_api_client import D3DMSClient


def get_all_properties(data_dict: dict) -> list:
    """Агрессивно собирает все свойства из разных структур d.3 JSON."""
    props = []
    if isinstance(data_dict.get("properties"), list):
        props.extend(data_dict["properties"])
    if isinstance(data_dict.get("objectProperties"), list):
        props.extend(data_dict["objectProperties"])
    if isinstance(data_dict.get("objectproperties"), list):
        props.extend(data_dict["objectproperties"])
    if isinstance(data_dict.get("multivalueProperties"), list):
        props.extend(data_dict["multivalueProperties"])

    source_props = data_dict.get("sourceProperties")
    if isinstance(source_props, dict):
        sp = source_props.get("properties")
        if isinstance(sp, list):
            props.extend(sp)

    return props


def extract_status_515_from_props(props: list) -> str:
    """
    Извлекает значение статуса воркфлоу с приоритетом точного поля 515 (vero_status).
    Игнорирует пустые значения и не прерывает поиск до нахождения заполненного статуса.
    """
    if not props:
        return ""

    for p in props:
        if not isinstance(p, dict):
            continue

        p_id = str(p.get("id", "")).strip().lower()
        p_name = str(p.get("name", "")).strip().lower()
        p_key = str(p.get("key", "")).strip().lower()

        if p_id == "515" or p_name in ["vero_status", "verostatus", "verostat"] or p_key == "515":
            val = p.get("value")
            if val is not None:
                val_str = str(val).strip()
                if val_str:
                    return val_str

            vals = p.get("values")
            if vals and isinstance(vals, list) and len(vals) > 0 and vals[0] is not None:
                val_str = str(vals[0]).strip()
                if val_str:
                    return val_str

    secondary_keys = {"status", "processing_status"}
    for p in props:
        if not isinstance(p, dict):
            continue

        p_id = str(p.get("id", "")).strip().lower()
        p_name = str(p.get("name", "")).strip().lower()
        p_key = str(p.get("key", "")).strip().lower()

        if p_id in secondary_keys or p_name in secondary_keys or p_key in secondary_keys:
            val = p.get("value")
            if val is not None:
                val_str = str(val).strip()
                if val_str:
                    return val_str

            vals = p.get("values")
            if vals and isinstance(vals, list) and len(vals) > 0 and vals[0] is not None:
                val_str = str(vals[0]).strip()
                if val_str:
                    return val_str

    return ""


def is_valid_kostenstelle(val: str) -> bool:
    """
    Проверяет, что строка является достоверным финансовым номером (Kostenstelle / Fonds / Finanzstelle),
    а не UUID, маркером отказа или пустой заглушкой.
    """
    if not val:
        return False
    val_clean = str(val).strip().lower()

    invalid_markers = {
        "n", "nein", "no", "abgelehnt", "keine", "none", "null",
        "-", "--", "unbekannt", "false", "0", "0000"
    }
    if val_clean in invalid_markers:
        return False

    if len(val_clean) == 36 and val_clean.count("-") == 4:
        return False

    return len(val_clean) >= 2


def is_explicit_rejection_value(val: str) -> bool:
    """Проверяет, введено ли в финансовое поле явное значение отказа."""
    if not val:
        return False
    val_clean = str(val).strip().lower()
    return val_clean in {"n", "nein", "no", "abgelehnt", "verworfen", "abbruch", "keine"}


def extract_kostenstelle_from_props(props: list) -> str:
    """
    Извлекает значение Fonds / Kostenstelle (бывшее поле Kostenstelle, поле 498).
    """
    if not props:
        return ""

    primary_keywords = [
        "fonds",
        "fond",
        "kostenstelle",
        "abrechnungselement",
        "abrechnungselemente",
        "pspelement",
        "psp_element",
        "psp-element",
        "cost_center",
        "costcenter"
    ]

    fallback_keys = {"aktentitel"}

    for p in props:
        if not isinstance(p, dict):
            continue

        p_id = str(p.get("id", "")).strip().lower()
        p_key = str(p.get("key", "")).strip().lower()
        p_name = str(p.get("name", "")).strip().lower()
        p_label = str(p.get("label", "")).strip().lower()
        p_caption = str(p.get("caption", "")).strip().lower()

        cleaned_identifiers = [
            re.sub(r"[^a-zA-Z0-9_]", "", ident)
            for ident in [p_id, p_key, p_name, p_label, p_caption]
            if ident
        ]

        is_match = any(
            any(kw in ident for kw in primary_keywords)
            for ident in cleaned_identifiers
        )

        if is_match:
            vals = p.get("values")
            if vals and isinstance(vals, list) and len(vals) > 0 and vals[0] is not None:
                val_str = str(vals[0]).strip()
                if val_str and val_str.lower() != "null":
                    return val_str
            val = p.get("value")
            if val is not None:
                val_str = str(val).strip()
                if val_str and val_str.lower() != "null":
                    return val_str

    for p in props:
        if not isinstance(p, dict):
            continue

        p_id = str(p.get("id", "")).strip().lower()
        p_key = str(p.get("key", "")).strip().lower()
        p_name = str(p.get("name", "")).strip().lower()

        if p_id in fallback_keys or p_key in fallback_keys or p_name in fallback_keys:
            vals = p.get("values")
            if vals and isinstance(vals, list) and len(vals) > 0 and vals[0] is not None:
                val_str = str(vals[0]).strip()
                if not (len(val_str) == 36 and val_str.count("-") == 4):
                    return val_str
            val = p.get("value")
            if val is not None:
                val_str = str(val).strip()
                if not (len(val_str) == 36 and val_str.count("-") == 4):
                    return val_str

    return ""


def extract_finanzstelle_from_props(props: list) -> str:
    """
    Извлекает значение дополнительного поля 'Finanzstelle'
    (Key: c154bee5-7f4d-4437-bd1f-8420a368639b / ID 517).
    """
    if not props:
        return ""

    target_identifiers = {
        "517",
        "c154bee5-7f4d-4437-bd1f-8420a368639b",
        "c154bee57f4d4437bd1f8420a368639b",
        "finanzstelle",
        "financial_center"
    }

    for p in props:
        if not isinstance(p, dict):
            continue

        p_id = str(p.get("id", "")).strip().lower()
        p_key = str(p.get("key", "")).strip().lower()
        p_name = str(p.get("name", "")).strip().lower()
        p_label = str(p.get("label", "")).strip().lower()

        cleaned_id = re.sub(r"[^a-zA-Z0-9_-]", "", p_id)
        cleaned_key = re.sub(r"[^a-zA-Z0-9_-]", "", p_key)

        if (p_id in target_identifiers or
            p_key in target_identifiers or
            p_name in target_identifiers or
            p_label in target_identifiers or
            cleaned_id in target_identifiers or
            cleaned_key in target_identifiers):

            vals = p.get("values")
            if vals and isinstance(vals, list) and len(vals) > 0 and vals[0] is not None:
                val_str = str(vals[0]).strip()
                if val_str and val_str.lower() != "null":
                    return val_str
            val = p.get("value")
            if val is not None:
                val_str = str(val).strip()
                if val_str and val_str.lower() != "null":
                    return val_str

    return ""


def get_details_from_d3_object(d3_client: D3DMSClient, doc_id: str) -> dict:
    """Точечный запрос свойств объекта d.3 со сбором полного контекста документа."""
    base_url = str(d3_client.base_url).rstrip("/")
    url = f"{base_url}/dms/r/{d3_client.repo_id}/o2/{doc_id}"
    result = {
        "status_515": "",
        "vorgangszeichen": "",
        "fonds": "",
        "finanzstelle": "",
        "kostenstelle": "",
        "title": "",
        "filename": "",
        "vero_id": "",
        "raw_text_dump": ""
    }

    headers = getattr(d3_client, "headers", None) or getattr(d3_client, "_headers", {})

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result["raw_text_dump"] = json.dumps(data).lower()
            result["title"] = str(data.get("caption") or data.get("displayTitle") or data.get("title") or data.get("name") or "").strip()
            result["filename"] = str(data.get("filename") or data.get("fileName") or "").strip()

            props = get_all_properties(data)

            for p in props:
                p_id = str(p.get("id") or "").strip().lower()
                p_key = str(p.get("key") or "").strip().lower()
                p_name = str(p.get("name") or "").strip().lower()
                vals = p.get("values") or [p.get("value")]
                val_first = str(vals[0]).strip() if vals and vals[0] is not None else ""

                if not val_first:
                    continue

                if p_id in ["12", "vorgangszeichen"] or p_key in ["vorgangszeichen"] or p_name in ["vorgangszeichen"]:
                    result["vorgangszeichen"] = val_first
                elif p_id in ["1", "10", "titel", "title", "betreff"] or p_key in ["titel", "title", "betreff"] or p_name in ["titel", "title", "betreff"]:
                    if not result["title"]:
                        result["title"] = val_first
                elif p_id in ["dateiname", "filename"] or p_key in ["dateiname", "filename"] or p_name in ["dateiname", "filename"]:
                    if not result["filename"]:
                        result["filename"] = val_first
                elif "vero" in p_id or "vero" in p_key or "vero" in p_name:
                    if "id" in p_id or "id" in p_key or "id" in p_name:
                        result["vero_id"] = val_first

            result["status_515"] = extract_status_515_from_props(props)
            result["fonds"] = extract_kostenstelle_from_props(props)
            result["finanzstelle"] = extract_finanzstelle_from_props(props)
            result["kostenstelle"] = result["fonds"] or result["finanzstelle"]

    except Exception as e:
        logging.debug(f"Ошибка получения деталей объекта {doc_id}: {e}")

    return result


def search_antrag_files_in_d3(d3_client: D3DMSClient, aktenzeichen: str, akte_id: str = "", item_uuid: str = "") -> list:
    """
    Ищет все документы внутри Акты с полной структурой метаданных.
    Опрашивает как Aktenzeichen, так и item_uuid, чтобы гарантированно находить
    все вложенные файлы (включая Meldebogen), исключая дубликаты.
    """
    if (not aktenzeichen or aktenzeichen == "UNBEKANNT") and not item_uuid:
        return []

    base_url = str(d3_client.base_url).rstrip("/")
    url = f"{base_url}/dms/r/{d3_client.repo_id}/sr/"
    headers = getattr(d3_client, "headers", None) or getattr(d3_client, "_headers", {})

    search_queries = []
    if aktenzeichen and aktenzeichen != "UNBEKANNT":
        search_queries.append(aktenzeichen)
    if item_uuid and len(item_uuid) >= 30 and item_uuid not in search_queries:
        search_queries.append(item_uuid)

    found_documents = []
    seen_ids = set()

    for query in search_queries:
        params = {"fulltext": query}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("_embedded", {}).get("items", []) or data.get("items", [])

                for item in items:
                    doc_href = item.get("_links", {}).get("self", {}).get("href", "")
                    doc_id = item.get("id") or doc_href.split("/")[-1].split("?")[0]

                    if not doc_id or doc_id in seen_ids:
                        continue
                    if akte_id and doc_id == akte_id:
                        continue

                    doc_info = get_details_from_d3_object(d3_client, doc_id)

                    if doc_info["vorgangszeichen"] and (
                        doc_info["vorgangszeichen"].endswith("/009") or
                        doc_info["vorgangszeichen"].endswith("/002")
                    ):
                        seen_ids.add(doc_id)
                        found_documents.append({
                            "doc_id": doc_id,
                            "vorgangszeichen": doc_info["vorgangszeichen"],
                            "vero_status_515": doc_info["status_515"] or "UNBEKANNT",
                            "fonds": doc_info["fonds"],
                            "finanzstelle": doc_info["finanzstelle"],
                            "kostenstelle": doc_info["kostenstelle"],
                            "title": doc_info["title"] or "",
                            "filename": doc_info["filename"] or "",
                            "vero_id": doc_info["vero_id"] or "",
                            "raw_text_dump": doc_info["raw_text_dump"] or ""
                        })

        except Exception as e:
            logging.error(f"[-] Ошибка поиска файлов по запросу '{query}' в d.3 DMS: {str(e)}")

    return found_documents
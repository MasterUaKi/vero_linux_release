# ==============================================================================
# Script Name: d3_dspace_status_checker.py
# Version:     2.4.0
# Date:        2026-08-24
# Author:      Oleh Riabtsev / AI Assistant
# Description: Helper module to search and check document status in d.3 DMS.
#              UPDATED: Added fallback extraction of Kostenstelle from 'Aktentitel'
#              property where d.3 workflow stores the cost center code.
# ==============================================================================

import json
import logging
import requests

from d3_api_client import D3DMSClient


def get_all_properties(data_dict: dict) -> list:
    """Агрессивно собирает все свойства из разных структур d.3 JSON."""
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
    """Извлекает значение поля 515 (verostat / Vero_Status / WF_Status)."""
    if not props:
        return ""
    target_keys = {"515", "verostat", "vero_status", "verostatus", "wf_status"}

    for p in props:
        if not isinstance(p, dict):
            continue

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


def extract_kostenstelle_from_props(props: list) -> str:
    """
    Извлекает значение Kostenstelle / SAP Abrechnungselement из свойств d.3.
    1. Проверяет профильные поля (Abrechnungselement, Abrechnungselemente, Kostenstelle, PSP-Element).
    2. Если они пусты, читает значение из Aktentitel (куда воркфлоу d.3 помещает номер при согласовании).
    """
    if not props:
        return ""

    primary_keys = {
        "abrechnungselement",
        "abrechnungselemente",
        "kostenstelle",
        "cost_center",
        "finanzstelle",
        "sap_kostenstelle",
        "pspelement",
        "psp_element",
        "psp-element"
    }

    fallback_keys = {"aktentitel"}

    # 1. Поиск по профильным SAP/Kostenstelle полям
    for p in props:
        if not isinstance(p, dict):
            continue

        p_id = str(p.get("id", "")).strip().lower()
        p_key = str(p.get("key", "")).strip().lower()
        p_name = str(p.get("name", "")).strip().lower()

        if p_id in primary_keys or p_key in primary_keys or p_name in primary_keys:
            vals = p.get("values")
            if vals and isinstance(vals, list) and len(vals) > 0 and vals[0]:
                val_str = str(vals[0]).strip()
                if val_str:
                    return val_str
            val = p.get("value")
            if val:
                val_str = str(val).strip()
                if val_str:
                    return val_str

    # 2. Фолбэк на поле Aktentitel
    for p in props:
        if not isinstance(p, dict):
            continue

        p_id = str(p.get("id", "")).strip().lower()
        p_key = str(p.get("key", "")).strip().lower()
        p_name = str(p.get("name", "")).strip().lower()

        if p_id in fallback_keys or p_key in fallback_keys or p_name in fallback_keys:
            vals = p.get("values")
            if vals and isinstance(vals, list) and len(vals) > 0 and vals[0]:
                val_str = str(vals[0]).strip()
                if val_str:
                    return val_str
            val = p.get("value")
            if val:
                val_str = str(val).strip()
                if val_str:
                    return val_str

    return ""


def get_details_from_d3_object(d3_client: D3DMSClient, doc_id: str) -> dict:
    """Точечный запрос свойств объекта d.3."""
    url = f"{d3_client.base_url}/dms/r/{d3_client.repo_id}/o2/{doc_id}"
    result = {"status_515": "", "vorgangszeichen": "", "kostenstelle": ""}

    try:
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
            result["kostenstelle"] = extract_kostenstelle_from_props(props)

    except Exception as e:
        logging.debug(f"Ошибка получения деталей объекта {doc_id}: {e}")

    return result


def search_antrag_files_in_d3(d3_client: D3DMSClient, aktenzeichen: str, akte_id: str) -> list:
    """Ищет документы в целевых папках (/009 и /002) Акты."""
    if not aktenzeichen or aktenzeichen == "UNBEKANNT":
        return []

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
                kostenstelle = extract_kostenstelle_from_props(props)

                vorgangszeichen = ""
                for p in props:
                    p_id = str(p.get("id") or p.get("key") or p.get("name")).strip().lower()
                    if p_id in ["12", "vorgangszeichen"]:
                        vals = p.get("values") or [p.get("value")]
                        if vals and vals[0]:
                            vorgangszeichen = str(vals[0])

                if not status_515 or not vorgangszeichen or not kostenstelle:
                    doc_info = get_details_from_d3_object(d3_client, doc_id)
                    if not status_515:
                        status_515 = doc_info["status_515"]
                    if not vorgangszeichen:
                        vorgangszeichen = doc_info["vorgangszeichen"]
                    if not kostenstelle:
                        kostenstelle = doc_info["kostenstelle"]

                if vorgangszeichen and (vorgangszeichen.endswith("/009") or vorgangszeichen.endswith("/002")):
                    found_documents.append({
                        "doc_id": doc_id,
                        "vorgangszeichen": vorgangszeichen,
                        "vero_status_515": status_515 or "UNBEKANNT",
                        "kostenstelle": kostenstelle or ""
                    })

    except Exception as e:
        logging.error(f"[-] Ошибка поиска файлов в d.3 DMS: {str(e)}")

    return found_documents
# ==============================================================================
# Script Name: d3_api_client.py
# Version:     2.9.0
# Date:        2026-08-12
# Author:      Oleh Riabtsev / AI Assistant
# Description: REST API Client for d.3 DMS.
#              UPDATED: Integrated D3_REQUEST_DELAY before API calls to ensure
#              rate-limiting and avoid server timeouts during batch operations.
# ==============================================================================

import json
import logging
import os
import time
import requests

from i18n import t
from config_loader import D3_REQUEST_DELAY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


class D3DMSClient:
    """REST API Клиент для работы с системой d.3 DMS (Университет Фехта)."""

    def __init__(self, base_url: str, api_key: str, repo_id: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.repo_id = repo_id
        self.token = None
        self.headers = {}

    def login(self) -> bool:
        """0. Авторизация в d.3 DMS и получение AuthSessionId."""
        login_url = f"{self.base_url}/identityprovider/login"
        headers_auth = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

        try:
            time.sleep(D3_REQUEST_DELAY)
            response = requests.get(login_url, headers=headers_auth)

            if response.status_code == 200:
                self.token = response.json().get("AuthSessionId")
                self.headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/hal+json",
                    "Origin": self.base_url
                }
                logging.info(t("AUTH_D3_SUCCESS"))
                return True
            else:
                logging.error(f"[-] Ошибка логина d.3! Код: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"[-] Исключение при авторизации в d.3: {str(e)}")
            return False

    def find_akte_by_vero_id(self, vero_id: str) -> str:
        """1. Поиск существующей Акты (ADRIT) через UI-эндпоинт d.3 (/sr/)."""
        url = f"{self.base_url}/dms/r/{self.repo_id}/sr/"
        params = {"fulltext": vero_id}

        try:
            time.sleep(D3_REQUEST_DELAY)
            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 200:
                data = response.json()
                items = data.get("_embedded", {}).get("items", []) or data.get("items", [])

                if items:
                    first_item = items[0]
                    href = first_item.get("_links", {}).get("self", {}).get("href") or first_item.get("id")
                    logging.info(t("AKTE_FOUND", vero_id=vero_id))
                    return href
            return None
        except Exception as e:
            logging.error(f"[-] Исключение при поиске Акты в d.3: {str(e)}")
            return None

    def create_akte(self, akte_payload: dict) -> str:
        """2. Создание Drittmittelakte (ADRIT) и получение ссылки Location."""
        url = f"{self.base_url}/dms/r/{self.repo_id}/o2m"
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"

        try:
            time.sleep(D3_REQUEST_DELAY)
            response = requests.post(url, headers=headers, json=akte_payload)
            if response.status_code in [200, 201]:
                return response.headers.get("Location")
            else:
                logging.error(f"[-] Ошибка создания Akte: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logging.error(f"[-] Исключение при создании Akte: {str(e)}")
            return None

    def get_aktenzeichen(self, location_url: str) -> str:
        """3. Извлечение сгенерированного Aktenzeichen по URL объекта."""
        if not location_url:
            return "UNBEKANNT"

        try:
            obj_id = location_url.split("/o2m/")[1].split("?")[0]
        except Exception:
            obj_id = location_url.split("/")[-1]

        url = f"{self.base_url}/dms/r/{self.repo_id}/o2/{obj_id}"

        try:
            time.sleep(D3_REQUEST_DELAY)
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                props = data.get("objectProperties", []) or data.get("properties", [])

                for p in props:
                    if str(p.get("id")) == "1":  # ID 1 = Aktenzeichen
                        vals = p.get("values")
                        if vals and isinstance(vals, list) and len(vals) > 0:
                            return vals[0]
                        elif p.get("value"):
                            return p.get("value")
            return "UNBEKANNT"
        except Exception:
            return "UNBEKANNT"

    def check_document_exists(self, vorgangszeichen: str, akte_id: str = None) -> bool:
        """ПРОВЕРКА ДУБЛИКАТОВ (исключая родительскую Акту)."""
        url = f"{self.base_url}/dms/r/{self.repo_id}/sr/"
        params = {"fulltext": vorgangszeichen}
        try:
            time.sleep(D3_REQUEST_DELAY)
            resp = requests.get(url, headers=self.headers, params=params)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("_embedded", {}).get("items", []) or data.get("items", [])
                for item in items:
                    doc_id = item.get("id") or \
                             item.get("_links", {}).get("self", {}).get("href", "").split("/")[-1].split("?")[0]

                    if akte_id and doc_id == akte_id:
                        continue

                    categories = item.get("sourceCategories", []) or []
                    obj_def = item.get("objectDefinitionId") or item.get("sourceCategory") or ""

                    props = item.get("properties", []) or item.get("objectProperties", [])
                    matched_vorgang = False
                    for p in props:
                        if str(p.get("id")) == "12" or str(p.get("key")) == "12":
                            vals = p.get("values") or [p.get("value")]
                            if any(vorgangszeichen in str(v) for v in vals if v):
                                matched_vorgang = True

                    if ("DDRIT" in categories or "DDRIT" in str(obj_def)) and matched_vorgang:
                        return True
        except Exception as e:
            logging.error(f"[-] Ошибка при проверке дубликата документа: {str(e)}")
        return False

    def upload_pdf_document(self, pdf_filepath: str, aktenzeichen: str, project_title: str,
                            folder_code: str = "009") -> str:
        """
        4. Загрузка PDF (DDRIT) в 2 шага (Blob + JSON Registration).
        :param pdf_filepath: Путь к файлу
        :param aktenzeichen: Номер Акты (напр. "11.01.0.2026-012")
        :param project_title: Название проекта
        :param folder_code: "009" (Application) или "002" (Funding)
        :return: Location URL созданного документа или пустая строка
        """
        filename = os.path.basename(pdf_filepath)
        vorgangszeichen = f"{aktenzeichen}/{folder_code}"

        clean_title = project_title[:200] if project_title else "Unbenannter_Antrag"
        clean_title = clean_title.replace("/", "-")
        betreff = f"{clean_title}/Meldebogen"

        # Динамический выбор типа документа (Feld 151) на основе кода папки
        doc_type = "Funding" if str(folder_code) == "002" else "Meldebogen"

        # =========================================================
        # ШАГ 1: Временная загрузка бинарного файла (/blob/chunk)
        # =========================================================
        try:
            with open(pdf_filepath, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            logging.error(f"[-] Ошибка чтения файла {pdf_filepath}: {str(e)}")
            return ""

        blob_url = f"{self.base_url}/dms/r/{self.repo_id}/blob/chunk"
        blob_headers = self.headers.copy()
        blob_headers["Content-Type"] = "application/octet-stream"

        time.sleep(D3_REQUEST_DELAY)
        blob_res = requests.post(blob_url, headers=blob_headers, data=file_bytes)

        if blob_res.status_code not in [200, 201]:
            logging.error(f"[-] Ошибка загрузки Blob ({blob_res.status_code}): {blob_res.text}")
            return ""

        content_location_uri = blob_res.headers.get("Location")
        if not content_location_uri:
            logging.error("[-] Сервер не вернул URI загруженного файла (Location header отсутствует)!")
            return ""

        # =========================================================
        # ШАГ 2: Регистрация метаданных документа (/o2m)
        # =========================================================
        payload = {
            "filename": filename,
            "sourceCategory": "DDRIT",
            "sourceId": f"/dms/r/{self.repo_id}/source",
            "contentLocationUri": content_location_uri,
            "sourceProperties": {
                "properties": [
                    {"key": "12", "values": [vorgangszeichen]},
                    {"key": "10", "values": [betreff]},
                    {"key": "151", "values": [doc_type]},
                    {"key": "515", "values": ["Antrag_eingegangen"]}
                ]
            }
        }

        doc_url = f"{self.base_url}/dms/r/{self.repo_id}/o2m"
        doc_headers = self.headers.copy()
        doc_headers["Content-Type"] = "application/json"

        time.sleep(D3_REQUEST_DELAY)
        doc_res = requests.post(doc_url, headers=doc_headers, json=payload)

        if doc_res.status_code in [200, 201]:
            location = doc_res.headers.get("Location", "")
            logging.info(f"✅ Документ [{doc_type}] успешно зарегистрирован в папку [{vorgangszeichen}]!")
            return location
        else:
            try:
                err_details = doc_res.content.decode('utf-8', errors='ignore')
            except Exception:
                err_details = str(doc_res.content)
            logging.error(f"[-] Ошибка регистрации PDF в d.3: Status {doc_res.status_code}")
            logging.error(f"📄 Детали ответа d.3: {err_details}")
            return ""
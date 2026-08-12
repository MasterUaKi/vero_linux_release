# ==============================================================================
# Script Name: dspace_scan_pool_details.py
# Version:     1.7.0
# Date:        2026-08-12
# Author:      Oleh Riabtsev / AI Assistant
# Description: Scanner for both unclaimed (pooltasks) and claimed (claimedtasks)
#              workflow items in DSpace 7 REST API.
#              UPDATED: Added API rate limiting (DSPACE_REQUEST_DELAY) to prevent
#              server overload and blocks.
# ==============================================================================

import json
import logging
import time
from datetime import datetime
import requests

from config_loader import (
    DSPACE_BASE_URL as BASE_URL,
    BOT_EMAIL,
    BOT_PASSWORD,
    DSPACE_REQUEST_DELAY
)
from i18n import t

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


class DSpacePoolScanner:
    def __init__(self, base_url=None):
        self.base_url = (base_url or BASE_URL).rstrip('/')
        self.session = requests.Session()
        self.token = None
        self.user_uuid = None

    def login(self, email=None, password=None):
        """1. Авторизация, получение токенов и UUID пользователя"""
        email = email or BOT_EMAIL
        password = password or BOT_PASSWORD

        logging.info(t("AUTH_DSPACE_STEP1"))

        status_url = f"{self.base_url}/authn/status?embed=eperson"

        time.sleep(DSPACE_REQUEST_DELAY)
        self.session.get(status_url)

        xsrf_cookie = self.session.cookies.get("DSPACE-XSRF-COOKIE")
        if xsrf_cookie:
            self.session.headers.update({"X-XSRF-TOKEN": xsrf_cookie})

        login_url = f"{self.base_url}/authn/login"

        time.sleep(DSPACE_REQUEST_DELAY)
        response = self.session.post(
            login_url,
            data={"user": email, "password": password}
        )

        if response.status_code != 200:
            logging.error(f"Ошибка авторизации! Код: {response.status_code}, Текст: {response.text}")
            return False

        auth_header = response.headers.get("Authorization")
        if not auth_header:
            logging.error("Заголовок Authorization отсутствует в ответе!")
            return False

        self.token = auth_header
        self.session.headers.update({"Authorization": self.token})

        xsrf_cookie = self.session.cookies.get("DSPACE-XSRF-COOKIE")
        if xsrf_cookie:
            self.session.headers.update({"X-XSRF-TOKEN": xsrf_cookie})

        time.sleep(DSPACE_REQUEST_DELAY)
        status_resp = self.session.get(status_url)

        if status_resp.status_code == 200:
            status_data = status_resp.json()
            if status_data.get("authenticated"):
                embedded = status_data.get("_embedded", {})
                eperson = embedded.get("eperson") or embedded.get("ePerson") or {}
                self.user_uuid = eperson.get("id")

                if not self.user_uuid:
                    eperson_href = status_data.get("_links", {}).get("eperson", {}).get("href", "")
                    if eperson_href:
                        self.user_uuid = eperson_href.rstrip('/').split('/')[-1]

                logging.info(t("AUTH_DSPACE_SUCCESS", user_uuid=self.user_uuid))
                return True

        logging.error("Не удалось извлечь UUID пользователя!")
        return False

    def _safe_get_link_data(self, links_dict, key):
        href = links_dict.get(key, {}).get("href")
        if href:
            time.sleep(DSPACE_REQUEST_DELAY)
            resp = self.session.get(href)
            if resp.status_code == 200:
                return resp.json()
        return {}

    def extract_workflow_item_details(self, wf_item_id):
        """2. Детальная сборка информации по одному WorkflowItem"""
        url = f"{self.base_url}/workflow/workflowitems/{wf_item_id}?embed=item,collection,submitter"

        time.sleep(DSPACE_REQUEST_DELAY)
        response = self.session.get(url)

        if response.status_code != 200:
            logging.error(f"Ошибка получения WorkflowItem ID={wf_item_id}! Код: {response.status_code}")
            return None

        wf_data = response.json()
        embedded = wf_data.get("_embedded") or {}
        links = wf_data.get("_links") or {}

        item_data = embedded.get("item") or self._safe_get_link_data(links, "item")
        collection_data = embedded.get("collection") or self._safe_get_link_data(links, "collection")
        submitter_data = embedded.get("submitter") or self._safe_get_link_data(links, "submitter")

        item_uuid = item_data.get("id") or item_data.get("uuid")

        raw_metadata = item_data.get("metadata") or {}
        formatted_metadata = {}
        for field_name, entries in raw_metadata.items():
            if isinstance(entries, list):
                values = [entry.get("value") for entry in entries if isinstance(entry, dict) and "value" in entry]
                formatted_metadata[field_name] = values

        files_info = []
        item_links = item_data.get("_links") or {}
        bitstreams_href = item_links.get("bitstreams", {}).get("href")

        if bitstreams_href:
            time.sleep(DSPACE_REQUEST_DELAY)
            bit_resp = self.session.get(bitstreams_href)
            if bit_resp.status_code == 200:
                bit_data = bit_resp.json()
                bitstreams = (bit_data.get("_embedded") or {}).get("bitstreams") or []
                for b in bitstreams:
                    files_info.append({
                        "id": b.get("id"),
                        "name": b.get("name"),
                        "size_bytes": b.get("sizeBytes"),
                        "mime_type": (b.get("format") or {}).get("mimetype"),
                        "download_url": (b.get("_links") or {}).get("content", {}).get("href")
                    })

        return {
            "workflow_item_id": wf_item_id,
            "step": wf_data.get("step"),
            "sections": wf_data.get("sections"),
            "collection": {
                "id": collection_data.get("id"),
                "name": collection_data.get("name"),
                "handle": collection_data.get("handle")
            },
            "submitter": {
                "id": submitter_data.get("id"),
                "email": submitter_data.get("email"),
                "name": submitter_data.get("name")
            },
            "item_info": {
                "uuid": item_uuid,
                "handle": item_data.get("handle"),
                "in_archive": item_data.get("inArchive"),
                "discoverable": item_data.get("discoverable"),
                "last_modified": item_data.get("lastModified")
            },
            "metadata": formatted_metadata,
            "metadata_raw": raw_metadata,
            "files": files_info
        }

    def scan_full_pool(self):
        """3. Сканирование НОВЫХ нераспределенных задач (pooltasks)"""
        logging.info(t("STEP_2_POOL_SCAN"))

        if not self.user_uuid:
            logging.error("Отсутствует UUID пользователя! Запрос отменен.")
            return None

        url = f"{self.base_url}/workflow/pooltasks/search/findByUser?uuid={self.user_uuid}&embed=workflowitem"

        time.sleep(DSPACE_REQUEST_DELAY)
        response = self.session.get(url)

        if response.status_code != 200:
            logging.error(f"Ошибка получения задач пула! Код: {response.status_code}")
            return None

        data = response.json()
        pool_tasks = (data.get("_embedded") or {}).get("pooltasks") or []

        logging.info(t("POOL_TASKS_FOUND_COUNT", count=len(pool_tasks)))

        detailed_pool_results = []
        for task in pool_tasks:
            pooltask_id = task.get("id")
            step = task.get("step")

            wf_item = (task.get("_embedded") or {}).get("workflowitem") or {}
            wf_item_id = wf_item.get("id")

            if not wf_item_id:
                wf_href = (task.get("_links") or {}).get("workflowitem", {}).get("href", "")
                if wf_href:
                    wf_item_id = wf_href.rstrip('/').split('/')[-1]

            wf_details = self.extract_workflow_item_details(wf_item_id) if wf_item_id else None

            detailed_pool_results.append({
                "pooltask_id": pooltask_id,
                "pool_step": step,
                "workflow_item_details": wf_details
            })

        return {
            "scan_timestamp": datetime.now().isoformat(),
            "bot_user_uuid": self.user_uuid,
            "total_tasks_in_pool": len(detailed_pool_results),
            "pool_tasks": detailed_pool_results
        }

    def scan_claimed_tasks(self):
        """4. Сканирование УЖЕ ПРИНЯТЫХ ботом задач (claimedtasks)"""
        logging.info(t("STEP_3_CLAIMED_SCAN"))

        if not self.user_uuid:
            return []

        url = f"{self.base_url}/workflow/claimedtasks/search/findByUser?uuid={self.user_uuid}&embed=workflowitem"

        time.sleep(DSPACE_REQUEST_DELAY)
        response = self.session.get(url)

        if response.status_code != 200:
            logging.error(f"Ошибка получения claimedtasks! Код: {response.status_code}")
            return []

        data = response.json()
        claimed_tasks = (data.get("_embedded") or {}).get("claimedtasks") or []

        logging.info(t("CLAIMED_TASKS_FOUND_COUNT", count=len(claimed_tasks)))

        detailed_claimed_results = []
        for task in claimed_tasks:
            claimedtask_id = task.get("id")
            step = task.get("step")

            wf_item = (task.get("_embedded") or {}).get("workflowitem") or {}
            wf_item_id = wf_item.get("id")

            if not wf_item_id:
                wf_href = (task.get("_links") or {}).get("workflowitem", {}).get("href", "")
                if wf_href:
                    wf_item_id = wf_href.rstrip('/').split('/')[-1]

            wf_details = self.extract_workflow_item_details(wf_item_id) if wf_item_id else None

            detailed_claimed_results.append({
                "claimedtask_id": claimedtask_id,
                "step": step,
                "workflow_item_details": wf_details
            })

        return detailed_claimed_results

    def claim_pool_task(self, pooltask_id: str) -> bool:
        """5. Принятие (claim) задачи из общего пула DSpace на имя бота"""
        url = f"{self.base_url}/workflow/claimedtasks"
        headers = {
            "Content-Type": "text/uri-list"
        }
        body = f"{self.base_url}/workflow/pooltasks/{pooltask_id}"

        try:
            time.sleep(DSPACE_REQUEST_DELAY)
            response = self.session.post(url, headers=headers, data=body)
            if response.status_code in [200, 201, 204]:
                logging.info(f"🤖 [DSpace] PoolTask ID={pooltask_id} CLAIMED SUCCESSFULLY!")
                return True
            elif response.status_code == 422 or "already" in response.text.lower():
                logging.info(f"ℹ️ [DSpace] PoolTask ID={pooltask_id} already claimed.")
                return True
            else:
                logging.warning(
                    f"⚠️ [DSpace] Failed to claim PoolTask ID={pooltask_id}: Code {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            logging.error(f"[-] Exception claiming PoolTask ID={pooltask_id}: {str(e)}")
            return False

    def approve_claimed_task(self, claimedtask_id: str) -> bool:
        """6. Завершение (одобрение/approve) задачи claimedtask в DSpace."""
        url = f"{self.base_url}/workflow/claimedtasks/{claimedtask_id}"
        data = {"submit_approve": "true"}
        try:
            time.sleep(DSPACE_REQUEST_DELAY)
            response = self.session.post(url, data=data)
            if response.status_code in [200, 201, 204]:
                logging.info(f"🎉 [DSpace] ClaimedTask ID={claimedtask_id} APPROVED SUCCESSFULLY!")
                return True
            else:
                logging.warning(
                    f"⚠️ [DSpace] Failed to approve ClaimedTask ID={claimedtask_id}: Code {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            logging.error(f"[-] Exception approving ClaimedTask ID={claimedtask_id}: {str(e)}")
            return False

    def reject_claimed_task(self, claimedtask_id: str, reason: str = "Отклонено Президиумом") -> bool:
        """7. Отклонение (reject) задачи claimedtask в DSpace."""
        url = f"{self.base_url}/workflow/claimedtasks/{claimedtask_id}"
        data = {
            "submit_reject": "true",
            "reason": reason
        }
        try:
            time.sleep(DSPACE_REQUEST_DELAY)
            response = self.session.post(url, data=data)
            if response.status_code in [200, 201, 204]:
                logging.info(f"❌ [DSpace] ClaimedTask ID={claimedtask_id} REJECTED SUCCESSFULLY!")
                return True
            else:
                logging.warning(
                    f"⚠️ [DSpace] Failed to reject ClaimedTask ID={claimedtask_id}: Code {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            logging.error(f"[-] Exception rejecting ClaimedTask ID={claimedtask_id}: {str(e)}")
            return False
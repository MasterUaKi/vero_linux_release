# ==============================================================================
# Script Name: config_loader.py
# Version:     1.4.0
# Date:        2026-08-13
# Author:      Oleh Riabtsev / AI Assistant
# Description: Centralized configuration loader for VeRO Integration Service.
#              UPDATED: Added multi-language support parameter (ru, en, de).
# ==============================================================================

import configparser
import os

CONFIG_FILE_NAME = "config.cfg"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, CONFIG_FILE_NAME)

config = configparser.ConfigParser()

if os.path.exists(CONFIG_PATH):
    config.read(CONFIG_PATH, encoding="utf-8")
else:
    # Дефолтные значения, если файла config.cfg нет
    config["DSPACE"] = {
        "base_url": "https://dspace-test.uni-vechta.de/server/api",
        "bot_email": "",
        "bot_password": "",
        "request_delay": "1.0"
    }
    config["D3DMS"] = {
        "base_url": "https://ecm-apps-test.uni-vechta.de",
        "api_key": "",
        "repo_id": "",
        "folder_application": "009",
        "folder_funding": "002",
        "request_delay": "1.5"
    }
    config["SERVICE"] = {
        "language": "de",
        "poll_interval_seconds": "360",
        "t_drive_dir": "generated_pdf_meldebogen",
        "log_dir": "logs",
        "log_filename": "vero_integration.log",
        "log_backup_count": "7"
    }

# --- DSpace parameters ---
DSPACE_BASE_URL = config.get("DSPACE", "base_url", fallback="https://dspace-test.uni-vechta.de/server/api")
BOT_EMAIL = config.get("DSPACE", "bot_email", fallback="")
BOT_PASSWORD = config.get("DSPACE", "bot_password", fallback="")
DSPACE_REQUEST_DELAY = config.getfloat("DSPACE", "request_delay", fallback=1.0)

# --- d.3 DMS parameters ---
D3_URL = config.get("D3DMS", "base_url", fallback="https://ecm-apps-test.uni-vechta.de")
D3_API_KEY = config.get("D3DMS", "api_key", fallback="")
D3_REPO_ID = config.get("D3DMS", "repo_id", fallback="")
D3_FOLDER_APPLICATION = config.get("D3DMS", "folder_application", fallback="009")
D3_FOLDER_FUNDING = config.get("D3DMS", "folder_funding", fallback="002")
D3_REQUEST_DELAY = config.getfloat("D3DMS", "request_delay", fallback=1.5)

# --- Service parameters ---
LANGUAGE = config.get("SERVICE", "language", fallback="de").strip().lower()
POLL_INTERVAL_SECONDS = config.getint("SERVICE", "poll_interval_seconds", fallback=360)
T_DRIVE_DIR = config.get("SERVICE", "t_drive_dir", fallback="generated_pdf_meldebogen")
LOG_DIR = config.get("SERVICE", "log_dir", fallback="logs")
LOG_FILENAME = config.get("SERVICE", "log_filename", fallback="vero_integration.log")
LOG_BACKUP_COUNT = config.getint("SERVICE", "log_backup_count", fallback=7)
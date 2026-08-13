# ==============================================================================
# Script Name: config_loader.py
# Version:     1.5.0
# Date:        2026-08-13
# Author:      Oleh Riabtsev / AI Assistant
# Description: Centralized configuration loader for VeRO Integration Service.
#              FIXED: Restored missing D3_DEFAULTS constants (DEFAULT_ZDA, etc.)
#              and added compatibility for [PATHS], [SETTINGS], and [LOGGING].
# ==============================================================================

import configparser
import os

CONFIG_FILE_NAME = "config.cfg"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, CONFIG_FILE_NAME)

config = configparser.ConfigParser()

if os.path.exists(CONFIG_PATH):
    config.read(CONFIG_PATH, encoding="utf-8")


def _get_opt(section: str, option: str, fallback: str = "") -> str:
    if config.has_section(section) and config.has_option(section, option):
        return config.get(section, option)
    return fallback


# --- DSpace parameters ---
DSPACE_BASE_URL = _get_opt("DSPACE", "base_url", "http://vero-test.uni-vechta.de/server/api")
BOT_EMAIL = _get_opt("DSPACE", "bot_email", "")
BOT_PASSWORD = _get_opt("DSPACE", "bot_password", "")
DSPACE_REQUEST_DELAY = float(_get_opt("DSPACE", "request_delay", "1.0"))

# --- d.3 DMS parameters ---
D3_URL = _get_opt("D3DMS", "url", _get_opt("D3DMS", "base_url", "https://ecm-apps-test.uni-vechta.de"))
D3_API_KEY = _get_opt("D3DMS", "api_key", "")
D3_REPO_ID = _get_opt("D3DMS", "repo_id", "")
D3_FOLDER_APPLICATION = _get_opt("D3DMS", "folder_application", "009")
D3_FOLDER_FUNDING = _get_opt("D3DMS", "folder_funding", "002")
D3_REQUEST_DELAY = float(_get_opt("D3DMS", "request_delay", "1.5"))

# --- Paths ---
T_DRIVE_DIR = _get_opt("PATHS", "t_drive_dir", _get_opt("SERVICE", "t_drive_dir", "generated_pdf_meldebogen"))

# --- D3 Defaults ---
DEFAULT_ZDA = _get_opt("D3_DEFAULTS", "zda", "Nein")
DEFAULT_AUSSONDERUNG = _get_opt("D3_DEFAULTS", "aussonderung", "B")
DEFAULT_AUFBEWAHRUNGSFRIST = _get_opt("D3_DEFAULTS", "aufbewahrungsfrist", "120")
DEFAULT_VERO_STATUS = _get_opt("D3_DEFAULTS", "vero_status", "Antrag_eingegangen")

# --- Settings ---
LANGUAGE = _get_opt("SETTINGS", "language", _get_opt("SERVICE", "language", "de")).strip().lower()
POLL_INTERVAL_SECONDS = int(_get_opt("SETTINGS", "poll_interval_seconds", _get_opt("SERVICE", "poll_interval_seconds", "360")))

# --- Logging ---
LOG_DIR = _get_opt("LOGGING", "log_dir", _get_opt("SERVICE", "log_dir", "logs"))
LOG_FILENAME = _get_opt("LOGGING", "log_filename", _get_opt("SERVICE", "log_filename", "vero_integration.log"))
LOG_BACKUP_COUNT = int(_get_opt("LOGGING", "backup_count", _get_opt("LOGGING", "log_backup_count", _get_opt("SERVICE", "log_backup_count", "30"))))
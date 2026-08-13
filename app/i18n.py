# ==============================================================================
# Script Name: i18n.py
# Version:     2.0.0
# Date:        2026-08-13
# Author:      Oleh Riabtsev / AI Assistant
# Description: Internationalization (i18n) module supporting German (de),
#              Russian (ru), and English (en) log messages and output strings.
# ==============================================================================

try:
    from config_loader import LANGUAGE
except ImportError:
    LANGUAGE = "de"

TRANSLATIONS = {
    # ==========================================================================
    # GERMAN (de)
    # ==========================================================================
    "de": {
        "START_SERVICE": "🚀 START DES VERO-INTEGRATIONSDIENSTES (Intervall: {seconds} Sek.)",
        "LOGGING_CONFIGURED": "📁 Protokollierung konfiguriert im Verzeichnis: [{path}]",
        "CYCLE_START": "🔄 --- START DES ZYKLUS #{count} ---",
        "AUTH_DSPACE_STEP1": "--- SCHRITT 1: DSpace-Authentifizierung ---",
        "AUTH_DSPACE_SUCCESS": "Erfolgreiche Authentifizierung! (Benutzer-UUID: {user_uuid})",
        "AUTH_DSPACE_ERROR": "[-] DSpace-Authentifizierungsfehler!",
        "AUTH_D3_SUCCESS": "Erfolgreiche Authentifizierung bei d.3 DMS!",
        "STEP_2_POOL_SCAN": "--- SCHRITT 2: Scannen von nicht zugewiesenen Aufgaben (pooltasks) ---",
        "STEP_3_CLAIMED_SCAN": "--- SCHRITT 3: Scannen von vom Bot übernommenen Aufgaben (claimedtasks) ---",
        "POOL_TASKS_FOUND_COUNT": "Neue Aufgaben im Pool gefunden: {count}",
        "CLAIMED_TASKS_FOUND_COUNT": "Vom Bot bereits übernommene Aufgaben gefunden: {count}",
        "PHASE_1_TITLE": "🔹 PHASE 1: Scannen des nicht zugewiesenen Pools (pooltasks)",
        "PHASE_2_TITLE": "🔹 PHASE 2: Scannen der vom Bot übernommenen Aufgaben (claimedtasks)",
        "FOUND_POOL_TASKS": "{count} neue Aufgaben im Pool gefunden. Starte Verarbeitung...",
        "NO_POOL_TASKS": "Keine neuen Aufgaben im allgemeinen Pool vorhanden.",
        "FOUND_CLAIMED_TASKS": "{count} Aufgaben beim Bot gefunden. Statusprüfung...",
        "NO_CLAIMED_TASKS": "Keine vom Bot übernommenen Aufgaben vorhanden.",
        "POOL_TASK_INFO": "[{idx}/{total}] PoolTask ID={task_id} | Typ: [{entity_type}] | Vero_ID={vero_id}",
        "CLAIMED_TASK_INFO": "[{idx}/{total}] ClaimedTask ID={task_id} | Typ: [{entity_type}] | Vero_ID={vero_id}",
        "TASK_TITLE": "📌 Titel: '{title}'",
        "TARGET_FOLDER": "📁 Zielordner in d.3 DMS: [{folder_name}] (Code: /{folder_code})",
        "SEARCH_PARENT_AKTE": "🔗 [Funding] Suche nach ÜBERGEORDNETER Application-Akte (ID: '{app_uuid}')...",
        "MISSING_LINKED_APP": "⚠️ Beim Funding-Eintrag fehlt die verknüpfte Application-UUID!",
        "WAITING_PARENT_AKTE": "⏳ Übergeordnete Akte (Application UUID={app_uuid}) noch nicht in d.3 DMS erstellt. Überspringen.",
        "PARENT_STATUS": "📊 Status des übergeordneten Antrags (Application) in d.3 (Feld 515): >>> {status} <<<",
        "WAITING_PRAESIDIUM": "⏳ Übergeordneter Antrag (UUID={app_uuid}) noch nicht vom Präsidium genehmigt (Status: {status}). Warten...",
        "APPROVED_PRAESIDIUM": "✅ [BESTÄTIGT] Übergeordneter Antrag vom Präsidium genehmigt! Verwende dessen Akte.",
        "CREATE_NEW_AKTE": "🆕 Akte nicht gefunden. Erstelle neue Drittmittelakte (ADRIT) in d.3 DMS...",
        "AKTE_FOUND": "🎯 [SUCHERFOLG] Akte mit Vero_ID={vero_id} GEFUNDEN!",
        "DOC_EXISTS": "⚠️ Dokument [{folder_name}] EXISTIERT BEREITS in d.3 DMS (Vorgangszeichen: {vorgangszeichen}). Überspringen.",
        "UPLOADING_PDF": "📤 Lade PDF {entity_type} in übergeordnete Akte [{aktenzeichen}] hoch, Ordner [{folder_name}] (/{folder_code})...",
        "DOC_STATUS_IN_D3": "📊 Aktueller Dokumentenstatus [{entity_type}] in d.3 (Ordner /{folder_code}, Feld 515): >>> {status} <<<",
        "APPROVED_WITH_COMMENT": "🎉 [MIT AUFLAGEN GENEHMIGT] {entity_type} vom Präsidium genehmigt (mit Kommentaren/Auflagen)!",
        "APPROVED_SIMPLE": "🎉 [GENEHMIGT] {entity_type} erfolgreich vom Präsidium genehmigt!",
        "REJECTED": "❌ [ABGELEHNT] {entity_type} vom Präsidium in d.3 DMS abgelehnt!",
        "REJECT_REASON": "Vom Präsidium in d.3 DMS abgelehnt",
        "IN_PROGRESS": "⏳ [IN BEARBEITUNG] {entity_type} befindet sich in d.3 DMS in der Abstimmung (Aktuelle Stufe: {status}).",
        "CYCLE_COMPLETE": "🏁 VOLLSTÄNDIGER INTEGRATIONSZYKLUS ABGESCHLOSSEN!",
        "SLEEPING": "💤 Warten auf die nächsten {seconds} Sekunden vor Zyklus #{next_count}...",
        "CYCLE_EXCEPTION": "❌ Ausnahmefehler im Zyklus #{count}: {e}",
        "SERVICE_STOPPED": "🛑 Dienst vom Benutzer gestoppt."
    },

    # ==========================================================================
    # RUSSIAN (ru)
    # ==========================================================================
    "ru": {
        "START_SERVICE": "🚀 ЗАПУСК СЛУЖБЫ ИНТЕГРАЦИИ VERO (Интервал: {seconds} сек.)",
        "LOGGING_CONFIGURED": "📁 Логирование настроено в директории: [{path}]",
        "CYCLE_START": "🔄 --- СТАРТ ЦИКЛА #{count} ---",
        "AUTH_DSPACE_STEP1": "--- ШАГ 1: Авторизация в DSpace ---",
        "AUTH_DSPACE_SUCCESS": "Успешная авторизация в DSpace! (UUID пользователя: {user_uuid})",
        "AUTH_DSPACE_ERROR": "[-] Ошибка авторизации в DSpace!",
        "AUTH_D3_SUCCESS": "Успешная авторизация в d.3 DMS!",
        "STEP_2_POOL_SCAN": "--- ШАГ 2: Сканирование нераспределенных задач (pooltasks) ---",
        "STEP_3_CLAIMED_SCAN": "--- ШАГ 3: Сканирование задач, взятых ботом (claimedtasks) ---",
        "POOL_TASKS_FOUND_COUNT": "Найдено новых задач в пуле: {count}",
        "CLAIMED_TASKS_FOUND_COUNT": "Задач, взятых ботом: {count}",
        "PHASE_1_TITLE": "🔹 ФАЗА 1: Сканирование общего пула (pooltasks)",
        "PHASE_2_TITLE": "🔹 ФАЗА 2: Сканирование принятых ботом задач (claimedtasks)",
        "FOUND_POOL_TASKS": "Найдено новых задач в пуле: {count}. Начинаем обработку...",
        "NO_POOL_TASKS": "В общем пуле нет новых задач.",
        "FOUND_CLAIMED_TASKS": "Найдено задач у бота: {count}. Проверка статусов...",
        "NO_CLAIMED_TASKS": "У бота нет активных взятых задач.",
        "POOL_TASK_INFO": "[{idx}/{total}] PoolTask ID={task_id} | Тип: [{entity_type}] | Vero_ID={vero_id}",
        "CLAIMED_TASK_INFO": "[{idx}/{total}] ClaimedTask ID={task_id} | Тип: [{entity_type}] | Vero_ID={vero_id}",
        "TASK_TITLE": "📌 Название: '{title}'",
        "TARGET_FOLDER": "📁 Целевая папка в d.3 DMS: [{folder_name}] (Код: /{folder_code})",
        "SEARCH_PARENT_AKTE": "🔗 [Funding] Поиск РОДИТЕЛЬСКОЙ Акты Application (ID: '{app_uuid}')...",
        "MISSING_LINKED_APP": "⚠️ У записи Funding отсутствует привязанный UUID Application!",
        "WAITING_PARENT_AKTE": "⏳ Родительская Акта (Application UUID={app_uuid}) еще не создана в d.3 DMS. Пропуск.",
        "PARENT_STATUS": "📊 Статус родительской Заявки (Application) в d.3 (Поле 515): >>> {status} <<<",
        "WAITING_PRAESIDIUM": "⏳ Родительская Заявка (UUID={app_uuid}) еще не одобрена Президиумом (Текущий статус: {status}). Ожидание...",
        "APPROVED_PRAESIDIUM": "✅ [ПОДТВЕРЖДЕНО] Родительская Заявка одобрена Президиумом! Используем её Акту.",
        "CREATE_NEW_AKTE": "🆕 Акта не найдена. Создаем новую Drittmittelakte (ADRIT) в d.3 DMS...",
        "AKTE_FOUND": "🎯 [УСПЕХ ПОИСКА] Акта с Vero_ID={vero_id} НАЙДЕНА в d.3 DMS!",
        "DOC_EXISTS": "⚠️ Документ [{folder_name}] УЖЕ СУЩЕСТВУЕТ в d.3 DMS (Vorgangszeichen: {vorgangszeichen}). Пропуск.",
        "UPLOADING_PDF": "📤 Загрузка PDF {entity_type} в Акту [{aktenzeichen}], папка [{folder_name}] (/{folder_code})...",
        "DOC_STATUS_IN_D3": "📊 Текущий статус документа [{entity_type}] в d.3 (Папка /{folder_code}, Поле 515): >>> {status} <<<",
        "APPROVED_WITH_COMMENT": "🎉 [ОДОБРЕНО С КОММЕНТАРИЕМ] {entity_type} успешно одобрен Президиумом (есть замечания/условия)!",
        "APPROVED_SIMPLE": "🎉 [ОДОБРЕНО] {entity_type} успешно одобрен Президиумом!",
        "REJECTED": "❌ [ОТКЛОНЕНО] {entity_type} отклонен Президиумом в d.3 DMS!",
        "REJECT_REASON": "Отклонено Президиумом в d.3 DMS",
        "IN_PROGRESS": "⏳ [В ОБРАБОТКЕ] {entity_type} находится на согласовании в d.3 DMS (Текущий статус: {status}).",
        "CYCLE_COMPLETE": "🏁 ПОЛНЫЙ ЦИКЛ ИНТЕГРАЦИИ ЗАВЕРШЕН!",
        "SLEEPING": "💤 Ожидание следующих {seconds} секунд перед циклом #{next_count}...",
        "CYCLE_EXCEPTION": "❌ Исключение в цикле #{count}: {e}",
        "SERVICE_STOPPED": "🛑 Служба остановлена пользователем."
    },

    # ==========================================================================
    # ENGLISH (en)
    # ==========================================================================
    "en": {
        "START_SERVICE": "🚀 STARTING VERO INTEGRATION SERVICE (Interval: {seconds} sec)",
        "LOGGING_CONFIGURED": "📁 Logging configured in directory: [{path}]",
        "CYCLE_START": "🔄 --- START OF CYCLE #{count} ---",
        "AUTH_DSPACE_STEP1": "--- STEP 1: DSpace Authentication ---",
        "AUTH_DSPACE_SUCCESS": "DSpace authentication successful! (User UUID: {user_uuid})",
        "AUTH_DSPACE_ERROR": "[-] DSpace authentication error!",
        "AUTH_D3_SUCCESS": "d.3 DMS authentication successful!",
        "STEP_2_POOL_SCAN": "--- STEP 2: Scanning unassigned pool tasks (pooltasks) ---",
        "STEP_3_CLAIMED_SCAN": "--- STEP 3: Scanning tasks claimed by bot (claimedtasks) ---",
        "POOL_TASKS_FOUND_COUNT": "New pool tasks found: {count}",
        "CLAIMED_TASKS_FOUND_COUNT": "Tasks claimed by bot found: {count}",
        "PHASE_1_TITLE": "🔹 PHASE 1: Scanning unassigned pool (pooltasks)",
        "PHASE_2_TITLE": "🔹 PHASE 2: Scanning tasks claimed by bot (claimedtasks)",
        "FOUND_POOL_TASKS": "Found {count} new tasks in pool. Starting processing...",
        "NO_POOL_TASKS": "No new tasks in the general pool.",
        "FOUND_CLAIMED_TASKS": "Found {count} claimed tasks for bot. Checking status...",
        "NO_CLAIMED_TASKS": "No claimed tasks for bot.",
        "POOL_TASK_INFO": "[{idx}/{total}] PoolTask ID={task_id} | Type: [{entity_type}] | Vero_ID={vero_id}",
        "CLAIMED_TASK_INFO": "[{idx}/{total}] ClaimedTask ID={task_id} | Type: [{entity_type}] | Vero_ID={vero_id}",
        "TASK_TITLE": "📌 Title: '{title}'",
        "TARGET_FOLDER": "📁 Target folder in d.3 DMS: [{folder_name}] (Code: /{folder_code})",
        "SEARCH_PARENT_AKTE": "🔗 [Funding] Searching for PARENT Application folder (ID: '{app_uuid}')...",
        "MISSING_LINKED_APP": "⚠️ Missing linked Application UUID for Funding entry!",
        "WAITING_PARENT_AKTE": "⏳ Parent folder (Application UUID={app_uuid}) not created in d.3 DMS yet. Skipping.",
        "PARENT_STATUS": "📊 Status of parent Application in d.3 (Field 515): >>> {status} <<<",
        "WAITING_PRAESIDIUM": "⏳ Parent Application (UUID={app_uuid}) not approved by Executive Board yet (Status: {status}). Waiting...",
        "APPROVED_PRAESIDIUM": "✅ [CONFIRMED] Parent Application approved by Executive Board! Using its folder.",
        "CREATE_NEW_AKTE": "🆕 Folder not found. Creating new Drittmittelakte (ADRIT) in d.3 DMS...",
        "AKTE_FOUND": "🎯 [SEARCH SUCCESS] Folder with Vero_ID={vero_id} FOUND in d.3 DMS!",
        "DOC_EXISTS": "⚠️ Document [{folder_name}] ALREADY EXISTS in d.3 DMS (Vorgangszeichen: {vorgangszeichen}). Skipping.",
        "UPLOADING_PDF": "📤 Uploading PDF {entity_type} to folder [{aktenzeichen}], subfolder [{folder_name}] (/{folder_code})...",
        "DOC_STATUS_IN_D3": "📊 Current document status [{entity_type}] in d.3 (Folder /{folder_code}, Field 515): >>> {status} <<<",
        "APPROVED_WITH_COMMENT": "🎉 [APPROVED WITH COMMENTS] {entity_type} approved by Executive Board (with comments/conditions)!",
        "APPROVED_SIMPLE": "🎉 [APPROVED] {entity_type} successfully approved by Executive Board!",
        "REJECTED": "❌ [REJECTED] {entity_type} rejected by Executive Board in d.3 DMS!",
        "REJECT_REASON": "Rejected by Executive Board in d.3 DMS",
        "IN_PROGRESS": "⏳ [IN PROGRESS] {entity_type} is in review in d.3 DMS (Current stage: {status}).",
        "CYCLE_COMPLETE": "🏁 FULL INTEGRATION CYCLE COMPLETED!",
        "SLEEPING": "💤 Waiting {seconds} seconds before cycle #{next_count}...",
        "CYCLE_EXCEPTION": "❌ Exception in cycle #{count}: {e}",
        "SERVICE_STOPPED": "🛑 Service stopped by user."
    }
}


def t(key: str, **kwargs) -> str:
    """
    Возвращает переведённую строку по ключу key для языка, выбранного в config.cfg.
    Используется безопасный фоллбэк: Выбранный язык -> Немецкий (de) -> Русский (ru) -> Сам ключ.
    """
    lang = LANGUAGE if LANGUAGE in TRANSLATIONS else "de"
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["de"])

    template = lang_dict.get(key)
    if template is None:
        template = TRANSLATIONS["de"].get(key, TRANSLATIONS["ru"].get(key, key))

    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    return template
# ==============================================================================
# Script Name: i18n.py
# Version:     1.1.0
# Date:        2026-08-04
# Author:      Oleh Riabtsev / AI Assistant
# Description: Lightweight Internationalization (i18n) module for VeRO.
# ==============================================================================

from config_loader import LANGUAGE

MESSAGES = {
    # === Старт и остановка сервиса ===
    "START_SERVICE": {
        "ru": "🚀 ЗАПУСК СЛУЖБЫ ВЕРО ИНТЕГРАЦИИ (Интервал: {seconds} сек)",
        "de": "🚀 START DES VERO-INTEGRATIONSDIENSTES (Intervall: {seconds} Sek.)"
    },
    "LOGGING_CONFIGURED": {
        "ru": "📁 Логирование настроено в директорию: [{path}]",
        "de": "📁 Protokollierung konfiguriert im Verzeichnis: [{path}]"
    },
    "CYCLE_START": {
        "ru": "🔄 --- СТАРТ ЦИКЛА #{count} ---",
        "de": "🔄 --- START DES ZYKLUS #{count} ---"
    },
    "SLEEPING": {
        "ru": "💤 Ожидание следующих {seconds} секунд перед циклом #{next_count}...",
        "de": "💤 Warten auf die nächsten {seconds} Sekunden vor Zyklus #{next_count}..."
    },
    "SERVICE_STOPPED": {
        "ru": "🛑 Сервис остановлен пользователем (Ctrl+C). До связи!",
        "de": "🛑 Dienst durch Benutzer gestoppt (Ctrl+C). Auf Wiedersehen!"
    },
    "CYCLE_EXCEPTION": {
        "ru": "❌ Исключение во время выполнения цикла #{count}: {e}",
        "de": "❌ Ausnahmefehler während der Ausführung von Zyklus #{count}: {e}"
    },

    # === Авторизация и шаги клиентов ===
    "AUTH_DSPACE_STEP1": {
        "ru": "--- ШАГ 1: Авторизация в DSpace ---",
        "de": "--- SCHRITT 1: DSpace-Authentifizierung ---"
    },
    "AUTH_DSPACE_SUCCESS": {
        "ru": " Успешная авторизация! (User UUID: {user_uuid})",
        "de": " Erfolgreiche Authentifizierung! (Benutzer-UUID: {user_uuid})"
    },
    "AUTH_D3_SUCCESS": {
        "ru": " Успешная авторизация в d.3 DMS!",
        "de": " Erfolgreiche Authentifizierung bei d.3 DMS!"
    },
    "AUTH_DSPACE_ERROR": {
        "ru": "Ошибка авторизации в DSpace!",
        "de": "DSpace-Authentifizierungsfehler!"
    },
    "AKTE_FOUND": {
        "ru": "🎯 [УСПЕХ ПОИСКА] Акта с Vero_ID={vero_id} НАЙДЕНА!",
        "de": "🎯 [SUCHERFOLG] Akte mit Vero_ID={vero_id} GEFUNDEN!"
    },
    "STEP_2_POOL_SCAN": {
        "ru": "--- ШАГ 2: Сканирование нераспределенных задач (pooltasks) ---",
        "de": "--- SCHRITT 2: Scannen von nicht zugewiesenen Aufgaben (pooltasks) ---"
    },
    "POOL_TASKS_FOUND_COUNT": {
        "ru": " Найдено новых задач в пуле: {count}",
        "de": " Neue Aufgaben im Pool gefunden: {count}"
    },
    "STEP_3_CLAIMED_SCAN": {
        "ru": "--- ШАГ 3: Сканирование принятых ботом задач (claimedtasks) ---",
        "de": "--- SCHRITT 3: Scannen von vom Bot übernommenen Aufgaben (claimedtasks) ---"
    },
    "CLAIMED_TASKS_FOUND_COUNT": {
        "ru": " Найдено уже принятых задач у бота: {count}",
        "de": " Vom Bot bereits übernommene Aufgaben gefunden: {count}"
    },

    # === Фазы и сканирование ===
    "PHASE_1_TITLE": {
        "ru": "🔹 ФАЗА 1: Сканирование нераспределенного пула (pooltasks)",
        "de": "🔹 PHASE 1: Scannen des nicht zugewiesenen Pools (pooltasks)"
    },
    "FOUND_POOL_TASKS": {
        "ru": "Найдено {count} новых задач в пуле. Начинаем обработку...",
        "de": "{count} neue Aufgaben im Pool gefunden. Starte Verarbeitung..."
    },
    "NO_POOL_TASKS": {
        "ru": "Новых задач в общем пуле нет.",
        "de": "Keine neuen Aufgaben im allgemeinen Pool vorhanden."
    },
    "PHASE_2_TITLE": {
        "ru": "🔹 ФАЗА 2: Сканирование принятых ботом задач (claimedtasks)",
        "de": "🔹 PHASE 2: Scannen der vom Bot übernommenen Aufgaben (claimedtasks)"
    },
    "FOUND_CLAIMED_TASKS": {
        "ru": "Найдено {count} задач у бота. Проверка статусов...",
        "de": "{count} Aufgaben beim Bot gefunden. Statusprüfung..."
    },
    "NO_CLAIMED_TASKS": {
        "ru": "Принятых задач у бота пока нет.",
        "de": "Derzeit keine übernommenen Aufgaben beim Bot."
    },
    "CYCLE_COMPLETE": {
        "ru": "🏁 ПОЛНЫЙ ЦИКЛ ИНТЕГРАЦИИ ЗАВЕРШЕН!",
        "de": "🏁 VOLLSTÄNDIGER INTEGRATIONSZYKLUS ABGESCHLOSSEN!"
    },

    # === Логирование обработки задач ===
    "POOL_TASK_INFO": {
        "ru": "[{idx}/{total}] PoolTask ID={task_id} | Тип: [{entity_type}] | Vero_ID={vero_id}",
        "de": "[{idx}/{total}] PoolTask ID={task_id} | Typ: [{entity_type}] | Vero_ID={vero_id}"
    },
    "CLAIMED_TASK_INFO": {
        "ru": "[{idx}/{total}] ClaimedTask ID={task_id} | Тип: [{entity_type}] | Vero_ID={vero_id}",
        "de": "[{idx}/{total}] ClaimedTask ID={task_id} | Typ: [{entity_type}] | Vero_ID={vero_id}"
    },
    "TASK_TITLE": {
        "ru": "📌 Название: '{title}'",
        "de": "📌 Titel: '{title}'"
    },
    "TARGET_FOLDER": {
        "ru": "📁 Целевая папка в d.3 DMS: [{folder_name}] (Код: /{folder_code})",
        "de": "📁 Zielordner in d.3 DMS: [{folder_name}] (Code: /{folder_code})"
    },
    "SEARCH_PARENT_AKTE": {
        "ru": "🔗 [Funding] Поиск РОДИТЕЛЬСКОЙ Акты Application (ID: '{app_uuid}')...",
        "de": "🔗 [Funding] Suche nach ÜBERGEORDNETER Application-Akte (ID: '{app_uuid}')..."
    },
    "MISSING_LINKED_APP": {
        "ru": "⚠️ У объекта Funding отсутствует ссылка на Application! Пропускаем.",
        "de": "⚠️ Für das Funding-Objekt fehlt der Verweis auf Application! Überspringe."
    },
    "WAITING_PARENT_AKTE": {
        "ru": "⏳ [ОЖИДАНИЕ] Родительская Акта Application ({app_uuid}) еще не создана в d.3 DMS. Пропускаем Funding.",
        "de": "⏳ [WARTEN] Übergeordnete Application-Akte ({app_uuid}) wurde in d.3 DMS noch nicht erstellt. Überspringe Funding."
    },
    "PARENT_STATUS": {
        "ru": "📊 Статус родительской Заявки (Application) в d.3 (Поле 515): >>> {status} <<<",
        "de": "📊 Status des übergeordneten Antrags (Application) in d.3 (Feld 515): >>> {status} <<<"
    },
    "WAITING_PRAESIDIUM": {
        "ru": "⏳ [ОЖИДАНИЕ] Заявка {app_uuid} еще НЕ одобрена Президиумом (Текущий этап: {status}). Обработка Funding отложена.",
        "de": "⏳ [WARTEN] Antrag {app_uuid} wurde noch NICHT vom Präsidium genehmigt (Aktuelle Stufe: {status}). Funding-Verarbeitung verschoben."
    },
    "APPROVED_PRAESIDIUM": {
        "ru": "✅ [ПОДТВЕРЖДЕНО] Родительская Заявка одобрена Президиумом! Используем её Акту.",
        "de": "✅ [BESTÄTIGT] Übergeordneter Antrag vom Präsidium genehmigt! Verwende dessen Akte."
    },
    "CREATE_NEW_AKTE": {
        "ru": "➕ Создаем новую Акту в d.3 DMS для Application...",
        "de": "➕ Erstelle neue Akte in d.3 DMS für Application..."
    },
    "DOC_EXISTS": {
        "ru": "⚠️ Документ уже существует в папке [{folder_name}] ({vorgangszeichen}).",
        "de": "⚠️ Dokument existiert bereits im Ordner [{folder_name}] ({vorgangszeichen})."
    },
    "UPLOADING_PDF": {
        "ru": "📤 Загрузка PDF {entity_type} в родительскую Акту [{aktenzeichen}], папка [{folder_name}] (/{folder_code})...",
        "de": "📤 Lade PDF {entity_type} in übergeordnete Akte [{aktenzeichen}] hoch, Ordner [{folder_name}] (/{folder_code})..."
    },
    "DOC_STATUS_IN_D3": {
        "ru": "📊 Текущий статус документа [{entity_type}] в d.3 (Папка /{folder_code}, Поле 515): >>> {status} <<<",
        "de": "📊 Aktueller Dokumentenstatus [{entity_type}] in d.3 (Ordner /{folder_code}, Feld 515): >>> {status} <<<"
    },
    "APPROVED_WITH_COMMENT": {
        "ru": "🎉 [ПОЛОЖИТЕЛЬНОЕ РЕШЕНИЕ] Президиум УТВЕРДИЛ {entity_type} С КОММЕНТАРИЕМ/УСЛОВИЕМ!",
        "de": "🎉 [POSITIVER BESCHEID] Präsidium hat {entity_type} MIT KOMMENTAR/AUFLAGEN GENEHMIGT!"
    },
    "APPROVED_SIMPLE": {
        "ru": "🎉 [ПОЛОЖИТЕЛЬНОЕ РЕШЕНИЕ] Президиум УТВЕРДИЛ {entity_type}!",
        "de": "🎉 [POSITIVER BESCHEID] Präsidium hat {entity_type} GENEHMIGT!"
    },
    "REJECTED": {
        "ru": "❌ [ОТКАЗ] Президиум ОТКЛОНИЛ {entity_type}.",
        "de": "❌ [ABLEHNUNG] Präsidium hat {entity_type} ABGELEHNT."
    },
    "REJECT_REASON": {
        "ru": "Отклонено Президиумом в d.3 DMS",
        "de": "Vom Präsidium in d.3 DMS abgelehnt"
    },
    "IN_PROGRESS": {
        "ru": "⏳ [В ПРОЦЕССЕ] {entity_type} находится на согласовании в d.3 DMS (Текущий этап: {status}).",
        "de": "⏳ [IN BEARBEITUNG] {entity_type} befindet sich in d.3 DMS in der Abstimmung (Aktuelle Stufe: {status})."
    }
}


def t(key: str, **kwargs) -> str:
    lang_dict = MESSAGES.get(key, {})
    template = lang_dict.get(LANGUAGE) or lang_dict.get("ru") or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
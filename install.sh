#!/bin/bash
# ==============================================================================
# File Name:   install.sh
# Version:     1.2.0
# Date:        2026-11-11
# Author:      Oleh Riabtsev
# Description: Automated installer for VeRO Integration Service (Ubuntu/Debian).
#              - Provisions system user and isolated directory structure
#              - Avoids self-copy warnings when cloned directly into /opt
#              - Configures git core.fileMode false to prevent chmod conflicts
#              - Disables pip cache (--no-cache-dir) for system user without $HOME
# ==============================================================================

set -e

INSTALL_DIR="/opt/vero-integration"
SERVICE_NAME="vero-integration.service"
USER_NAME="vero-bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Начинаем установку VeRO Integration Service (v1.2.0)..."

# 1. Создание системного пользователя (без интерактивной оболочки)
if ! id "$USER_NAME" &>/dev/null; then
    echo "👤 Создание системного пользователя $USER_NAME..."
    sudo useradd -r -s /bin/false "$USER_NAME"
fi

# 2. Создание рабочих директорий
echo "📁 Создание рабочих директорий..."
sudo mkdir -p "$INSTALL_DIR/app"
sudo mkdir -p "$INSTALL_DIR/logs"
sudo mkdir -p "$INSTALL_DIR/generated_pdf_meldebogen"

# 3. Копирование исходного кода (только если запуск идет не из целевой папки)
echo "📄 Проверка и копирование исходного кода..."
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    sudo cp -r "$SCRIPT_DIR/app/"* "$INSTALL_DIR/app/"
    if [ -f "$SCRIPT_DIR/$SERVICE_NAME" ]; then
        sudo cp "$SCRIPT_DIR/$SERVICE_NAME" "$INSTALL_DIR/$SERVICE_NAME"
    fi
fi

# Копируем шаблон как рабочий конфиг, если он еще не создан
if [ ! -f "$INSTALL_DIR/app/config.cfg" ]; then
    sudo cp "$SCRIPT_DIR/config.cfg.template" "$INSTALL_DIR/app/config.cfg"
    echo "⚠️ ВНИМАНИЕ: Создан новый config.cfg. Не забудьте вписать туда пароли!"
fi

# 4. Настройка владельца, прав доступа и параметров Git
echo "🔐 Настройка прав доступа и репозитория Git..."
sudo chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR"
sudo chmod -R 750 "$INSTALL_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
    sudo -u "$USER_NAME" git -C "$INSTALL_DIR" config core.fileMode false
fi

# 5. Настройка виртуального окружения Python (без кеша pip для системного пользователя)
echo "🐍 Настройка Python Virtual Environment..."
sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv python3-pip
sudo -u "$USER_NAME" python3 -m venv "$INSTALL_DIR/.venv"
sudo -u "$USER_NAME" "$INSTALL_DIR/.venv/bin/pip" install --no-cache-dir --upgrade pip
sudo -u "$USER_NAME" "$INSTALL_DIR/.venv/bin/pip" install --no-cache-dir -r "$INSTALL_DIR/app/requirements.txt"

# 6. Регистрация systemd службы
echo "⚙️ Установка фоновой службы (Daemon)..."
sudo cp "$SCRIPT_DIR/$SERVICE_NAME" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo "======================================================"
echo "✅ Установка успешно завершена!"
echo "1. Отредактируйте конфиг: sudo nano $INSTALL_DIR/app/config.cfg"
echo "2. Запустите бота:        sudo systemctl start $SERVICE_NAME"
echo "3. Проверьте статус:      sudo systemctl status $SERVICE_NAME"
echo "4. Читайте логи:          journalctl -u $SERVICE_NAME -f"
echo "======================================================"
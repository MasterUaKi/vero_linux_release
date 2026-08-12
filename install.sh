#!/bin/bash
# ==============================================================================
# Installer for VeRO Integration Service (Linux Ubuntu/Debian)
# ==============================================================================

INSTALL_DIR="/opt/vero-integration"
SERVICE_NAME="vero-integration.service"
USER_NAME="vero-bot"

echo "🚀 Начинаем установку VeRO Integration Service..."

# 1. Создание пользователя (без доступа к оболочке, только для запуска бота)
if ! id "$USER_NAME" &>/dev/null; then
    echo "👤 Создание системного пользователя $USER_NAME..."
    sudo useradd -r -s /bin/false $USER_NAME
fi

# 2. Создание директорий
echo "📁 Создание рабочих директорий..."
sudo mkdir -p $INSTALL_DIR/app
sudo mkdir -p $INSTALL_DIR/logs
sudo mkdir -p $INSTALL_DIR/generated_pdf_meldebogen

# 3. Копирование файлов
echo "📄 Копирование исходного кода..."
sudo cp -r app/* $INSTALL_DIR/app/
# Копируем шаблон как реальный конфиг, если его еще нет
if [ ! -f "$INSTALL_DIR/app/config.cfg" ]; then
    sudo cp config.cfg.template $INSTALL_DIR/app/config.cfg
    echo "⚠️ ВНИМАНИЕ: Создан новый config.cfg. Не забудьте вписать туда пароли!"
fi

# Настройка прав
sudo chown -R $USER_NAME:$USER_NAME $INSTALL_DIR
sudo chmod -R 750 $INSTALL_DIR

# 4. Виртуальное окружение
echo "🐍 Настройка Python Virtual Environment..."
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
sudo -u $USER_NAME python3 -m venv $INSTALL_DIR/.venv
sudo -u $USER_NAME $INSTALL_DIR/.venv/bin/pip install --upgrade pip
sudo -u $USER_NAME $INSTALL_DIR/.venv/bin/pip install -r app/requirements.txt

# 5. Регистрация systemd службы
echo "⚙️ Установка фоновой службы (Daemon)..."
sudo cp $SERVICE_NAME /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

echo "======================================================"
echo "✅ Установка успешно завершена!"
echo "1. Отредактируйте конфиг: sudo nano $INSTALL_DIR/app/config.cfg"
echo "2. Запустите бота:        sudo systemctl start $SERVICE_NAME"
echo "3. Проверьте статус:      sudo systemctl status $SERVICE_NAME"
echo "4. Читайте логи:          journalctl -u $SERVICE_NAME -f"
echo "======================================================"
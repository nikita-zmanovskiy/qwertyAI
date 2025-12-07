#!/bin/bash

echo "🚀 Запуск Script Analysis API..."

# Создаем виртуальное окружение если его нет
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python -m venv venv
fi

# Активируем виртуальное окружение
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Устанавливаем зависимости
echo "📥 Установка зависимостей..."
pip install -r requirements.txt
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install huggingface_hub
echo "📥 Установка модели..."
mkdir -p models/phi3_h
huggingface-cli download microsoft/Phi-3-mini-4k-instruct --local-dir models/phi3_h --local-dir-use-symlinks False
# Инициализируем базу данных
echo "🗄️ Инициализация базы данных..."
python recreate_db.py

# Запускаем приложение
echo "🌐 Запуск сервера..."
python main.py
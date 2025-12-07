import re

try:
    import PyPDF2
    from docx import Document
except ImportError:
    print("⚠️  Предупреждение: PyPDF2 или python-docx не установлены. Установите: pip install PyPDF2 python-docx")


def extract_text_from_file(file_path: str, filename: str) -> str:
    """
    Извлекает текст из файлов разных форматов.
    Поддерживает кодировки: UTF-8, UTF-16, CP1251 (Windows-1251), KOI8-R, ISO-8859-5, MacRoman, ASCII.
    """
    try:
        if filename.endswith('.txt'):
            # Для текстовых файлов - пробуем разные кодировки согласно ТЗ
            encodings = ['utf-8', 'utf-16', 'cp1251', 'koi8-r', 'iso-8859-5', 'macroman', 'ascii']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text = f.read()
                        # Проверяем что текст не пустой и содержит разумные символы
                        if text and len(text.strip()) > 0:
                            return text
                except (UnicodeDecodeError, UnicodeError, LookupError):
                    continue
            
            # Если все кодировки не подошли, пробуем с обработкой ошибок
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read()
            except Exception:
                with open(file_path, 'r', encoding='cp1251', errors='replace') as f:
                    return f.read()

        elif filename.endswith('.pdf'):
            # Для PDF файлов
            try:
                text = ""
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                return text
            except NameError:
                return "Ошибка: PyPDF2 не установлен. Установите: pip install PyPDF2"

        elif filename.endswith('.docx'):
            # Для DOCX файлов
            try:
                doc = Document(file_path)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text
            except NameError:
                return "Ошибка: python-docx не установлен. Установите: pip install python-docx"

        else:
            return "Неизвестный формат файла"

    except Exception as e:
        return f"Ошибка при извлечении текста: {str(e)}"


def is_scene_heading(line: str) -> bool:
    """Определяет, является ли строка заголовком сцены сценария"""
    line = line.strip()
    if not line:
        return False

    # Паттерны для заголовков сцен
    patterns = [
        r'^\d+-\d+\.',  # 1-2.
        r'^\d+\.',  # 1.
        r'^[А-ЯЁA-Z\s\-\.]+$',  # Все заглавные с тире и точками
        r'^.*(НАТ\.|ИНТ\.|EXT\.)',  # Содержит НАТ./ИНТ./EXT.
        r'^.*(ДЕНЬ|НОЧЬ|УТРО|ВЕЧЕР)$',  # Заканчивается на время суток
        r'^.*(УЛИЦА|ПОЛЕ|ЛЕС|ДОМ|КОМНАТА|ОФИС)$',  # Заканчивается на локацию
    ]

    # Проверяем все паттерны
    for pattern in patterns:
        if re.search(pattern, line, re.IGNORECASE):
            return True

    # Проверяем, состоит ли строка в основном из заглавных букв (признак заголовка сцены)
    if len(line) > 5 and sum(1 for c in line if c.isupper() or c in ' -.') / len(line) > 0.7:
        return True

    return False


def split_script_into_sentences(text: str) -> list:
    """Разбивает текст сценария на предложения, пропуская заголовки сцен"""
    if not text:
        return []

    # Разбиваем текст на строки
    lines = text.split('\n')
    sentences = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Пропускаем заголовки сцен
        if is_scene_heading(line):
            continue

        # Разбиваем строку на предложения, учитывая разные знаки препинания
        line_sentences = re.split(r'(?<=[.!?])\s+', line)

        for sentence in line_sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 5 and not is_scene_heading(sentence):
                sentences.append(sentence)

    return sentences


def process_script_file(file_path: str, filename: str) -> list:
    """Основная функция: извлекает текст из файла и разбивает на предложения"""
    # Извлекаем текст из файла
    raw_text = extract_text_from_file(file_path, filename)

    # Разбиваем на предложения
    sentences = split_script_into_sentences(raw_text)

    return sentences
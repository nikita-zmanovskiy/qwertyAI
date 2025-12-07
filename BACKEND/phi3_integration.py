"""
Модуль для интеграции с дообученной моделью Phi-3.
Использует реальную модель с LoRA адаптером для анализа сценариев.
"""

import logging
import os
import json
import re
import torch
from typing import List, Dict, Any
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === НАСТРОЙКИ ===
BASE_MODEL_NAME = "microsoft/phi-3-mini-4k-instruct"
LOCAL_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "phi3_h")

# Системный промпт для анализа возрастных рейтингов
SYSTEM_PROMPT = """Ты — анализатор возрастных рейтингов для сценариев. Проанализируй текст и определи возрастной рейтинг по российским стандартам (436-ФЗ).

РУКОВОДСТВО ПО РЕЙТИНГАМ:
0+  - Безопасный контент для всех возрастов
6+  - Мягкие конфликтные ситуации, персонажи в опасности
12+ - Умеренное насилие без крови, легкий испуг
16+ - Алкоголь/табак, явное насилие, сексуальные отсылки
18+ - Жестокость, наркотики, откровенный секс

КАТЕГОРИИ НАРУШЕНИЙ:
- НАСИЛИЕ
- НЕНОРМАТИВНАЯ ЛЕКСИКА  
- СЕКСУАЛЬНЫЙ КОНТЕНТ
- АЛКОГОЛЬ/ТАБАК
- ПУГАЮЩИЙ КОНТЕНТ

Верни ответ ТОЛЬКО в формате JSON:
{"rating": "рейтинг", "why": "объяснение", "label": "категория"}

Текст для анализа:"""


def extract_json(text: str) -> dict:
    """Извлекает JSON из текста ответа модели"""
    try:
        # Ищем JSON объект в тексте
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx == -1 or end_idx == -1:
            return {}

        json_str = text[start_idx:end_idx + 1]
        return json.loads(json_str)
    except:
        return {}


class Phi3Analyzer:
    """Класс для анализа текста с помощью дообученной модели Phi-3."""

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = None
        self.model_path = None
        logger.info("🤖 Инициализация Phi-3 анализатора")

    async def load_model(self):
        """Загружает локальную модель Phi-3 с LoRA адаптером"""
        if self.model is not None:
            logger.info("✅ Модель уже загружена")
            return

        try:
            logger.info("🔄 Начинаю загрузку локальной модели Phi-3...")

            # Проверяем устройство
            if torch.cuda.is_available():
                self.device = "cuda"
                logger.info(f"✅ CUDA доступна: {torch.cuda.get_device_name(0)}")
            else:
                self.device = "cpu"
                logger.warning("⚠️ CUDA недоступна, используется CPU")

            # Настройка квантования для экономии VRAM
            quantization_config = None
            if self.device == "cuda":
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                logger.info("✅ Квантование 4-bit активировано")

            # Проверяем существование путей
            if not os.path.exists(LOCAL_MODEL_DIR):
                raise RuntimeError(f"❌ Локальная база модели не найдена: {LOCAL_MODEL_DIR}")

            logger.info(f"✅ Путь к базовой модели: {LOCAL_MODEL_DIR}")

            # Загружаем токенизатор из локальной модели
            logger.info("📥 Загружаю токенизатор...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                LOCAL_MODEL_DIR,
                trust_remote_code=True
            )
            logger.info("✅ Токенизатор загружен")

            # Загружаем базовую модель локально
            logger.info("📥 Загружаю базовую модель Phi-3...")
            model_kwargs = {
                "trust_remote_code": True,
            }
            if self.device == "cuda":
                model_kwargs["device_map"] = "auto"
                model_kwargs["torch_dtype"] = torch.float16
                model_kwargs["quantization_config"] = quantization_config
            else:
                model_kwargs["torch_dtype"] = torch.float32

            base_model = AutoModelForCausalLM.from_pretrained(
                LOCAL_MODEL_DIR,
                **model_kwargs
            )
            logger.info("✅ Базовая модель загружена")

            # Используем базовую модель (адаптер временно отключен)
            self.model = base_model
            self.model_path = LOCAL_MODEL_DIR
            logger.info("✅ Используется базовая модель")

            # Переводим модель в режим инференса
            self.model.eval()

            # Применяем настройки для стабильности
            if hasattr(self.model.config, 'use_cache'):
                self.model.config.use_cache = False

            logger.info("✅ Модель Phi-3 успешно загружена!")

        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке локальной модели: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Не удалось загрузить модель: {e}")

    def build_prompt(self, message: str) -> str:
        """Строит промпт для модели"""
        return (
            f"<|system|>\n{SYSTEM_PROMPT}<|end|>\n"
            f"<|user|>\n{message}<|end|>\n"
            f"<|assistant|>\n"
        )

    async def analyze_with_system_prompt(self, message: str) -> str:
        """Анализ с системным промптом для определения рейтинга"""
        if self.model is None:
            await self.load_model()

        return await self._analyze_with_system_prompt_real(message)

    async def _analyze_with_system_prompt_real(self, message: str) -> str:
        """Анализ с использованием реальной модели"""
        try:
            # Формируем промпт
            prompt = self.build_prompt(message)

            # Токенизация
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Генерация
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=200,
                    do_sample=False,
                    temperature=0.0,
                    top_p=1.0,
                    repetition_penalty=1.05,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    use_cache=False,
                )

            # Декодирование
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=False)

            # Извлекаем ответ ассистента
            if "<|assistant|>" in generated_text:
                response = generated_text.split("<|assistant|>")[-1].strip()
                response = response.replace("<|end|>", "").strip()
            else:
                response = generated_text.split(prompt)[
                    -1].strip() if prompt in generated_text else generated_text.strip()

            logger.info(f"📄 Ответ модели: {response}")

            # Извлекаем JSON
            parsed = extract_json(response)

            if parsed:
                logger.info(f"✅ Извлеченный JSON: {parsed}")
                return json.dumps(parsed, ensure_ascii=False)
            else:
                # Если JSON не извлекли, создаем базовый ответ
                logger.warning(f"⚠️ Не удалось извлечь JSON из ответа: {response}")
                return json.dumps({
                    "rating": "0+",
                    "why": "Не удалось проанализировать контент",
                    "label": "НЕОПРЕДЕЛЕНО"
                }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"❌ Ошибка при анализе реальной моделью: {e}")
            return json.dumps({
                "rating": "0+",
                "why": f"Ошибка анализа: {str(e)}",
                "label": "ОШИБКА"
            }, ensure_ascii=False)

    async def analyze_sentence(self, sentence: str) -> Dict[str, Any]:
        """Анализирует одно предложение и преобразует в формат БД"""
        try:
            # Получаем анализ от нейросети
            json_result = await self.analyze_with_system_prompt(sentence)
            neural_analysis = json.loads(json_result)

            # Преобразуем в формат для базы данных
            return self._convert_neural_to_db_format(neural_analysis, sentence)

        except Exception as e:
            logger.error(f"❌ Ошибка при анализе предложения: {e}")
            return self._get_default_analysis(sentence)

    def _convert_neural_to_db_format(self, neural_analysis: Dict, sentence: str) -> Dict[str, Any]:
        """Преобразует вывод нейросети в формат базы данных"""
        rating = neural_analysis.get("rating", "0+")
        why = neural_analysis.get("why", "")
        label = neural_analysis.get("label", "").upper()

        # Определяем тип нарушения на основе label
        has_violence = "НАСИЛИЕ" in label
        has_profanity = "ЛЕКСИКА" in label or "НЕНОРМАТИВ" in label
        has_sexual_content = "СЕКС" in label
        has_drugs_alcohol = "АЛКОГОЛЬ" in label or "ТАБАК" in label or "НАРКО" in label
        has_fear_elements = "ПУГАЮЩИЙ" in label or "СТРАХ" in label

        # Определяем уровни на основе рейтинга
        level_map = {
            "0+": 0.0,
            "6+": 0.3,
            "12+": 0.6,
            "16+": 0.8,
            "18+": 0.9
        }

        severity_map = {
            "0+": "None",
            "6+": "Mild",
            "12+": "Moderate",
            "16+": "Severe",
            "18+": "Severe"
        }

        level = level_map.get(rating, 0.0)
        severity = severity_map.get(rating, "None")

        # Устанавливаем уровни только для соответствующих нарушений
        violence_level = level if has_violence else 0.0
        profanity_level = level if has_profanity else 0.0
        sexual_level = level if has_sexual_content else 0.0
        drugs_level = level if has_drugs_alcohol else 0.0
        fear_level = level if has_fear_elements else 0.0

        violence_severity = severity if has_violence else "None"
        profanity_severity = severity if has_profanity else "None"
        sexual_severity = severity if has_sexual_content else "None"
        drugs_severity = severity if has_drugs_alcohol else "None"
        fear_severity = severity if has_fear_elements else "None"

        # Генерируем рекомендации
        recommendations = self._generate_recommendations(
            has_violence, has_profanity, has_sexual_content,
            has_drugs_alcohol, has_fear_elements, rating
        )

        return {
            "has_violence": has_violence,
            "has_profanity": has_profanity,
            "has_sexual_content": has_sexual_content,
            "has_drugs_alcohol": has_drugs_alcohol,
            "has_fear_elements": has_fear_elements,
            "violence_level": violence_level,
            "profanity_level": profanity_level,
            "sexual_content_level": sexual_level,
            "drugs_alcohol_level": drugs_level,
            "fear_level": fear_level,
            "violence_severity": violence_severity,
            "profanity_severity": profanity_severity,
            "sexual_severity": sexual_severity,
            "drugs_severity": drugs_severity,
            "fear_severity": fear_severity,
            "assigned_rating": rating,
            "explanation": why,
            "correction_recommendations": recommendations,
            "is_problematic": rating != "0+",
            "neural_analysis": neural_analysis  # Сохраняем оригинальный анализ
        }

    def _generate_recommendations(self, has_violence: bool, has_profanity: bool,
                                  has_sexual: bool, has_drugs: bool, has_fear: bool,
                                  rating: str) -> List[str]:
        """Генерирует рекомендации по корректировке"""
        recommendations = []

        if rating == "18+":
            recommendations.append("Требуется значительная переработка контента для снижения рейтинга")

        if has_profanity:
            recommendations.append("Замените ненормативную лексику на более мягкие выражения")
        if has_violence and rating in ["16+", "18+"]:
            recommendations.append("Уменьшите интенсивность сцен насилия")
        if has_sexual and rating in ["16+", "18+"]:
            recommendations.append("Сделайте эротические сцены менее откровенными")
        if has_drugs and rating in ["16+", "18+"]:
            recommendations.append("Уберите или смягчите сцены употребления алкоголя/табака")
        if has_fear and rating in ["12+", "16+", "18+"]:
            recommendations.append("Уменьшите интенсивность пугающих элементов")

        if not recommendations:
            recommendations = ["Нарушений не обнаружено, корректировка не требуется"]

        return recommendations

    def _get_default_analysis(self, sentence: str) -> Dict[str, Any]:
        """Возвращает анализ по умолчанию при ошибке"""
        return {
            "has_violence": False,
            "has_profanity": False,
            "has_sexual_content": False,
            "has_drugs_alcohol": False,
            "has_fear_elements": False,
            "violence_level": 0.0,
            "profanity_level": 0.0,
            "sexual_content_level": 0.0,
            "drugs_alcohol_level": 0.0,
            "fear_level": 0.0,
            "violence_severity": "None",
            "profanity_severity": "None",
            "sexual_severity": "None",
            "drugs_severity": "None",
            "fear_severity": "None",
            "assigned_rating": "0+",
            "explanation": "Ошибка анализа контента",
            "correction_recommendations": ["Повторите анализ"],
            "is_problematic": False
        }


# Глобальный экземпляр анализатора
phi3_analyzer = Phi3Analyzer()


async def analyze_all_sentences(sentences: List[str]) -> List[Dict[str, Any]]:
    """Анализирует все предложения с помощью нейросети"""
    logger.info(f"🔍 Анализ {len(sentences)} предложений нейросетью...")

    # Убеждаемся что модель загружена
    if phi3_analyzer.model is None:
        await phi3_analyzer.load_model()

    analyses = []
    for i, sentence in enumerate(sentences):
        if (i + 1) % 5 == 0:  # Логируем каждые 5 предложений
            logger.info(f"📝 Анализ {i + 1}/{len(sentences)}...")

        try:
            analysis = await phi3_analyzer.analyze_sentence(sentence)
            analyses.append(analysis)
        except Exception as e:
            logger.error(f"❌ Ошибка при анализе предложения {i + 1}: {e}")
            # Добавляем анализ по умолчанию при ошибке
            analyses.append(phi3_analyzer._get_default_analysis(sentence))

    logger.info(f"✅ Анализ завершен: {len(analyses)} предложений")
    return analyses


# Функции для совместимости
def calculate_overall_rating(analyses: List[Dict[str, Any]]) -> str:
    """Вычисляет общий рейтинг на основе всех анализов"""
    ratings_order = {"0+": 0, "6+": 1, "12+": 2, "16+": 3, "18+": 4}
    max_rating = "0+"

    for analysis in analyses:
        current_rating = analysis["assigned_rating"]
        if ratings_order.get(current_rating, 0) > ratings_order.get(max_rating, 0):
            max_rating = current_rating

    return max_rating


def generate_overall_summary(analyses: List[Dict[str, Any]]) -> str:
    """Генерирует общее резюме анализа"""
    problematic_count = sum(1 for a in analyses if a["is_problematic"])
    total = len(analyses)
    overall_rating = calculate_overall_rating(analyses)

    if problematic_count == 0:
        return f"✅ Отлично! Все {total} предложений безопасны для всех возрастов (рейтинг 0+)."
    else:
        return f"⚠️ Найдено {problematic_count} проблемных предложений из {total}. Общий рейтинг: {overall_rating}."


def calculate_statistics(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Вычисляет статистику по анализам"""
    total = len(analyses)
    problematic = sum(1 for a in analyses if a["is_problematic"])

    violations = {
        "violence": sum(1 for a in analyses if a["has_violence"]),
        "profanity": sum(1 for a in analyses if a["has_profanity"]),
        "sexual_content": sum(1 for a in analyses if a["has_sexual_content"]),
        "drugs_alcohol": sum(1 for a in analyses if a["has_drugs_alcohol"]),
        "fear_elements": sum(1 for a in analyses if a["has_fear_elements"]),
    }

    return {
        "total_sentences": total,
        "problematic_sentences": problematic,
        "problematic_percentage": round((problematic / total) * 100, 2) if total > 0 else 0,
        "violations": violations
    }
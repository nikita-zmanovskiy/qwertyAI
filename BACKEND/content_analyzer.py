"""
Модуль для анализа контента согласно Федеральному закону № 436-ФЗ.
Определяет возрастные рейтинги и категории нарушений.
"""

import re
from typing import Dict, List, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """
    Анализатор контента для определения возрастных рейтингов по 436-ФЗ.
    """

    def __init__(self):
        # Паттерны для определения различных типов контента
        self.violence_patterns = [
            r'\b(убийств[оау]|убил|убить|убивают)\b',
            r'\b(умер|смерть|погиб)\b',
            r'\b(насили[ея]|изнасилован)\b',
            r'\b(драк[аиу]|побил|избиение)\b',
            r'\b(кровь|кровав)\b',
            r'\b(оружие|пистолет|нож|револьвер)\b',
            r'\b(стрельб[аы]|выстрел)\b',
            r'\b(труп[аы]|мертв)\b'
        ]

        self.profanity_patterns = [
            r'\b(блять|блядь|хуй|пизда|ебал|ебать)\b',
            r'\b(мудак|говно|дерьмо)\b',
            r'\b(сука|тварь|падл[аы])\b'
        ]

        self.sexual_patterns = [
            r'\b(секс|интим|половой)\b',
            r'\b(трах|выебать|отсос)\b',
            r'\b(гол[ыы]й|обнажен)\b',
            r'\b(порно|проститут)\b',
            r'\b(оргазм|конча[тью])\b'
        ]

        self.drugs_alcohol_patterns = [
            r'\b(алкогол[ья]|пьян|выпивк)\b',
            r'\b(водк[аиу]|вино|пиво|коньяк)\b',
            r'\b(наркотик[иов]|героин|кокаин)\b',
            r'\b(курит|сигарет|табак)\b',
            r'\b(закладк[аи]|доз[аы])\b',
            r'\b(ломк[аи]|наркоман)\b'
        ]

        self.fear_patterns = [
            r'\b(ужас|страх|кошмар)\b',
            r'\b(призрак|монстр|демон)\b',
            r'\b(сатанизм|оккультизм)\b',
            r'\b(кладбище|могил)\b',
            r'\b(псих|сумасшедш)\b'
        ]

        # Уровни серьезности для каждой категории
        self.severity_levels = {
            "None": 0,
            "Mild": 1,
            "Moderate": 2,
            "Severe": 3
        }

        # Рейтинги по 436-ФЗ
        self.ratings_order = ["0+", "6+", "12+", "16+", "18+"]

    def analyze_sentence(self, sentence: str) -> Dict[str, Any]:
        """
        Анализирует одно предложение на наличие проблемного контента.

        Args:
            sentence: Текст предложения для анализа

        Returns:
            Словарь с результатами анализа
        """
        sentence_lower = sentence.lower()

        # Анализ насилия
        violence_result = self._analyze_violence(sentence_lower)

        # Анализ ненормативной лексики
        profanity_result = self._analyze_profanity(sentence_lower)

        # Анализ сексуального контента
        sexual_result = self._analyze_sexual_content(sentence_lower)

        # Анализ алкоголя/наркотиков
        drugs_result = self._analyze_drugs_alcohol(sentence_lower)

        # Анализ пугающего контента
        fear_result = self._analyze_fear_elements(sentence_lower)

        # Определение общего рейтинга
        assigned_rating = self._determine_rating([
            violence_result["severity"],
            profanity_result["severity"],
            sexual_result["severity"],
            drugs_result["severity"],
            fear_result["severity"]
        ])

        # Формирование объяснения
        explanation = self._generate_explanation(
            violence_result, profanity_result, sexual_result,
            drugs_result, fear_result, assigned_rating
        )

        # Рекомендации по корректировке
        recommendations = self._generate_recommendations(
            violence_result, profanity_result, sexual_result,
            drugs_result, fear_result, assigned_rating
        )

        return {
            "has_violence": violence_result["present"],
            "has_profanity": profanity_result["present"],
            "has_sexual_content": sexual_result["present"],
            "has_drugs_alcohol": drugs_result["present"],
            "has_fear_elements": fear_result["present"],
            "violence_level": violence_result["level"],
            "profanity_level": profanity_result["level"],
            "sexual_content_level": sexual_result["level"],
            "drugs_alcohol_level": drugs_result["level"],
            "fear_level": fear_result["level"],
            "violence_severity": violence_result["severity"],
            "profanity_severity": profanity_result["severity"],
            "sexual_severity": sexual_result["severity"],
            "drugs_severity": drugs_result["severity"],
            "fear_severity": fear_result["severity"],
            "assigned_rating": assigned_rating,
            "explanation": explanation,
            "correction_recommendations": recommendations,
            "is_problematic": assigned_rating != "0+"
        }

    def _analyze_violence(self, text: str) -> Dict[str, Any]:
        """Анализирует контент на наличие насилия."""
        matches = []
        for pattern in self.violence_patterns:
            if re.search(pattern, text):
                matches.append(pattern)

        if not matches:
            return {"present": False, "level": 0.0, "severity": "None"}

        # Определяем серьезность на основе количества и типа совпадений
        severity = "Mild"
        level = 0.3

        if any(p in str(matches) for p in ["убийств", "смерть", "труп", "кровь"]):
            severity = "Severe"
            level = 0.9
        elif any(p in str(matches) for p in ["насили", "избиение", "оружие"]):
            severity = "Moderate"
            level = 0.6

        return {"present": True, "level": level, "severity": severity}

    def _analyze_profanity(self, text: str) -> Dict[str, Any]:
        """Анализирует контент на наличие ненормативной лексики."""
        matches = []
        for pattern in self.profanity_patterns:
            if re.search(pattern, text):
                matches.append(pattern)

        if not matches:
            return {"present": False, "level": 0.0, "severity": "None"}

        # Матерные слова всегда считаются серьезным нарушением
        return {"present": True, "level": 0.9, "severity": "Severe"}

    def _analyze_sexual_content(self, text: str) -> Dict[str, Any]:
        """Анализирует контент на наличие сексуального контента."""
        matches = []
        for pattern in self.sexual_patterns:
            if re.search(pattern, text):
                matches.append(pattern)

        if not matches:
            return {"present": False, "level": 0.0, "severity": "None"}

        severity = "Mild"
        level = 0.3

        if any(p in str(matches) for p in ["порно", "проститут", "оргазм"]):
            severity = "Severe"
            level = 0.9
        elif any(p in str(matches) for p in ["секс", "трах", "выебать"]):
            severity = "Moderate"
            level = 0.6

        return {"present": True, "level": level, "severity": severity}

    def _analyze_drugs_alcohol(self, text: str) -> Dict[str, Any]:
        """Анализирует контент на наличие алкоголя/наркотиков."""
        matches = []
        for pattern in self.drugs_alcohol_patterns:
            if re.search(pattern, text):
                matches.append(pattern)

        if not matches:
            return {"present": False, "level": 0.0, "severity": "None"}

        severity = "Mild"
        level = 0.3

        if any(p in str(matches) for p in ["наркотик", "героин", "кокаин", "закладк", "ломк"]):
            severity = "Severe"
            level = 0.9
        elif any(p in str(matches) for p in ["алкогол", "пьян", "водк"]):
            severity = "Moderate"
            level = 0.6

        return {"present": True, "level": level, "severity": severity}

    def _analyze_fear_elements(self, text: str) -> Dict[str, Any]:
        """Анализирует контент на наличие пугающих элементов."""
        matches = []
        for pattern in self.fear_patterns:
            if re.search(pattern, text):
                matches.append(pattern)

        if not matches:
            return {"present": False, "level": 0.0, "severity": "None"}

        severity = "Mild"
        level = 0.3

        if any(p in str(matches) for p in ["сатанизм", "оккультизм", "псих"]):
            severity = "Moderate"
            level = 0.6

        return {"present": True, "level": level, "severity": severity}

    def _determine_rating(self, severities: List[str]) -> str:
        """Определяет возрастной рейтинг на основе серьезности нарушений."""
        severity_scores = {
            "None": 0,
            "Mild": 1,
            "Moderate": 2,
            "Severe": 3
        }

        max_severity_score = 0
        for severity in severities:
            max_severity_score = max(max_severity_score, severity_scores.get(severity, 0))

        # Соответствие между серьезностью и рейтингом
        if max_severity_score >= 3:  # Severe
            return "18+"
        elif max_severity_score >= 2:  # Moderate
            return "16+"
        elif max_severity_score >= 1:  # Mild
            return "12+"
        else:  # None
            return "0+"

    def _generate_explanation(self, violence: Dict, profanity: Dict, sexual: Dict,
                              drugs: Dict, fear: Dict, rating: str) -> str:
        """Генерирует объяснение для рейтинга."""
        reasons = []

        if violence["present"]:
            reasons.append(f"насилие ({violence['severity']})")
        if profanity["present"]:
            reasons.append("ненормативная лексика")
        if sexual["present"]:
            reasons.append(f"сексуальный контент ({sexual['severity']})")
        if drugs["present"]:
            reasons.append(f"алкоголь/наркотики ({drugs['severity']})")
        if fear["present"]:
            reasons.append(f"пугающие элементы ({fear['severity']})")

        if not reasons:
            return "Контент безопасен для всех возрастов"

        return f"Рейтинг {rating} установлен из-за: {', '.join(reasons)}"

    def _generate_recommendations(self, violence: Dict, profanity: Dict, sexual: Dict,
                                  drugs: Dict, fear: Dict, rating: str) -> List[str]:
        """Генерирует рекомендации по корректировке."""
        recommendations = []

        if rating == "18+":
            recommendations.append("Рекомендуется значительная переработка контента")

        if violence["present"] and violence["severity"] in ["Moderate", "Severe"]:
            recommendations.append("Уменьшите интенсивность сцен насилия")

        if profanity["present"]:
            recommendations.append("Замените ненормативную лексику")

        if sexual["present"] and sexual["severity"] in ["Moderate", "Severe"]:
            recommendations.append("Сделайте эротические сцены менее откровенными")

        if drugs["present"] and drugs["severity"] in ["Moderate", "Severe"]:
            recommendations.append("Уберите или смягчите сцены употребления")

        if fear["present"] and fear["severity"] == "Moderate":
            recommendations.append("Уменьшите интенсивность пугающих элементов")

        if not recommendations:
            recommendations.append("Корректировка не требуется")

        return recommendations


# Глобальный экземпляр анализатора
content_analyzer = ContentAnalyzer()
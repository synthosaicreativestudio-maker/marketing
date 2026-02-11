"""
Классификатор сложности запросов.

Реализует каскадную систему обработки:
- SIMPLE: Приветствия, благодарности → короткий ответ
- MEDIUM: Технические вопросы → промпт + RAG
- COMPLEX: Аналитика, персонализация → промпт + RAG + память
"""
import re
from enum import Enum
from typing import Tuple


class QueryComplexity(Enum):
    """Уровни сложности запросов."""
    SIMPLE = 1    # Приветствия, благодарности
    MEDIUM = 2    # Технические вопросы
    COMPLEX = 3   # Аналитика, персонализация


# Паттерны для простых запросов (SIMPLE)
SIMPLE_PATTERNS = [
    # Приветствия
    r'^(привет|здравствуй|здравствуйте|добрый день|добрый вечер|доброе утро|хай|ку|здорово|приветик|хеллоу|hello|hi)[\s!\.]*$',
    # Благодарности
    r'^(спасибо|благодарю|пасиб|спс|благодарность|thanks|thx)[\s!\.]*$',
    # Прощания
    r'^(пока|до свидания|увидимся|удачи|всего доброго|bye)[\s!\.]*$',
    # Подтверждения
    r'^(да|нет|ок|окей|хорошо|понял|понятно|ясно|угу|ага|неа)[\s!\.]*$',
    # Короткие вопросы о состоянии
    r'^(как дела|что нового|как ты)[\s\?!\.]*$',
]

# Маркеры сложных запросов (COMPLEX)
COMPLEX_MARKERS = [
    # Аналитика
    'проанализируй', 'аналитика', 'анализ', 'сравни', 'оцени',
    'статистика', 'метрики', 'показатели', 'эффективность',
    # Временные периоды (указывают на работу с историей)
    'за месяц', 'за неделю', 'за год', 'за период',
    'за последние', 'история', 'динамика',
    # Память/контекст
    'раньше', 'прошлый раз', 'мы обсуждали', 'помнишь',
    'как в прошлый', 'напомни', 'ранее',
    # Стратегия/планирование
    'стратегия', 'план', 'рекомендации по моей',
    'индивидуальный', 'персональный', 'для меня',
    # ROI/бизнес-метрики
    'roi', 'рентабельность', 'окупаемость', 'конверсия',
]

# Маркеры средних запросов (для явной классификации)
MEDIUM_MARKERS = [
    # Технические вопросы
    'как', 'где', 'почему', 'что делать',
    'не работает', 'ошибка', 'проблема',
    # CRM/площадки
    'космос', 'авито', 'циан', 'домклик',
    'выгрузка', 'модерация', 'объявление',
    # Инструкции
    'инструкция', 'как сделать', 'подскажи',
]


def classify_query(text: str) -> Tuple[QueryComplexity, str]:
    """
    Классифицирует запрос по сложности.
    
    Args:
        text: Текст запроса пользователя
        
    Returns:
        Tuple[QueryComplexity, str]: (уровень сложности, причина классификации)
    """
    text_lower = text.lower().strip()
    
    # Уровень 1: Простые запросы (приветствия, подтверждения)
    for pattern in SIMPLE_PATTERNS:
        if re.match(pattern, text_lower, re.IGNORECASE):
            return QueryComplexity.SIMPLE, "greeting_or_acknowledgment"
    
    # Короткие сообщения без вопросительных слов — тоже простые
    if len(text_lower) < 15 and '?' not in text_lower:
        # Проверяем, нет ли маркеров сложных запросов
        has_complex = any(m in text_lower for m in COMPLEX_MARKERS)
        has_medium = any(m in text_lower for m in MEDIUM_MARKERS)
        if not has_complex and not has_medium:
            return QueryComplexity.SIMPLE, "short_message"
    
    # Уровень 3: Сложные запросы (аналитика, персонализация)
    for marker in COMPLEX_MARKERS:
        if marker in text_lower:
            return QueryComplexity.COMPLEX, f"complex_marker:{marker}"
    
    # Уровень 2: Средние запросы (технические вопросы) — по умолчанию
    return QueryComplexity.MEDIUM, "default_technical"


def get_max_tokens_for_complexity(complexity: QueryComplexity) -> int:
    """
    Возвращает рекомендуемое ограничение токенов для ответа.
    
    Args:
        complexity: Уровень сложности запроса
        
    Returns:
        int: Максимальное количество токенов
    """
    limits = {
        QueryComplexity.SIMPLE: 150,   # Короткий ответ
        QueryComplexity.MEDIUM: 1000,  # Стандартная инструкция
        QueryComplexity.COMPLEX: 2000, # Полный анализ
    }
    return limits.get(complexity, 1000)


def should_use_rag(complexity: QueryComplexity) -> bool:
    """Нужно ли использовать RAG для данного уровня сложности."""
    return complexity in (QueryComplexity.MEDIUM, QueryComplexity.COMPLEX)


def should_use_memory(complexity: QueryComplexity) -> bool:
    """Нужно ли использовать контекстную память."""
    return complexity == QueryComplexity.COMPLEX

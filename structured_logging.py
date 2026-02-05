"""
Structured Logging — JSON-формат логов с метриками.

Преимущества:
- Легко анализировать программами (grep, jq)
- Единый формат для всех модулей
- Включает время, user_id, action, duration

Overhead: 0.1-0.5 мс на лог, +50% размер файлов.
"""

import logging
import json
import time
from typing import Optional
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Форматтер для вывода логов в JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Добавляем extra-поля если есть
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "action"):
            log_data["action"] = record.action
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "tokens"):
            log_data["tokens"] = record.tokens
        if hasattr(record, "model"):
            log_data["model"] = record.model
        
        # Добавляем информацию об ошибке если есть
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_json_logging(level: int = logging.INFO) -> None:
    """
    Настраивает JSON-логирование для всего приложения.
    
    Вызывать один раз при старте бота.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Удаляем старые обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Добавляем JSON-handler для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)


class LLMMetricsLogger:
    """
    Логгер для метрик LLM (время ответа, токены).
    
    Использование:
        with LLMMetricsLogger(user_id=123, model="gemini-3") as metrics:
            # ... запрос к LLM ...
            metrics.set_tokens(input=100, output=50)
    """
    
    def __init__(self, user_id: int, model: str, action: str = "llm_request"):
        self.user_id = user_id
        self.model = model
        self.action = action
        self.start_time: float = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.logger = logging.getLogger("llm_metrics")
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def set_tokens(self, input_tokens: int = 0, output_tokens: int = 0):
        """Устанавливает количество токенов."""
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        extra = {
            "user_id": self.user_id,
            "model": self.model,
            "action": self.action,
            "duration_ms": round(duration_ms, 2),
        }
        
        if self.input_tokens or self.output_tokens:
            extra["tokens"] = {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "total": self.input_tokens + self.output_tokens
            }
        
        if exc_type:
            self.logger.error(
                f"LLM request failed after {duration_ms:.0f}ms",
                extra=extra,
                exc_info=(exc_type, exc_val, exc_tb)
            )
        else:
            self.logger.info(
                f"LLM response in {duration_ms:.0f}ms (model: {self.model})",
                extra=extra
            )
        
        return False  # Не подавляем исключения


def log_llm_metrics(
    user_id: int,
    model: str,
    duration_ms: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    success: bool = True,
    error: Optional[str] = None
) -> None:
    """
    Простая функция для логирования метрик LLM.
    
    Использование:
        start = time.perf_counter()
        # ... запрос к LLM ...
        log_llm_metrics(user_id, model, (time.perf_counter() - start) * 1000)
    """
    logger = logging.getLogger("llm_metrics")
    
    log_data = {
        "user_id": user_id,
        "model": model,
        "action": "llm_request",
        "duration_ms": round(duration_ms, 2),
    }
    
    if input_tokens or output_tokens:
        log_data["tokens"] = {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens
        }
    
    if success:
        logger.info(f"LLM response: {model} in {duration_ms:.0f}ms", extra=log_data)
    else:
        log_data["error"] = error or "unknown"
        logger.error(f"LLM failed: {model} after {duration_ms:.0f}ms - {error}", extra=log_data)

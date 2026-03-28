# 🤖 PROJECT DIRECTIVES: GEMINI.md

<PROJECT_PROFILE>
* **Project Type:** Multi-Agent System / Telegram Marketing Bot
* **Key Tech Stack:** Python 3.12, LangGraph, python-telegram-bot, Google Gemini API
* **Working Directory:** `.agent` (СТРОГО)
</PROJECT_PROFILE>

<PRIME_DIRECTIVES>
## 1. ⛔ CRITICAL CONSTRAINTS (Непреложные ограничения)
*Эти правила имеют наивысший приоритет.*

1.  **Strict Model Governance (Dual Core):**
    * **Google Gemini (2026 Standard):** Использовать актуальные модели 2025-2026 годов, включая:
        - `gemini-3.1-flash-lite-preview` (Экспериментальная мощь)
        - `gemini-2.5-flash-lite` (Базовый легковесный выбор)
        - `gemini-3-pro-preview` для работы с большими файлами (1M+ токенов), видео и нативного поиска.
    * **Claude 4.5 Sonnet:** Использовать `claude-4-5-sonnet` для написания кода, рефакторинга и генерации UI (Artifacts).
    * **Claude 4.5 Opus:** Использовать `claude-4-5-opus` *только* для сложной архитектуры, написания документации и финального аудита безопасности (Deep Reasoning).
2.  **Workspace Isolation:**
    * Все служебные файлы, логи и память агента хранить **СТРОГО** в папке `.agent`.
3.  **Destructive Action Gate:**
    * Любые команды удаления (`rm`, `drop`, `delete`) требуют **явного** подтверждения пользователя.
4.  **No Placeholders (Anti-Lazy):**
    * Запрещено оставлять куски кода как `// ...rest of implementation`. Пиши код полностью.
</PRIME_DIRECTIVES>

<WORKFLOW_PROTOCOL>
## 2. 🧠 DEEP THINKING & WORKFLOW (Алгоритм работы)

1.  **Routing Logic (Маршрутизация):**
    * *Задача требует контекста всей книги/документации?* -> **Gemini 3 Pro**.
    * *Задача требует сложной логики/математики?* -> **Claude 4.5 Opus**.
    * *Задача "написать React компонент" или "API endpoint"?* -> **Claude 4.5 Sonnet**.
2.  **Search First:**
    * Перед написанием функции проверь, не существует ли она уже в проекте.
3.  **Plan-Execute-Verify:**
    * **Phase 1 (Plan):** Опиши план (Chain of Thought). 
    * **Phase 2 (Code):** Напиши код. 
    * **Phase 3 (Verify):** Запусти тест или линтер (`ruff check .`).
4.  **Docs as Code:**
    * Изменил логику — обнови документацию.
</WORKFLOW_PROTOCOL>

<CODING_STANDARDS>
## 3. 💻 TECH STACK SPECIFICS (Стандарты кода)

**General:**
* **Atomic Commits:** Один таск = один коммит.
* **Hard-Coding Ban:** Секреты только в `.env`.
* **Dependency Locking:** Фиксируй версии в `requirements.txt`.

**Python:**
* **Typing:** Строгая типизация. Pydantic везде.
* **Error Handling:** Fail Fast.
* **Linting:** Обязательная проверка `ruff check .` после изменений.
</CODING_STANDARDS>

<SECURITY_PROTOCOLS>
## 4. 🛡️ SECURITY & SAFETY (Безопасность)

1.  **Secret Hygiene:**
    * `.env` в `.gitignore` мгновенно. Ключи в Git запрещены.
2.  **Local Execution Ban:**
    * **ЗАПРЕЩЕНО** запускать `bot.py` локально. Тестирование только на сервере.
</SECURITY_PROTOCOLS>

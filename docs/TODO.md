# TODO: Technical Improvements & Debt

## 🔴 High Priority (Reliability)
- [ ] **Implement "Graceful Degradation" for initialization.**  
  *Current behavior:* Bot crashes if OpenAI or Sheets are unreachable at startup.  
  *Desired behavior:* Bot starts in "Safe Mode" (e.g., only basic commands work), logs the error, and retries background connection.
- [ ] **Implement Feature Flags (The "Switchboard").**  
  Add to `.env`: `ENABLE_AI=true/false`, `ENABLE_PROMOTIONS=true/false`.  
  Allow disabling modules without code changes.

## 🟡 Medium Priority (Optimization)
- [ ] **Background Task Isolation.**  
  Move heavy tasks (like mass notifications) to a separate process/worker (e.g., using `Celery` or just a separate daemon script) so they don't block the main chat bot.
- [ ] **Structured Logging.**  
  Switch from plain text logs to JSON logs for better analysis (especially if integrating with external monitoring tools later).

- [ ] **Unit Tests.**  
   Write tests for `AuthService` logic to prevent regression during updates.

## 🔵 Future: RAG System Redesign (Ideas)
- [ ] **Switch to `bm25s` library.** 
  Current `rank_bm25` and `sklearn` are too heavy for the VM. `bm25s` offers similar accuracy with much lower memory footprint.
- [ ] **Context Selection Optimization.**
  Reduce `top_k` from 10 to 3-5 to prevent "information noise" and focus the AI on the most relevant data.
- [ ] **Smart Prompting for Context.**
  Add explicit instructions to the system prompt to ignore retrieved context if it doesn't directly answer the user's question.
- [ ] **Lightweight Lemmatization.**
  Use `razdel` for tokenization and apply `pymorphy2` only where strictly necessary to save RAM.
- [ ] **Context-Aware RAG Activation.**
  Only trigger RAG for specific query types (technical, analytics) via the `query_classifier.py`.

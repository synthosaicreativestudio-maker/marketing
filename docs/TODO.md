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

## 🟢 Low Priority (Cleanup)
- [ ] **Type Hinting Coverage.**  
  Ensure 100% type coverage with `mypy` for better code stability.
- [ ] **Unit Tests.**  
  Write tests for `AuthService` logic to prevent regression during updates.

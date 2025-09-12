## Implementation status

This file summarizes the current implementation status of core components in the repository.

- bot.py
  - Purpose: Telegram bot main entry. Registers handlers, receives web_app_data and forwards it to sheet service.
  - Status: Implemented and functional. Uses `python-telegram-bot` conventions.

- handlers/start_handler.py
  - Purpose: `/start` handler. Sends a Web App button to the user.
  - Status: Implemented and used by the bot.

- google_sheets_service.py
  - Purpose: Integrate with Google Sheets to store partner/authorization data.
  - Status: Placeholder implementation. Methods `find_and_update_user` and `get_user_auth_status` return demo/stubbed values. Needs real service account credentials and API calls.

- Mini App (`docs/index.html`)
  - Purpose: Web App for collecting partner phone, name and authorization data.
  - Status: Implemented. Sends data to the bot via `Telegram.WebApp.sendData`.

- Scheduler
  - Purpose: periodic tasks (send reminders, check auth status).
  - Status: Not present. There's an environment variable `EKATERINBURG_TIMEZONE` and doc references, but no `scheduler_service.py` or equivalent.

- Testing
  - Purpose: automated tests for bot logic.
  - Status: None found. Add unit tests for handlers and the Google Sheets service.

- CI / Deployment
  - Purpose: deploy Mini App to GitHub Pages.
  - Status: Workflow `deploy.yml` present and configured to use `actions/deploy-pages@v3`. See `docs/DEPLOYMENT.md` for details on failures and required steps.

#!/usr/bin/env python3
"""
Создание листа "Очередь" в таблице аналитики.
Лист используется для очереди запросов аналитики от Telegram-бота.
"""

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1Xq6bcxaDV2AEVWGqhaLlFcr6-hTNv0L5frXgPY-z7fU"
SA_KEY_PATH = "/Users/verakoroleva/Desktop/доработка маркетинг 2/аналитика/estateanalyticsbot-bfb509c50754.json"
SHEET_NAME = "Очередь"

HEADERS = [
    "id",
    "created_at",
    "object_code",
    "chat_id",
    "user",
    "status",
    "started_at",
    "finished_at",
    "tries",
    "error",
    "result_text",
    "eta_sec",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def main():
    print(f"🔗 Подключение к таблице {SPREADSHEET_ID}...")
    creds = Credentials.from_service_account_file(SA_KEY_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)

    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    print(f"✅ Таблица: {spreadsheet.title}")

    # Проверяем, существует ли лист
    existing = [ws.title for ws in spreadsheet.worksheets()]
    print(f"📋 Существующие листы: {existing}")

    if SHEET_NAME in existing:
        print(f"⚠️  Лист '{SHEET_NAME}' уже существует. Пропускаем создание.")
        return

    # Создаём лист
    worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
    print(f"✅ Лист '{SHEET_NAME}' создан ({len(HEADERS)} столбцов, 1000 строк)")

    # Записываем заголовки
    worksheet.update("A1", [HEADERS])
    print(f"✅ Заголовки записаны: {HEADERS}")

    # Форматирование заголовков (жирный шрифт, заливка)
    worksheet.format("A1:L1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.95},
        "horizontalAlignment": "CENTER",
    })
    print("✅ Форматирование применено")

    # Ширина столбцов
    col_widths = {
        "A": 80,   # id
        "B": 160,  # created_at
        "C": 120,  # object_code
        "D": 120,  # chat_id
        "E": 150,  # user
        "F": 100,  # status
        "G": 160,  # started_at
        "H": 160,  # finished_at
        "I": 60,   # tries
        "J": 200,  # error
        "K": 400,  # result_text
        "L": 80,   # eta_sec
    }
    requests = []
    for col_letter, width in col_widths.items():
        col_index = ord(col_letter) - ord("A")
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": worksheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": col_index,
                    "endIndex": col_index + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })
    spreadsheet.batch_update({"requests": requests})
    print("✅ Ширина столбцов настроена")

    print(f"\n🎉 Готово! Лист '{SHEET_NAME}' создан в таблице '{spreadsheet.title}'")


if __name__ == "__main__":
    main()

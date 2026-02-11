#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from collections import Counter
from typing import Dict, List, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build


DEFAULT_SPREADSHEET_ID = "1Xq6bcxaDV2AEVWGqhaLlFcr6-hTNv0L5frXgPY-z7fU"
DEFAULT_EXCLUDES = ["Лист4", "3. 2. активные в группе"]


EXPECTED_HEADERS = {
    # Sources
    "2. 2. активные": [
        "Дата вывода заявки в активные",
        "Район",
        "Тип объекта",
        "Кол-во комнат",
        "Площадь",
        "Код объекта",
        "Тип ремонта",
        "Цена",
        "Этаж",
        "Кол-во этажей",
        "Год постройки",
        "Ссылка на объект",
    ],
    "1. 2. проданные": [
        "Дата закрытия заявки",
        "Район",
        "Тип объекта",
        "Кол-во комнат",
        "Площадь",
        "Код объекта",
        "Тип ремонта",
        "Цена",
        "Этаж",
        "Кол-во этажей",
        "Год постройки",
        "Ссылка на объект",
        "Дата публикации",
    ],
    "3. 56. авито": [
        "Код объекта",
        "авито",
        "дата",
    ],
    "5. 56. циан": [
        "Код объекта",
        "циан",
        "дата",
    ],
    "6. 56. домклик": [
        "Код объекта",
        "домклик",
        "дата",
    ],
    # Outputs / analytics
    "аналитика ОН по коду": [
        "код объекта",
    ],
    "лист анализа объекта": [
        "Дата вывода заявки в активные",
        "Район",
        "Тип объекта",
        "Кол-во комнат",
        "Площадь",
        "Ссылка на объект",
        "Тип ремонта",
        "Цена",
        "Этаж",
        "Кол-во этажей",
        "Год постройки",
    ],
    "конкуренты активные и проданные для анализа": [
        "Код объекта",
        "Район",
        "Тип объекта",
        "Кол-во комнат",
        "Площадь",
        "Цена",
        "Цена за м²",
        "Срок продажи, дней",
        "Ссылка",
        "Ремонт",
        "Состояние дома",
        "Этаж/Этажность",
        "Год постройки",
    ],
    "критерии для сравнения конкурентов": [
        "КРИТЕРИИ ДЛЯ ПОИСКА КОНКУРЕНТОВ",
        "ПАРАМЕТРЫ ОБЪЕКТА",
        "КРИТЕРИИ ФИЛЬТРАЦИИ",
        "РАСЧЕТНЫЕ КРИТЕРИИ",
        "ДАТА АНАЛИЗА",
    ],
    # Optional
    "7. 92. просмотры на площадках": [
        "Площадка (групп.)",
        "Авито",
        "Циан",
        "Этажи",
        "Яндекс",
        "Итого",
    ],
}


def build_service(key_path: str):
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)
    return build("sheets", "v4", credentials=creds)


def get_sheet_titles(service, spreadsheet_id: str) -> List[Dict]:
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title,gridProperties))")
        .execute()
    )
    return [s["properties"] for s in meta.get("sheets", [])]


def fetch_preview(service, spreadsheet_id: str, title: str, max_cols: int = 52, max_rows: int = 10):
    # A1:AZ10
    end_col = chr(ord("A") + max_cols - 1)
    rng = f"'{title}'!A1:{end_col}{max_rows}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=rng, majorDimension="ROWS")
        .execute()
    )
    return result.get("values", [])


def detect_header_row(rows: List[List[str]]) -> Tuple[int, List[str]]:
    if not rows:
        return -1, []
    best_idx = -1
    best_count = 0
    for i, row in enumerate(rows):
        count = sum(1 for v in row if str(v).strip() != "")
        if count > best_count:
            best_count = count
            best_idx = i
    if best_idx == -1:
        return -1, []
    header = [str(v).strip() for v in rows[best_idx]]
    return best_idx + 1, header


def normalize(name: str) -> str:
    return " ".join(name.lower().split())


def match_expected(sheet_title: str, header: List[str]) -> List[str]:
    expected = EXPECTED_HEADERS.get(sheet_title)
    if not expected:
        return []
    header_norm = {normalize(h) for h in header if h}
    missing = []
    for exp in expected:
        if normalize(exp) not in header_norm:
            missing.append(exp)
    return missing


def analyze_header(header: List[str]) -> Dict:
    trimmed = [h.strip() for h in header if h is not None]
    empty = [i + 1 for i, h in enumerate(trimmed) if h == ""]
    counts = Counter(h for h in trimmed if h != "")
    duplicates = [h for h, c in counts.items() if c > 1]
    return {"empty_positions": empty, "duplicates": duplicates, "count": len(trimmed)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", default=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    parser.add_argument("--spreadsheet", default=DEFAULT_SPREADSHEET_ID)
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    if not args.key:
        raise SystemExit("Укажите путь к сервисному ключу через --key или GOOGLE_APPLICATION_CREDENTIALS")

    excludes = set(DEFAULT_EXCLUDES + (args.exclude or []))
    service = build_service(args.key)

    sheets = get_sheet_titles(service, args.spreadsheet)
    print(f"Spreadsheet: {args.spreadsheet}")
    print(f"Excluded sheets: {', '.join(sorted(excludes))}")
    print("")

    for props in sheets:
        title = props["title"]
        if title in excludes:
            print(f"[SKIP] {title}")
            continue

        rows = fetch_preview(service, args.spreadsheet, title)
        header_row_idx, header = detect_header_row(rows)

        print(f"[SHEET] {title}")
        print(f"- Header row: {header_row_idx if header_row_idx > 0 else 'not found'}")
        print(f"- Header columns: {len(header)}")

        hdr_info = analyze_header(header)
        if hdr_info["empty_positions"]:
            print(f"- Empty header cells at positions: {hdr_info['empty_positions']}")
        if hdr_info["duplicates"]:
            print(f"- Duplicate header names: {hdr_info['duplicates']}")

        missing = match_expected(title, header)
        if missing:
            print(f"- Missing expected headers: {missing}")
        elif title in EXPECTED_HEADERS:
            print("- Expected headers: OK")

        # Basic sample checks for data presence
        if header_row_idx > 0:
            data_rows = rows[header_row_idx:header_row_idx + 3]
            non_empty_rows = sum(1 for r in data_rows if any(str(v).strip() for v in r))
            print(f"- Sample data rows (next 3): {non_empty_rows} non-empty")

        print("")


if __name__ == "__main__":
    main()

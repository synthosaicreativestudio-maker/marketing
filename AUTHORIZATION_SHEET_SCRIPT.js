/**
 * УМНАЯ СИНХРОНИЗАЦИЯ (v2.1 - ПО СКРИНШОТАМ)
 * Исправлено: "Телефон сотрудника", точные имена листов и защита от #ERROR!
 */

const SHEET_AUTH = "список сотрудников для авторизации";
const SOURCE_AUTH = "1. 3. список сотрудников для авто";
const AUTH_HEADERS = ["Код партнера", "ФИО партнера", "Телефон партнера", "Статус авторизации", "Telegram ID", "Дата авторизации"];

function onOpen() {
    SpreadsheetApp.getUi()
        .createMenu('👥 Управление доступом')
        .addItem('🔄 Синхронизировать сотрудников', 'syncEmployeeList')
        .addItem('⚙️ Настроить заголовки', 'setupAuthorizationSheet')
        .addToUi();
}

function syncEmployeeList() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const srcSheet = ss.getSheetByName(SOURCE_AUTH);
    const dstSheet = ss.getSheetByName(SHEET_AUTH);

    if (!srcSheet || !dstSheet) {
        SpreadsheetApp.getUi().alert("Ошибка: Лист не найден. Проверьте названия внизу таблицы.");
        return;
    }

    // ШАГ 1: Поиск колонок (учитываем любые вариации)
    const sHeaders = srcSheet.getRange(1, 1, 3, srcSheet.getLastColumn()).getValues();
    function findCol(names) {
        for (let name of names) {
            let search = name.toLowerCase().trim();
            for (let r = 0; r < sHeaders.length; r++) {
                for (let c = 0; c < sHeaders[r].length; c++) {
                    let header = String(sHeaders[r][c]).toLowerCase();
                    if (header.indexOf(search) !== -1) return c;
                }
            }
        }
        return -1;
    }

    const sIdx = {
        code: findCol(["код партнера", "код из системы"]),
        name: findCol(["фио партнера", "фио сотрудника", "фио"]),
        phone: findCol(["телефон сотруд", "телефон партнера", "телефон"])
    };

    const dHeaders = dstSheet.getRange(1, 1, 1, dstSheet.getLastColumn()).getValues()[0];
    const dIdx = {
        code: dHeaders.indexOf("Код партнера"),
        name: dHeaders.indexOf("ФИО партнера"),
        phone: dHeaders.indexOf("Телефон партнера"),
        status: dHeaders.indexOf("Статус авторизации"),
        tgId: dHeaders.indexOf("Telegram ID"),
        date: dHeaders.indexOf("Дата авторизации")
    };

    // Читаем данные. Данные в источнике начинаются с 3-й строки
    const srcData = srcSheet.getRange(3, 1, Math.max(1, srcSheet.getLastRow() - 2), srcSheet.getLastColumn()).getValues();
    const dstLast = dstSheet.getLastRow();
    const dstData = dstLast >= 2 ? dstSheet.getRange(2, 1, dstLast - 1, dHeaders.length).getValues() : [];

    const existingRows = {};
    dstData.forEach(row => {
        let code = String(row[dIdx.code]).trim();
        if (code) existingRows[code] = row;
    });

    const finalRows = [];
    srcData.forEach(row => {
        let code = String(row[sIdx.code]).trim();
        if (!code || code.toLowerCase() === "итого" || code.indexOf("Дата") !== -1) return;

        let oldRow = existingRows[code];
        let newRow = new Array(dHeaders.length).fill("");

        newRow[dIdx.code] = code;
        newRow[dIdx.name] = sIdx.name !== -1 ? row[sIdx.name] : (oldRow ? oldRow[dIdx.name] : "");

        // Чистим телефон от #ERROR! и лишних знаков
        let rawPhone = sIdx.phone !== -1 ? row[sIdx.phone] : "";
        let phoneFromSrc = cleanPhone(rawPhone);
        newRow[dIdx.phone] = phoneFromSrc || (oldRow ? oldRow[dIdx.phone] : "");

        if (oldRow) {
            newRow[dIdx.status] = oldRow[dIdx.status] || "не авторизован";
            newRow[dIdx.tgId] = oldRow[dIdx.tgId] || "";
            newRow[dIdx.date] = oldRow[dIdx.date] || "";
        } else {
            newRow[dIdx.status] = "не авторизован";
        }
        finalRows.push(newRow);
    });

    if (dstLast >= 2) dstSheet.getRange(2, 1, dstLast - 1, dHeaders.length).clearContent();
    if (finalRows.length > 0) {
        dstSheet.getRange(2, 1, finalRows.length, finalRows[0].length).setValues(finalRows);
    }

    applyAuthFormatting(dstSheet, dIdx.status, finalRows.length);
    SpreadsheetApp.getUi().alert("✅ Успешно! Синхронизировано " + finalRows.length + " чел. Проверьте колонку 'Телефон партнера'.");
}

function cleanPhone(phone) {
    if (!phone || String(phone).indexOf("#") !== -1) return ""; // Игнорируем ошибки #ERROR!
    let d = String(phone).replace(/\D/g, "");
    if (d.length === 10) return "8" + d;
    if (d.length === 11 && d.startsWith("7")) return "8" + d.substring(1);
    return d;
}

function applyAuthFormatting(sheet, statusIdx, rows) {
    if (rows <= 0) return;
    const range = sheet.getRange(2, statusIdx + 1, rows, 1);
    sheet.clearConditionalFormatRules();
    const rules = [
        SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo("authorized").setBackground("#d9ead3").setRanges([range]).build(),
        SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo("авторизован").setBackground("#d9ead3").setRanges([range]).build(),
        SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo("не авторизован").setBackground("#f4cccc").setRanges([range]).build()
    ];
    sheet.setConditionalFormatRules(rules);
    for (let i = 1; i <= sheet.getLastColumn(); i++) sheet.autoResizeColumn(i);
}

function setupAuthorizationSheet() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(SHEET_AUTH) || ss.insertSheet(SHEET_AUTH);
    sheet.getRange(1, 1, 1, AUTH_HEADERS.length).setValues([AUTH_HEADERS]).setFontWeight("bold");
    sheet.setFrozenRows(1);
}

from unittest.mock import MagicMock, patch


def make_fake_sheet(rows):
    ws = MagicMock()
    ws.get_all_values.return_value = rows
    def update_cell(r, c, v):
        # emulate update_cell by modifying rows
        idx = r - 1
        while idx >= len(rows):
            rows.append([''] * 6)
        row = rows[idx]
        while len(row) < 6:
            row.append('')
        row[c-1] = v
        rows[idx] = row
    ws.update_cell.side_effect = update_cell
    return ws


@patch('app.sheets._get_client_and_sheet')
@patch('app.bot_helper._send_sync')
def test_auth_updates_sheet(mock_send_sync, mock_get_ws):
    # prepare fake sheet with header + one row
    rows = [
        ['partner_code','name','phone','status','telegram_id','auth_date'],
        ['111098','Test','89827701055','','','']
    ]
    ws = make_fake_sheet(rows)
    mock_get_ws.return_value = ws
    mock_send_sync.return_value = True

    # call find_row and update
    from app.sheets import (
        find_row_by_partner_and_phone,
        normalize_phone,
        update_row_with_auth,
    )
    row = find_row_by_partner_and_phone('111098', normalize_phone('89827701055'))
    assert row == 2
    update_row_with_auth(row, 12345, status='authorized')
    assert rows[1][3] == 'authorized'
    assert rows[1][4] == '12345'

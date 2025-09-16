import os

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_REAL_INTEGRATION') != '1',
    reason='Real integration disabled'
)


def test_real_sheet_update():
    # This test will make real calls — enable only when you're ready.
    resp = requests.post('http://127.0.0.1:8080/api/webapp/auth', json={
        'initData': 'ok', 'partner_code': '111098', 'partner_phone': '89827701055'
    }, timeout=10)
    pytest.assume(resp.status_code == 200)

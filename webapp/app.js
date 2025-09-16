document.addEventListener('DOMContentLoaded', function () {
  const authBtn = document.getElementById('authBtn')
  const msg = document.getElementById('msg')

  function setMessage(text, isError) {
    msg.textContent = text
    msg.style.color = isError ? 'crimson' : 'green'
  }

  async function doAuth() {
    const codeEl = document.getElementById('partner_code')
    const phoneEl = document.getElementById('partner_phone')
    const code = codeEl.value.trim()
    const phone = phoneEl.value.trim()

    if (!/^[0-9]{1,20}$/.test(code)) {
      setMessage('Код партнёра должен содержать только цифры (1-20)', true)
      return
    }
    if (!phone) {
      setMessage('Введите телефон', true)
      return
    }

    // initData from Telegram Web App (when opened inside Telegram). If not present, still allow for local testing.
    const initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || ''

    authBtn.disabled = true
    setMessage('Проверяю...', false)

    try {
  const resp = await fetch('/api/webapp/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initData, partner_code: code, partner_phone: phone })
      })

      const body = await resp.json().catch(() => null)
      if (resp.ok && body && body.ok !== false) {
        setMessage(body.message || 'Авторизация успешна', false)
      } else {
        const err = body || { error: 'unknown', message: 'Неизвестная ошибка' }
        setMessage((err.message || err.error || 'Ошибка') , true)
      }
    } catch (e) {
      setMessage('Ошибка сети: ' + e.message, true)
    } finally {
      authBtn.disabled = false
    }
  }

  authBtn.addEventListener('click', doAuth)
})

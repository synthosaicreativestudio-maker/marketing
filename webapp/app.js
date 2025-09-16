document.addEventListener('DOMContentLoaded', function () {
  // Initialize Telegram Web App
  if (window.Telegram && window.Telegram.WebApp) {
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    
    // Set theme colors
    document.body.style.backgroundColor = tg.themeParams.bg_color || '#ffffff';
    document.body.style.color = tg.themeParams.text_color || '#000000';
    
    // Setup Main Button instead of HTML button
    tg.MainButton.setText('Авторизоваться');
    tg.MainButton.show();
    
    // Hide HTML button when using MainButton
    const authBtn = document.getElementById('authBtn');
    if (authBtn) {
      authBtn.style.display = 'none';
    }
    
    // Handle Main Button click
    tg.MainButton.onClick(doAuth);
  }

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

    // Disable MainButton and show loader
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.MainButton.showProgress();
    }
    setMessage('Проверяю...', false)

    try {
      // Use Telegram Web App sendData for keyboard button
      if (window.Telegram && window.Telegram.WebApp) {
        const dataToSend = JSON.stringify({
          partner_code: code,
          partner_phone: phone
        })
        
        console.log('Отправляем данные через sendData:', dataToSend)
        window.Telegram.WebApp.sendData(dataToSend)
        setMessage('Данные отправлены боту...', false)
      } else {
        setMessage('Ошибка: Telegram Web App недоступен', true)
      }
    } catch (e) {
      setMessage('Ошибка отправки: ' + e.message, true)
    } finally {
      // Hide loader and enable MainButton
      if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.MainButton.hideProgress();
      }
    }
  }

  // HTML button fallback for testing outside Telegram
  if (authBtn) {
    authBtn.addEventListener('click', doAuth)
  }
})

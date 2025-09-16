document.addEventListener('DOMContentLoaded', function () {
  // Initialize Telegram Web App
  if (window.Telegram && window.Telegram.WebApp) {
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    
    console.log('🔍 Telegram Web App initialized:', tg);
    console.log('🔍 MainButton available:', !!tg.MainButton);
    
    // Set theme colors
    document.body.style.backgroundColor = tg.themeParams.bg_color || '#ffffff';
    document.body.style.color = tg.themeParams.text_color || '#000000';
    
    // Try to setup MainButton as additional option
    try {
      tg.MainButton.setText('Авторизоваться');
      tg.MainButton.show();
      tg.MainButton.onClick(doAuth);
      console.log('🔍 MainButton configured as additional option');
    } catch (e) {
      console.log('❌ MainButton setup failed:', e);
    }

    // Setup keyboard button for input fields
    try {
      // Show keyboard button when user focuses on input fields
      const codeInput = document.getElementById('partner_code');
      const phoneInput = document.getElementById('partner_phone');
      
      if (codeInput && phoneInput) {
        const updateMainButton = () => {
          const code = codeInput.value.trim();
          const phone = phoneInput.value.trim();
          
          if (tg.MainButton) {
            if (code && phone) {
              tg.MainButton.setText('Авторизоваться');
              tg.MainButton.show();
              tg.MainButton.enable();
            } else {
              tg.MainButton.setText('Заполните поля');
              tg.MainButton.show();
              tg.MainButton.disable();
            }
          }
        };
        
        // Show/update button on focus and input
        codeInput.addEventListener('focus', updateMainButton);
        phoneInput.addEventListener('focus', updateMainButton);
        codeInput.addEventListener('input', updateMainButton);
        phoneInput.addEventListener('input', updateMainButton);
        
        // Initial check
        updateMainButton();
        
        console.log('🔍 Smart keyboard button setup for input fields');
      }
    } catch (e) {
      console.log('❌ Keyboard button setup failed:', e);
    }
  } else {
    console.log('❌ Telegram Web App not available');
  }

  const msg = document.getElementById('msg')
  const keyboardButton = document.getElementById('keyboard-button')
  const authKeyboardBtn = document.getElementById('auth-keyboard-btn')

  function setMessage(text, isError) {
    msg.textContent = text
    msg.style.color = isError ? 'crimson' : 'green'
  }

  async function doAuth() {
    console.log('🚀 doAuth function called');
    
    const codeEl = document.getElementById('partner_code')
    const phoneEl = document.getElementById('partner_phone')
    const code = codeEl.value.trim()
    const phone = phoneEl.value.trim()

    console.log('🔍 Начинаем авторизацию:', { code, phone })

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

    // Show loader on MainButton
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
      // Hide loader on MainButton
      if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.MainButton.hideProgress();
      }
    }
  }

  // Setup floating keyboard button
  if (keyboardButton && authKeyboardBtn) {
    const codeInput = document.getElementById('partner_code');
    const phoneInput = document.getElementById('partner_phone');
    
    // Show/hide floating button based on keyboard visibility
    const showKeyboardButton = () => {
      const code = codeInput.value.trim();
      const phone = phoneInput.value.trim();
      
      keyboardButton.style.display = 'block';
      
      if (code && phone) {
        authKeyboardBtn.disabled = false;
        authKeyboardBtn.textContent = 'Авторизоваться';
      } else {
        authKeyboardBtn.disabled = true;
        authKeyboardBtn.textContent = 'Заполните поля';
      }
    };
    
    const hideKeyboardButton = () => {
      keyboardButton.style.display = 'none';
    };
    
    // Event listeners for input fields
    if (codeInput && phoneInput) {
      codeInput.addEventListener('focus', showKeyboardButton);
      phoneInput.addEventListener('focus', showKeyboardButton);
      codeInput.addEventListener('input', showKeyboardButton);
      phoneInput.addEventListener('input', showKeyboardButton);
      
      codeInput.addEventListener('blur', () => {
        setTimeout(hideKeyboardButton, 100); // Delay to allow button click
      });
      phoneInput.addEventListener('blur', () => {
        setTimeout(hideKeyboardButton, 100); // Delay to allow button click
      });
    }
    
    // Add click handler to floating button
    authKeyboardBtn.addEventListener('click', doAuth);
    
    console.log('🔍 Floating keyboard button setup complete');
  }
})

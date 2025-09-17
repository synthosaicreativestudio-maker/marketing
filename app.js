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
  const hideKeyboardBtn = document.getElementById('hide-keyboard-btn')

  function setMessage(text, isError) {
    msg.textContent = text
    msg.style.color = isError ? 'crimson' : 'green'
  }

  // Function to hide keyboard
  function hideKeyboard() {
    if (document.activeElement) {
      document.activeElement.blur();
      console.log('🔍 Keyboard hidden programmatically');
    }
  }

  // Function to normalize phone number and check if complete
  function normalizePhone(phone) {
    const digits = phone.replace(/\D/g, ''); // Remove non-digits
    return digits;
  }

  function isPhoneComplete(phone) {
    const digits = normalizePhone(phone);
    return digits.length >= 11; // Russian phone number
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
        
        // Закрываем WebApp после отправки данных
        setTimeout(() => {
          window.Telegram.WebApp.close();
        }, 2000); // Небольшая задержка для отображения сообщения
      } else {
        setMessage('Ошибка: Telegram Web App недоступен', true)
      }
    } catch (e) {
      setMessage('Ошибка отправки: ' + e.message, true)
      console.error('Ошибка отправки данных:', e);
    } finally {
      // Hide loader on MainButton
      if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.MainButton.hideProgress();
      }
    }
  }

  // Setup floating keyboard button with iOS Safari support
  if (keyboardButton && authKeyboardBtn) {
    const codeInput = document.getElementById('partner_code');
    const phoneInput = document.getElementById('partner_phone');
    
    // Check if input should trigger keyboard
    const isKeyboardInput = (elem) => {
      return elem.tagName === 'INPUT' && 
             !['button', 'submit', 'checkbox', 'file', 'image'].includes(elem.type);
    };
    
    // Update button state based on input values
    const updateButtonState = () => {
      const code = codeInput.value.trim();
      const phone = phoneInput.value.trim();
      
      // Show buttons if any field has content
      if (code || phone) {
        keyboardButton.style.display = 'block';
        document.body.classList.add('keyboard-open');
      }
      
      if (code && phone) {
        authKeyboardBtn.disabled = false;
        authKeyboardBtn.textContent = 'Авторизоваться';
      } else {
        authKeyboardBtn.disabled = true;
        authKeyboardBtn.textContent = 'Заполните поля';
      }
    };
    
    // Show keyboard button
    const showKeyboardButton = () => {
      document.body.classList.add('keyboard-open');
      keyboardButton.style.display = 'block';
      updateButtonState();
      console.log('🔍 Keyboard opened - button shown');
    };
    
    // Hide keyboard button
    const hideKeyboardButton = () => {
      document.body.classList.remove('keyboard-open');
      keyboardButton.style.display = 'none';
      console.log('🔍 Keyboard closed - button hidden');
    };
    
    // Modern approach: Use focusin/focusout events (iOS Safari compatible)
    document.addEventListener('focusin', (e) => {
      if (e.target && isKeyboardInput(e.target)) {
        showKeyboardButton();
      }
    });
    
    document.addEventListener('focusout', (e) => {
      if (e.target && isKeyboardInput(e.target)) {
        // Delay to allow button click before hiding
        setTimeout(hideKeyboardButton, 150);
      }
    });
    
    // Update button state on input and auto-hide keyboard
    if (codeInput && phoneInput) {
      codeInput.addEventListener('input', updateButtonState);
      
      phoneInput.addEventListener('input', (e) => {
        updateButtonState();
        
        // Auto-hide keyboard when phone number is complete (11 digits)
        const phone = e.target.value;
        if (isPhoneComplete(phone)) {
          setTimeout(() => {
            hideKeyboard();
            setMessage('Номер телефона введён полностью', false);
          }, 500); // Small delay for better UX
        }
      });
    }
    
    // Add click handlers
    authKeyboardBtn.addEventListener('click', doAuth);
    
    if (hideKeyboardBtn) {
      hideKeyboardBtn.addEventListener('click', hideKeyboard);
    }
    
    // Modern viewport API support (if available)
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', () => {
        console.log('🔍 Viewport resized:', window.visualViewport.height);
      });
    }
    
    console.log('🔍 iOS-compatible keyboard button setup complete');
    
    // DEBUG: Force show buttons for testing
    setTimeout(() => {
      if (keyboardButton) {
        keyboardButton.style.display = 'block';
        document.body.classList.add('keyboard-open');
        console.log('🔍 DEBUG: Force showing keyboard buttons for testing');
      }
    }, 2000);
  }
})

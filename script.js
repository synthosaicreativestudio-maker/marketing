const tg = window.Telegram.WebApp;
tg.ready();

// Кэш для акций
let promotionsCache = {
    data: null,
    timestamp: null,
    ttl: 10 * 60 * 1000 // 10 минут в миллисекундах
};

const SECTIONS = [
    'Агрегаторы',
    'Контент', 
    'Финансы',
    'Технические проблемы',
    'Дизайн и материалы',
    'Регламенты и обучение',
    'Акции и мероприятия',
    'Аналитика',
    'Связаться со специалистом'
];

const SUBSECTIONS = {
    'Агрегаторы': [
        'Статус',
        'Проблемы с выгрузкой',
        'Платное продвижение',
        'Ошибки, отклонения и блокировки',
        'Редактирование контента на площадках',
        'Прочие вопросы'
    ],
    'Контент': [
        'Заказ фото/видео съемки',
        'Работа с текстами объявлений',
        'Требования к контенту',
        'Прочие вопросы'
    ],
    'Финансы': [
        'Списания и расходы',
        'Баланс и пополнение',
        'Отчетность',
        'Прочие вопросы'
    ],
    'Технические проблемы': [
        'Доступ к системам',
        'Проблемы с телефонией',
        'Прочие вопросы'
    ],
    'Дизайн и материалы': [
        'Заказ полиграфии',
        'Заказ цифровых материалов',
        'Прочие вопросы'
    ],
    'Акции и мероприятия': [
        'Акции',
        'Мероприятия',
        'События',
        'Прочие вопросы'
    ]
};

const SECTIONS_WITH_SUBSECTIONS = ['Агрегаторы', 'Контент', 'Финансы', 'Технические проблемы', 'Дизайн и материалы', 'Акции и мероприятия'];

// Навигация между экранами
function showScreen(screenId) {
    const screens = document.querySelectorAll('.screen');
    screens.forEach(screen => {
        screen.classList.remove('active', 'prev');
        if (screen.id === screenId) {
            screen.classList.add('active');
        } else {
            screen.classList.add('prev');
        }
    });
}

function goToMain() {
    showScreen('main-screen');
}

function goToSection(section) {
    const screenMap = {
        'Агрегаторы': 'agregatory-screen',
        'Контент': 'content-screen',
        'Финансы': 'finance-screen',
        'Технические проблемы': 'tech-screen',
        'Дизайн и материалы': 'design-screen',
        'Акции и мероприятия': 'events-screen'
    };
    
    if (screenMap[section]) {
        showScreen(screenMap[section]);
    }
}

function goToEvents() {
    showScreen('events-screen');
}

function goToPromotions() {
    showScreen('promotions-screen');
    loadPromotions();
}



// Отправка данных в бот
function sendToBot(data) {
    try {
        // Проверяем доступность Telegram API
        if (typeof tg.sendData !== 'function') {
            console.error('Telegram WebApp API недоступен');
            tg.showAlert('Ошибка: Telegram API недоступен');
            return false;
        }
        
        // Валидация данных
        if (!data || typeof data !== 'object') {
            console.error('Некорректные данные для отправки:', data);
            tg.showAlert('Ошибка: некорректные данные');
            return false;
        }
        
        const jsonData = JSON.stringify(data);
        console.log('Отправка данных:', jsonData);
        tg.sendData(jsonData);
        return true;
    } catch(error) {
        console.error('Ошибка при отправке данных:', error);
        tg.showAlert('Ошибка при отправке. Попробуйте ещё раз.');
        return false;
    }
}

// Создание главного меню
function renderMainMenu() {
    const mainGrid = document.getElementById('main_menu_grid');
    mainGrid.innerHTML = '';
    
    SECTIONS.forEach(section => {
        const btn = document.createElement('button');
        btn.className = 'menu-btn';
        btn.textContent = section;
        
        btn.onclick = () => {
            if (SECTIONS_WITH_SUBSECTIONS.includes(section)) {
                // Переход к подразделам
                goToSection(section);
            } else {
                // Отправка данных для разделов без подпунктов
                if (sendToBot({type: 'menu_selection', section: section})) {
                    btn.textContent = 'Отправлено ✓';
                    setTimeout(() => {
                        btn.textContent = section;
                    }, 2000);
                }
            }
        };
        
        mainGrid.appendChild(btn);
    });
}

// Создание подменю для разделов
function renderSubsectionMenu(section, gridId) {
    const grid = document.getElementById(gridId);
    grid.innerHTML = '';
    
    if (SUBSECTIONS[section]) {
        SUBSECTIONS[section].forEach(subsection => {
            const btn = document.createElement('button');
            btn.className = 'menu-btn';
            btn.textContent = subsection;
            
            btn.onclick = () => {
                // Специальная обработка для Акций
                if (section === 'Акции и мероприятия' && subsection === 'Акции') {
                    goToPromotions();
                    return;
                }
                
                // Обычная обработка для остальных подразделов
                if (sendToBot({type: 'subsection_selection', section: section, subsection: subsection})) {
                    btn.textContent = 'Отправлено ✓';
                    setTimeout(() => {
                        tg.close();
                    }, 1000);
                }
            };
            
            grid.appendChild(btn);
        });
    }
}

// Инициализация
function init() {
    renderMainMenu();
    renderSubsectionMenu('Агрегаторы', 'agregatory_grid');
    renderSubsectionMenu('Контент', 'content_grid');
    renderSubsectionMenu('Финансы', 'finance_grid');
    renderSubsectionMenu('Технические проблемы', 'tech_grid');
    renderSubsectionMenu('Дизайн и материалы', 'design_grid');
    renderSubsectionMenu('Акции и мероприятия', 'events_grid');
}

// Запуск при загрузке
init();

// Проверяем URL параметры для автоматического перехода
const urlParams = new URLSearchParams(window.location.search);
const section = urlParams.get('section');
if (section === 'promotions') {
    // Автоматически переходим в раздел акций
    setTimeout(() => {
        goToPromotions();
    }, 500);
}

// Слушатель для получения данных от бота
tg.onEvent('webAppDataReceived', function(data) {
    console.log('📱 Получены данные от бота:', data);
    try {
        const payload = JSON.parse(data);
        if (payload.type === 'promotions_response') {
            console.log('🎉 Получены акции от бота:', payload.promotions);
            const promotions = payload.promotions || [];
            updatePromotionsCache(promotions);
            renderPromotions(promotions);
        }
    } catch (e) {
        console.error('❌ Ошибка парсинга данных от бота:', e);
        renderPromotions([]);
    }
});

// Функции для акций
function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('ru-RU');
    } catch (e) {
        return dateStr;
    }
}

function getStatusText(status) {
    switch (status) {
        case 'active': return 'Активна';
        case 'published': return 'Опубликована';
        case 'finished': return 'Завершена';
        default: return status;
    }
}

function getStatusEmoji(status) {
    switch (status) {
        case 'active': return '🟢';
        case 'published': return '🟡';
        case 'finished': return '🔴';
        default: return '⚪';
    }
}

function renderPromotions(promotions) {
    const container = document.getElementById('promotions-content');
    console.log('🎨 renderPromotions вызвана с данными:', promotions);
    
    if (!promotions || promotions.length === 0) {
        console.log('📋 Нет акций для отображения');
        container.innerHTML = `
            <div class="no-promotions">
                <div class="no-promotions-icon">📋</div>
                <h2>Актуальных акций пока нет</h2>
                <p>Следите за обновлениями!<br>Мы обязательно сообщим о новых предложениях.</p>
                <div style="text-align: center; margin-top: 30px;">
                    <button class="menu-btn back-btn" onclick="goToMain()">
                        ← Назад в меню
                    </button>
                </div>
            </div>
        `;
        return;
    }
    
    console.log(`🎉 Отображаем ${promotions.length} акций`);

    let html = `
        <div class="promotions-header">
            <h2 style="text-align: center; margin-bottom: 30px; color: #d4af37;">🎯 АКТИВНЫЕ АКЦИИ</h2>
        </div>
        <div class="promotions-list">
    `;
    
    promotions.forEach((promotion, index) => {
        // Показываем только название акции (столбец B)
        html += `
            <div class="promotion-card" onclick="togglePromotion(${index})">
                <div class="promotion-header">
                    <div class="promotion-title">
                        ${promotion.name || 'Без названия'}
                    </div>
                    <div class="promotion-toggle">▼</div>
                </div>
                <div class="promotion-content">
                    ${promotion.description ? `<div class="promotion-description"><strong>Описание:</strong><br>${promotion.description}</div>` : ''}
                    ${promotion.content ? `<div class="promotion-content-text"><strong>Контент:</strong><br>${promotion.content}</div>` : ''}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    // Добавляем кнопки навигации
    html += `
        <div style="text-align: center; margin-top: 30px;">
            <button class="menu-btn back-btn" onclick="goToMain()">
                ← Назад в меню
            </button>
            <button class="menu-btn back-btn" onclick="goToEvents()" style="margin-left: 10px;">
                ← Назад к мероприятиям
            </button>
        </div>
    `;
    
    container.innerHTML = html;
}

function togglePromotion(index) {
    console.log(`🔄 togglePromotion вызвана для индекса: ${index}`);
    const cards = document.querySelectorAll('.promotion-card');
    console.log(`📋 Найдено ${cards.length} карточек акций`);
    const card = cards[index];
    if (card) {
        card.classList.toggle('expanded');
        console.log(`✅ Карточка ${index} переключена, класс expanded: ${card.classList.contains('expanded')}`);
    } else {
        console.error(`❌ Карточка с индексом ${index} не найдена`);
    }
}

function renderMediaContent(media) {
    if (!media || media.length === 0) {
        return '';
    }
    
    let html = '<div class="promotion-media">';
    media.forEach(item => {
        if (item.type === 'image') {
            html += `<div class="media-item"><img src="${item.url}" alt="Медиа контент" loading="lazy"></div>`;
        } else if (item.type === 'video') {
            if (item.url.includes('youtube.com/embed')) {
                html += `<div class="media-item"><iframe src="${item.url}" frameborder="0" allowfullscreen></iframe></div>`;
            } else {
                html += `<div class="media-item"><video controls><source src="${item.url}" type="video/mp4"></video></div>`;
            }
        }
    });
    html += '</div>';
    return html;
}

function loadPromotions() {
    // Проверяем кэш
    if (promotionsCache.data && promotionsCache.timestamp) {
        const now = Date.now();
        const cacheAge = now - promotionsCache.timestamp;
        
        if (cacheAge < promotionsCache.ttl) {
            console.log('💾 Используем кэшированные акции');
            renderPromotions(promotionsCache.data);
            return;
        } else {
            console.log('⏰ Кэш устарел, обновляем данные');
        }
    }
    
    // Запрашиваем реальные данные акций от бота
    console.log('🔄 Загружаем акции от бота...');
    
    // Отправляем запрос на получение акций
    const requestData = {
        type: 'get_promotions',
        timestamp: new Date().toISOString()
    };
    
    if (sendToBot(requestData)) {
        console.log('✅ Запрос акций отправлен боту');
        // Показываем загрузку пока ждем ответ
        setTimeout(() => {
            // Если через 5 секунд нет ответа, показываем пустое состояние
            const container = document.getElementById('promotions-content');
            if (container.innerHTML.includes('loading-spinner')) {
                console.log('⏰ Таймаут загрузки акций, показываем пустое состояние');
                renderPromotions([]);
            }
        }, 5000);
    } else {
        console.error('❌ Не удалось отправить запрос акций');
        renderPromotions([]);
    }
}

function updatePromotionsCache(promotions) {
    promotionsCache.data = promotions;
    promotionsCache.timestamp = Date.now();
    console.log('💾 Кэш акций обновлен');
}

function refreshPromotions() {
    // Очищаем кэш и загружаем заново
    promotionsCache.data = null;
    promotionsCache.timestamp = null;
    console.log('🔄 Принудительное обновление акций');
    loadPromotions();
}

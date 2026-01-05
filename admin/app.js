// Конфигурация API
const API_BASE_URL = window.location.origin + '/api';
// Для локальной разработки можно использовать:
// const API_BASE_URL = 'http://localhost:8000/api';

// Состояние приложения
let currentAppealId = null;
let authToken = null;

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем, есть ли сохраненный токен
    authToken = localStorage.getItem('authToken');
    
    if (authToken) {
        showMainScreen();
        loadAppeals();
    } else {
        showLoginScreen();
    }

    // Обработчики событий
    setupEventHandlers();
});

// Настройка обработчиков событий
function setupEventHandlers() {
    // Логин
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    
    // Выход
    document.getElementById('logoutBtn').addEventListener('click', handleLogout);
    
    // Фильтр статусов
    document.getElementById('statusFilter').addEventListener('change', (e) => {
        loadAppeals(e.target.value);
    });
    
    // Обновление списка
    document.getElementById('refreshBtn').addEventListener('click', () => {
        loadAppeals(document.getElementById('statusFilter').value);
    });
    
    // Назад к списку
    document.getElementById('backBtn').addEventListener('click', () => {
        showMainScreen();
        loadAppeals();
    });
    
    // Отправка ответа
    document.getElementById('sendResponseBtn').addEventListener('click', sendResponse);
    
    // Изменение статуса
    document.getElementById('updateStatusBtn').addEventListener('click', updateStatus);
}

// Показ экранов
function showLoginScreen() {
    document.getElementById('loginScreen').classList.remove('hidden');
    document.getElementById('mainScreen').classList.add('hidden');
    document.getElementById('detailScreen').classList.add('hidden');
}

function showMainScreen() {
    document.getElementById('loginScreen').classList.add('hidden');
    document.getElementById('mainScreen').classList.remove('hidden');
    document.getElementById('detailScreen').classList.add('hidden');
}

function showDetailScreen() {
    document.getElementById('loginScreen').classList.add('hidden');
    document.getElementById('mainScreen').classList.add('hidden');
    document.getElementById('detailScreen').classList.remove('hidden');
}

// Авторизация
async function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');
    
    // Простая проверка (в продакшене использовать реальную авторизацию)
    // Для MVP используем простую проверку
    if (username === 'admin' && password === 'admin') {
        authToken = 'demo_token_' + Date.now();
        localStorage.setItem('authToken', authToken);
        errorDiv.classList.remove('show');
        showMainScreen();
        loadAppeals();
    } else {
        errorDiv.textContent = 'Неверный логин или пароль';
        errorDiv.classList.add('show');
    }
}

function handleLogout() {
    authToken = null;
    localStorage.removeItem('authToken');
    showLoginScreen();
    document.getElementById('loginForm').reset();
}

// Загрузка списка обращений
async function loadAppeals(status = '') {
    const loadingIndicator = document.getElementById('loadingIndicator');
    const appealsList = document.getElementById('appealsList');
    
    loadingIndicator.style.display = 'block';
    appealsList.innerHTML = '';
    
    try {
        const url = status 
            ? `${API_BASE_URL}/appeals?status=${status}`
            : `${API_BASE_URL}/appeals`;
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки обращений');
        }
        
        const appeals = await response.json();
        
        if (appeals.length === 0) {
            appealsList.innerHTML = '<div class="appeal-card"><p style="text-align: center; color: #888;">Обращений не найдено</p></div>';
        } else {
            appealsList.innerHTML = appeals.map(appeal => createAppealCard(appeal)).join('');
            
            // Добавляем обработчики кликов
            appeals.forEach(appeal => {
                document.getElementById(`appeal-${appeal.id}`).addEventListener('click', () => {
                    showAppealDetail(appeal.id);
                });
            });
        }
    } catch (error) {
        console.error('Ошибка загрузки обращений:', error);
        appealsList.innerHTML = '<div class="appeal-card"><p style="text-align: center; color: #e74c3c;">Ошибка загрузки данных</p></div>';
    } finally {
        loadingIndicator.style.display = 'none';
    }
}

// Создание карточки обращения
function createAppealCard(appeal) {
    const statusClass = `status-${appeal.status}`;
    const statusText = getStatusText(appeal.status);
    const createdDate = new Date(appeal.created_at).toLocaleString('ru-RU');
    
    return `
        <div class="appeal-card" id="appeal-${appeal.id}">
            <div class="appeal-header">
                <span class="status-badge ${statusClass}">${statusText}</span>
                <span class="appeal-date">${createdDate}</span>
            </div>
            <div class="appeal-info">
                <div class="info-item">
                    <span class="info-label">ФИО</span>
                    <span class="info-value">${appeal.fio || 'Не указано'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Телефон</span>
                    <span class="info-value">${appeal.phone || 'Не указано'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Код партнера</span>
                    <span class="info-value">${appeal.partner_code || 'Не указано'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Telegram ID</span>
                    <span class="info-value">${appeal.telegram_id}</span>
                </div>
            </div>
        </div>
    `;
}

// Получение текста статуса
function getStatusText(status) {
    const statusMap = {
        'новое': 'Новое',
        'в_работе': 'В работе',
        'передано_специалисту': 'Передано специалисту',
        'ответ_ии': 'Ответ ИИ',
        'решено': 'Решено'
    };
    return statusMap[status] || status;
}

// Показать детали обращения
async function showAppealDetail(appealId) {
    currentAppealId = appealId;
    showDetailScreen();
    
    const detailDiv = document.getElementById('appealDetail');
    detailDiv.innerHTML = '<div class="loading">Загрузка...</div>';
    
    try {
        // Загружаем обращение
        const appealResponse = await fetch(`${API_BASE_URL}/appeals/${appealId}`);
        if (!appealResponse.ok) throw new Error('Ошибка загрузки обращения');
        const appeal = await appealResponse.json();
        
        // Загружаем сообщения
        const messagesResponse = await fetch(`${API_BASE_URL}/appeals/${appealId}/messages`);
        if (!messagesResponse.ok) throw new Error('Ошибка загрузки сообщений');
        const messages = await messagesResponse.json();
        
        // Отображаем детали
        detailDiv.innerHTML = createAppealDetailHTML(appeal, messages);
        
        // Устанавливаем текущий статус в селект
        document.getElementById('statusSelect').value = appeal.status;
        
    } catch (error) {
        console.error('Ошибка загрузки деталей:', error);
        detailDiv.innerHTML = '<p style="color: #e74c3c;">Ошибка загрузки данных</p>';
    }
}

// Создание HTML деталей обращения
function createAppealDetailHTML(appeal, messages) {
    const statusClass = `status-${appeal.status}`;
    const statusText = getStatusText(appeal.status);
    const createdDate = new Date(appeal.created_at).toLocaleString('ru-RU');
    const updatedDate = new Date(appeal.updated_at).toLocaleString('ru-RU');
    
    const messagesHTML = messages.map(msg => {
        const messageClass = `message-${msg.message_type}`;
        const messageTypeText = {
            'user': '👤 Пользователь',
            'ai': '🤖 ИИ',
            'specialist': '👨‍💼 Специалист'
        }[msg.message_type] || msg.message_type;
        
        const messageDate = new Date(msg.created_at).toLocaleString('ru-RU');
        
        return `
            <div class="message ${messageClass}">
                <div class="message-header">
                    <span>${messageTypeText}</span>
                    <span>${messageDate}</span>
                </div>
                <div class="message-text">${escapeHtml(msg.message_text)}</div>
            </div>
        `;
    }).join('');
    
    return `
        <div class="detail-header">
            <span class="status-badge ${statusClass}">${statusText}</span>
        </div>
        <div class="detail-info">
            <div class="info-item">
                <span class="info-label">ID обращения</span>
                <span class="info-value">#${appeal.id}</span>
            </div>
            <div class="info-item">
                <span class="info-label">ФИО</span>
                <span class="info-value">${appeal.fio || 'Не указано'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Телефон</span>
                <span class="info-value">${appeal.phone || 'Не указано'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Код партнера</span>
                <span class="info-value">${appeal.partner_code || 'Не указано'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Telegram ID</span>
                <span class="info-value">${appeal.telegram_id}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Создано</span>
                <span class="info-value">${createdDate}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Обновлено</span>
                <span class="info-value">${updatedDate}</span>
            </div>
        </div>
        <div class="messages-section">
            <h3 class="messages-title">История сообщений</h3>
            ${messagesHTML || '<p style="color: #888;">Сообщений пока нет</p>'}
        </div>
    `;
}

// Отправка ответа
async function sendResponse() {
    const responseText = document.getElementById('responseText').value.trim();
    
    if (!responseText) {
        alert('Введите текст ответа');
        return;
    }
    
    if (!currentAppealId) {
        alert('Ошибка: ID обращения не найден');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/appeals/${currentAppealId}/response`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                response_text: responseText,
                specialist_name: 'Консультант'
            })
        });
        
        if (!response.ok) {
            throw new Error('Ошибка отправки ответа');
        }
        
        // Очищаем поле ввода
        document.getElementById('responseText').value = '';
        
        // Обновляем детали обращения
        showAppealDetail(currentAppealId);
        
        alert('Ответ успешно отправлен!');
        
    } catch (error) {
        console.error('Ошибка отправки ответа:', error);
        alert('Ошибка отправки ответа');
    }
}

// Изменение статуса
async function updateStatus() {
    const newStatus = document.getElementById('statusSelect').value;
    
    if (!currentAppealId) {
        alert('Ошибка: ID обращения не найден');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/appeals/${currentAppealId}/status?status=${newStatus}`, {
            method: 'PATCH'
        });
        
        if (!response.ok) {
            throw new Error('Ошибка изменения статуса');
        }
        
        // Обновляем детали обращения
        showAppealDetail(currentAppealId);
        
        alert('Статус успешно изменен!');
        
    } catch (error) {
        console.error('Ошибка изменения статуса:', error);
        alert('Ошибка изменения статуса');
    }
}

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

"""
Модуль для управления кэшем авторизации
Объединяет все кэши в единую систему с поддержкой персистентности
"""

import json
import os
import time
import logging
import threading
from typing import Set, Dict, Optional, Tuple
from config import AUTH_CONFIG

logger = logging.getLogger(__name__)

class AuthCache:
    """Единый кэш для авторизации пользователей с поддержкой персистентности"""
    
    def __init__(self, persistence_file: str = 'auth_cache.json'):
        self._lock = threading.Lock()  # Thread-safe операции
        self.authorized_ids: Set[str] = set()
        self.auth_timestamp: float = 0
        self.user_cache: Dict[int, Dict] = {}  # user_id -> {is_authorized, timestamp, partner_code, phone}
        self.failed_attempts: Dict[int, Dict] = {}  # user_id -> {attempts, blocked_until, block_count}
        
        # Конфигурация
        self.cache_ttl = AUTH_CONFIG['CACHE_TTL']
        self.user_cache_ttl = AUTH_CONFIG['USER_CACHE_TTL']
        self.max_attempts = AUTH_CONFIG['MAX_ATTEMPTS']
        self.block_durations = AUTH_CONFIG['BLOCK_DURATIONS']
        
        # Персистентность
        self.persistence_file = persistence_file
        self._load_from_file()
    
    def _load_from_file(self):
        """Загружает данные кэша из файла"""
        if not os.path.exists(self.persistence_file):
            return
            
        try:
            with open(self.persistence_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Восстанавливаем авторизованные ID
            self.authorized_ids = set(data.get('authorized_ids', []))
            self.auth_timestamp = data.get('auth_timestamp', 0)
            
            # Восстанавливаем кэш пользователей
            user_cache_raw = data.get('user_cache', {})
            self.user_cache = {int(k): v for k, v in user_cache_raw.items()}
            
            # Восстанавливаем неудачные попытки
            failed_attempts_raw = data.get('failed_attempts', {})
            self.failed_attempts = {int(k): v for k, v in failed_attempts_raw.items()}
            
            logger.info(f'Кэш авторизации загружен: {len(self.authorized_ids)} авторизованных пользователей')
            
        except Exception as e:
            logger.warning(f'Ошибка загрузки кэша из {self.persistence_file}: {e}')
    
    def _save_to_file(self):
        """Сохраняет данные кэша в файл"""
        try:
            data = {
                'authorized_ids': list(self.authorized_ids),
                'auth_timestamp': self.auth_timestamp,
                'user_cache': {str(k): v for k, v in self.user_cache.items()},
                'failed_attempts': {str(k): v for k, v in self.failed_attempts.items()},
                'last_saved': time.time()
            }
            
            with open(self.persistence_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f'Кэш авторизации сохранён в {self.persistence_file}')
            
        except Exception as e:
            logger.error(f'Ошибка сохранения кэша в {self.persistence_file}: {e}')
    
    def get_authorized_ids(self) -> Optional[Set[str]]:
        """Получает кэшированный список авторизованных ID"""
        now = time.time()
        
        if self.authorized_ids and (now - self.auth_timestamp < self.cache_ttl):
            return self.authorized_ids
        
        return None
    
    def set_authorized_ids(self, ids: Set[str]):
        """Устанавливает список авторизованных ID"""
        self.authorized_ids = set(str(i) for i in ids if i)
        self.auth_timestamp = time.time()
        logger.info(f'Кэш авторизованных пользователей обновлён: {len(self.authorized_ids)} записей')
        self._save_to_file()
    
    def is_user_authorized(self, user_id: int) -> Optional[bool]:
        """Проверяет авторизацию пользователя из кэша"""
        if user_id not in self.user_cache:
            return None
        
        user_data = self.user_cache[user_id]
        if 'auth_timestamp' not in user_data:
            return None
        
        # Проверяем TTL кэша пользователя
        if time.time() - user_data['auth_timestamp'] < self.user_cache_ttl:
            return user_data.get('is_authorized', False)
        
        # Кэш устарел
        return None
    
    def set_user_authorized(self, user_id: int, is_authorized: bool, partner_code: str = '', phone: str = ''):
        """Устанавливает статус авторизации пользователя"""
        with self._lock:
            self.user_cache[user_id] = {
                'is_authorized': is_authorized,
                'auth_timestamp': time.time(),
                'partner_code': partner_code,
                'phone': phone
            }
            self._save_to_file()
    
    def get_user_data(self, user_id: int) -> Optional[Dict]:
        """Получает данные пользователя из кэша"""
        if user_id not in self.user_cache:
            return None
        
        user_data = self.user_cache[user_id]
        if time.time() - user_data['auth_timestamp'] < self.user_cache_ttl:
            return user_data
        
        return None
    
    def is_user_blocked(self, user_id: int) -> Tuple[bool, int]:
        """Проверяет заблокирован ли пользователь"""
        if user_id not in self.failed_attempts:
            return False, 0
        
        user_data = self.failed_attempts[user_id]
        blocked_until = user_data.get('blocked_until', 0)
        
        if blocked_until > time.time():
            return True, int(blocked_until - time.time())
        
        # Разблокирован - сбрасываем попытки
        if blocked_until > 0:
            user_data['attempts'] = 0
            user_data['blocked_until'] = 0
        
        return False, 0
    
    def add_failed_attempt(self, user_id: int) -> Tuple[bool, int]:
        """Добавляет неудачную попытку авторизации"""
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = {
                'attempts': 0, 
                'blocked_until': 0, 
                'block_count': 0
            }
        
        user_data = self.failed_attempts[user_id]
        user_data['attempts'] += 1
        
        if user_data['attempts'] >= self.max_attempts:
            # Блокируем пользователя
            block_count = min(user_data['block_count'], len(self.block_durations) - 1)
            block_duration = self.block_durations[block_count]
            user_data['blocked_until'] = time.time() + block_duration
            user_data['block_count'] += 1
            user_data['attempts'] = 0
            return True, block_duration
        
        return False, 0
    
    def clear_failed_attempts(self, user_id: int):
        """Очищает неудачные попытки при успешной авторизации"""
        if user_id in self.failed_attempts:
            self.failed_attempts[user_id]['attempts'] = 0
            self.failed_attempts[user_id]['blocked_until'] = 0
    
    def get_attempts_left(self, user_id: int) -> int:
        """Получает количество оставшихся попыток"""
        if user_id not in self.failed_attempts:
            return self.max_attempts
        
        user_data = self.failed_attempts[user_id]
        return max(0, self.max_attempts - user_data['attempts'])
    
    def clear_user_cache(self, user_id: int):
        """Очищает кэш конкретного пользователя"""
        if user_id in self.user_cache:
            del self.user_cache[user_id]
    
    def clear_all_caches(self):
        """Очищает все кэши"""
        self.authorized_ids.clear()
        self.auth_timestamp = 0
        self.user_cache.clear()
        self.failed_attempts.clear()
        logger.info('Все кэши авторизации очищены')
        self._save_to_file()
    
    def cleanup_expired_data(self):
        """Удаляет устаревшие данные из кэшей"""
        now = time.time()
        
        # Очищаем устаревшие данные пользователей
        expired_users = []
        for user_id, data in self.user_cache.items():
            if now - data.get('auth_timestamp', 0) > self.user_cache_ttl:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.user_cache[user_id]
        
        # Очищаем разблокированных пользователей
        unblocked_users = []
        for user_id, data in self.failed_attempts.items():
            if data.get('blocked_until', 0) < now and data.get('blocked_until', 0) > 0:
                unblocked_users.append(user_id)
        
        for user_id in unblocked_users:
            self.failed_attempts[user_id]['attempts'] = 0
            self.failed_attempts[user_id]['blocked_until'] = 0
        
        if expired_users or unblocked_users:
            logger.info(f'Очищены устаревшие данные: {len(expired_users)} пользователей, {len(unblocked_users)} разблокировок')
    
    def get_cache_stats(self) -> Dict:
        """Получает статистику кэша"""
        return {
            'authorized_count': len(self.authorized_ids),
            'user_cache_count': len(self.user_cache),
            'failed_attempts_count': len(self.failed_attempts),
            'cache_age': time.time() - self.auth_timestamp if self.auth_timestamp > 0 else 0
        }

# Глобальный экземпляр кэша
auth_cache = AuthCache()



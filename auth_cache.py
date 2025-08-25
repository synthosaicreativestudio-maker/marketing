"""
Модуль для управления кэшем авторизации
Объединяет все кэши в единую систему
"""

import time
import logging
from typing import Set, Dict, Optional, Tuple
from config import AUTH_CONFIG

logger = logging.getLogger(__name__)

class AuthCache:
    """Единый кэш для авторизации пользователей"""
    
    def __init__(self):
        self.authorized_ids: Set[str] = set()
        self.auth_timestamp: float = 0
        self.user_cache: Dict[int, Dict] = {}  # user_id -> {is_authorized, timestamp, partner_code, phone}
        self.failed_attempts: Dict[int, Dict] = {}  # user_id -> {attempts, blocked_until, block_count}
        
        # Конфигурация
        self.cache_ttl = AUTH_CONFIG['CACHE_TTL']
        self.user_cache_ttl = AUTH_CONFIG['USER_CACHE_TTL']
        self.max_attempts = AUTH_CONFIG['MAX_ATTEMPTS']
        self.block_durations = AUTH_CONFIG['BLOCK_DURATIONS']
    
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
        self.user_cache[user_id] = {
            'is_authorized': is_authorized,
            'auth_timestamp': time.time(),
            'partner_code': partner_code,
            'phone': phone
        }
    
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



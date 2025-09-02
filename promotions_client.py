#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Клиент для работы с таблицей акций.
Обеспечивает мониторинг публикаций, получение активных акций и обработку медиа контента.
"""

import gspread
import re
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from oauth2client.service_account import ServiceAccountCredentials
import logging

logger = logging.getLogger(__name__)

class PromotionsClient:
    """
    Клиент для работы с Google Sheets таблицей акций.
    """
    
    def __init__(self, credentials_file: str, sheet_url: str):
        """
        Инициализация клиента акций.
        
        Args:
            credentials_file: Путь к файлу credentials.json
            sheet_url: URL Google Sheets таблицы с акциями
        """
        self.credentials_file = credentials_file
        self.sheet_url = sheet_url
        self.sheet = None
        self.gc = None
        
        # Константы колонок (соответствуют Google Apps Script)
        self.HEADER_ROW = 1
        self.RELEASE_DATE_COLUMN = 1  # A - Дата релиза
        self.NAME_COLUMN = 2          # B - Название
        self.DESCRIPTION_COLUMN = 3   # C - Описание  
        self.STATUS_COLUMN = 4        # D - Статус
        self.START_DATE_COLUMN = 5    # E - Дата начала
        self.END_DATE_COLUMN = 6      # F - Дата окончания
        self.CONTENT_COLUMN = 7       # G - Контент
        self.BUTTON_COLUMN = 8        # H - Опубликовать
        self.NOTIFICATION_COLUMN = 9  # I - Уведомление отправлено
        
        # Статусы
        self.STATUS_PUBLISHED = 'Опубликовано'
        self.STATUS_ACTIVE = 'Активна'
        self.STATUS_WAITING = 'Ожидает'
        self.STATUS_FINISHED = 'Закончена'
        
    def connect(self) -> bool:
        """
        Подключение к Google Sheets.
        
        Returns:
            bool: True если подключение успешно
        """
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            self.gc = gspread.authorize(creds)
            
            # Открываем таблицу по URL
            self.sheet = self.gc.open_by_url(self.sheet_url).worksheet('Акции')
            
            logger.info("✅ Подключение к таблице акций успешно")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к таблице акций: {e}")
            return False
    
    def get_new_published_promotions(self) -> List[Dict[str, Any]]:
        """
        Получает новые опубликованные акции для отправки уведомлений.
        
        Returns:
            List[Dict]: Список новых акций для уведомления
        """
        try:
            if not self.sheet:
                logger.error("Таблица акций не подключена")
                return []
            
            # Получаем все данные таблицы
            all_values = self.sheet.get_all_values()
            
            if len(all_values) <= self.HEADER_ROW:
                return []
            
            new_promotions = []
            
            # Проходим по всем строкам начиная с HEADER_ROW + 1
            for row_idx, row_data in enumerate(all_values[self.HEADER_ROW:], start=self.HEADER_ROW + 1):
                
                # Проверяем достаточно ли колонок
                if len(row_data) < self.STATUS_COLUMN:
                    continue
                
                status = row_data[self.STATUS_COLUMN - 1] if len(row_data) >= self.STATUS_COLUMN else ''
                notification_sent = row_data[self.NOTIFICATION_COLUMN - 1] if len(row_data) >= self.NOTIFICATION_COLUMN else ''
                name = row_data[self.NAME_COLUMN - 1] if len(row_data) >= self.NAME_COLUMN else ''
                
                # Ищем акции со статусом "Активна" без отправленного уведомления
                if status == self.STATUS_ACTIVE and not notification_sent:
                    
                    promotion_data = {
                        'row': row_idx,
                        'release_date': self._parse_date(row_data[self.RELEASE_DATE_COLUMN - 1]) if len(row_data) >= self.RELEASE_DATE_COLUMN else None,
                        'name': row_data[self.NAME_COLUMN - 1] if len(row_data) >= self.NAME_COLUMN else '',
                        'description': row_data[self.DESCRIPTION_COLUMN - 1] if len(row_data) >= self.DESCRIPTION_COLUMN else '',
                        'status': status,
                        'start_date': self._parse_date(row_data[self.START_DATE_COLUMN - 1]) if len(row_data) >= self.START_DATE_COLUMN else None,
                        'end_date': self._parse_date(row_data[self.END_DATE_COLUMN - 1]) if len(row_data) >= self.END_DATE_COLUMN else None,
                        'content': row_data[self.CONTENT_COLUMN - 1] if len(row_data) >= self.CONTENT_COLUMN else '',
                    }
                    
                    # Добавляем только акции с названием
                    if promotion_data['name']:
                        new_promotions.append(promotion_data)
            
            logger.info(f"📬 Найдено {len(new_promotions)} новых акций для уведомления")
            return new_promotions
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения новых акций: {e}")
            return []
    
    def mark_notification_sent(self, row: int) -> bool:
        """
        Помечает акцию как уведомление отправлено.
        
        Args:
            row: Номер строки в таблице
            
        Returns:
            bool: True если успешно
        """
        try:
            if not self.sheet:
                return False
            
            # Расширяем таблицу если нужно
            current_cols = self.sheet.col_count
            if current_cols < self.NOTIFICATION_COLUMN:
                self.sheet.add_cols(self.NOTIFICATION_COLUMN - current_cols)
            
            # Устанавливаем заголовок для колонки уведомлений если его нет
            header_value = self.sheet.cell(self.HEADER_ROW, self.NOTIFICATION_COLUMN).value
            if not header_value:
                self.sheet.update_cell(self.HEADER_ROW, self.NOTIFICATION_COLUMN, 'Уведомление')
            
            # Помечаем уведомление как отправленное
            self.sheet.update_cell(row, self.NOTIFICATION_COLUMN, 'отправлено')
            
            logger.info(f"✅ Акция в строке {row} помечена как уведомление отправлено")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка пометки уведомления: {e}")
            return False
    
    def get_active_promotions(self) -> List[Dict[str, Any]]:
        """
        Получает активные акции для отображения в мини-приложении.
        
        Returns:
            List[Dict]: Список активных акций
        """
        try:
            if not self.sheet:
                logger.error("Таблица акций не подключена")
                return []
            
            all_values = self.sheet.get_all_values()
            
            if len(all_values) <= self.HEADER_ROW:
                return []
            
            active_promotions = []
            today = date.today()
            
            for row_idx, row_data in enumerate(all_values[self.HEADER_ROW:], start=self.HEADER_ROW + 1):
                
                if len(row_data) < self.STATUS_COLUMN:
                    continue
                
                status = row_data[self.STATUS_COLUMN - 1] if len(row_data) >= self.STATUS_COLUMN else ''
                
                # Показываем только активные акции
                if status == self.STATUS_ACTIVE:
                    
                    promotion_data = {
                        'row': row_idx,
                        'release_date': self._parse_date(row_data[self.RELEASE_DATE_COLUMN - 1]) if len(row_data) >= self.RELEASE_DATE_COLUMN else None,
                        'name': row_data[self.NAME_COLUMN - 1] if len(row_data) >= self.NAME_COLUMN else '',
                        'description': row_data[self.DESCRIPTION_COLUMN - 1] if len(row_data) >= self.DESCRIPTION_COLUMN else '',
                        'status': status,
                        'start_date': self._parse_date(row_data[self.START_DATE_COLUMN - 1]) if len(row_data) >= self.START_DATE_COLUMN else None,
                        'end_date': self._parse_date(row_data[self.END_DATE_COLUMN - 1]) if len(row_data) >= self.END_DATE_COLUMN else None,
                        'content': row_data[self.CONTENT_COLUMN - 1] if len(row_data) >= self.CONTENT_COLUMN else '',
                        'media': self._process_media_content(row_data[self.CONTENT_COLUMN - 1]) if len(row_data) >= self.CONTENT_COLUMN else [],
                    }
                    
                    # Определяем актуальный статус для UI
                    promotion_data['ui_status'] = self._determine_ui_status(promotion_data, today)
                    
                    # Добавляем только акции с названием
                    if promotion_data['name']:
                        active_promotions.append(promotion_data)
            
            # Сортируем акции по приоритету
            active_promotions.sort(key=self._get_sort_priority)
            
            logger.info(f"📋 Получено {len(active_promotions)} акций для отображения")
            return active_promotions
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения активных акций: {e}")
            return []
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Парсит дату из строки.
        
        Args:
            date_str: Строка с датой
            
        Returns:
            date или None
        """
        if not date_str:
            return None
        
        try:
            # Пробуем разные форматы дат
            formats = ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y']
            
            for fmt in formats:
                try:
                    return datetime.strptime(str(date_str), fmt).date()
                except ValueError:
                    continue
            
            logger.warning(f"Не удалось распарсить дату: {date_str}")
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга даты {date_str}: {e}")
            return None
    
    def _process_media_content(self, content: str) -> List[Dict[str, str]]:
        """
        Обрабатывает медиа контент из поля "Контент".
        
        Args:
            content: Строка с ссылками на медиа
            
        Returns:
            List[Dict]: Список обработанных медиа файлов
        """
        if not content:
            return []
        
        media_list = []
        
        # Разделяем по запятым если несколько ссылок
        links = [link.strip() for link in content.split(',') if link.strip()]
        
        for link in links:
            media_item = self._process_single_media_link(link)
            if media_item:
                media_list.append(media_item)
        
        return media_list
    
    def _process_single_media_link(self, link: str) -> Optional[Dict[str, str]]:
        """
        Обрабатывает одну ссылку на медиа.
        
        Args:
            link: Ссылка на медиа файл
            
        Returns:
            Dict с типом и URL или None
        """
        try:
            # Google Drive ссылки
            if 'drive.google.com' in link:
                direct_link = self._convert_drive_link(link)
                return {'type': 'image', 'url': direct_link}
            
            # YouTube ссылки
            elif 'youtube.com' in link or 'youtu.be' in link:
                embed_url = self._convert_youtube_link(link)
                return {'type': 'video', 'url': embed_url}
            
            # Прямые ссылки на изображения
            elif any(ext in link.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                return {'type': 'image', 'url': link}
            
            # Прямые ссылки на видео
            elif any(ext in link.lower() for ext in ['.mp4', '.webm', '.ogg']):
                return {'type': 'video', 'url': link}
            
            # Остальные ссылки как изображения по умолчанию
            else:
                return {'type': 'image', 'url': link}
                
        except Exception as e:
            logger.warning(f"Ошибка обработки медиа ссылки {link}: {e}")
            return None
    
    def _convert_drive_link(self, link: str) -> str:
        """
        Конвертирует Google Drive ссылку в прямую ссылку.
        
        Args:
            link: Google Drive ссылка
            
        Returns:
            str: Прямая ссылка
        """
        # Извлекаем ID файла из ссылки
        file_id_match = re.search(r'/file/d/([a-zA-Z0-9-_]+)', link)
        if file_id_match:
            file_id = file_id_match.group(1)
            return f'https://drive.google.com/uc?export=view&id={file_id}'
        
        return link
    
    def _convert_youtube_link(self, link: str) -> str:
        """
        Конвертирует YouTube ссылку в embed ссылку.
        
        Args:
            link: YouTube ссылка
            
        Returns:
            str: Embed ссылка
        """
        # Извлекаем video ID
        video_id = None
        
        if 'youtube.com' in link:
            video_id_match = re.search(r'[?&]v=([^&]+)', link)
            if video_id_match:
                video_id = video_id_match.group(1)
        elif 'youtu.be' in link:
            video_id_match = re.search(r'youtu\.be/([^?]+)', link)
            if video_id_match:
                video_id = video_id_match.group(1)
        
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}'
        
        return link
    
    def _determine_ui_status(self, promotion: Dict[str, Any], today: date) -> str:
        """
        Определяет статус для отображения в UI.
        
        Args:
            promotion: Данные акции
            today: Текущая дата
            
        Returns:
            str: Статус для UI
        """
        status = promotion['status']
        start_date = promotion['start_date']
        end_date = promotion['end_date']
        
        # Завершенные акции
        if status == self.STATUS_FINISHED:
            return 'finished'
        
        # Активные акции
        if status == self.STATUS_ACTIVE:
            return 'active'
        
        # Опубликованные акции
        if status == self.STATUS_PUBLISHED:
            if start_date and today >= start_date:
                return 'active'  # Должна быть активной, но статус еще не обновился
            else:
                return 'published'  # Скоро стартует
        
        return 'unknown'
    
    def _get_sort_priority(self, promotion: Dict[str, Any]) -> tuple:
        """
        Получает приоритет сортировки для акции.
        
        Args:
            promotion: Данные акции
            
        Returns:
            tuple: Кортеж для сортировки
        """
        ui_status = promotion['ui_status']
        release_date = promotion['release_date'] or date.min
        
        # Приоритет: активные -> опубликованные -> завершенные
        if ui_status == 'active':
            priority = 1
        elif ui_status == 'published':
            priority = 2
        else:  # finished
            priority = 3
        
        # Внутри группы сортируем по дате релиза (новые первыми)
        return (priority, -release_date.toordinal())
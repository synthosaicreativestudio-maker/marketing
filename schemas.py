# -*- coding: utf-8 -*-
"""
Этот файл содержит Pydantic-модели для валидации входящих данных.
"""

from pydantic import BaseModel, constr
from typing import Literal

class AuthRequest(BaseModel):
    """Схема для валидации запроса на авторизацию от WebApp."""
    type: Literal['auth_request']
    code: constr(min_length=3)
    # Проверяет, что телефон состоит из 10 или 11 цифр
    phone: constr(regex=r'^\d{10,11}$')

class MenuSelection(BaseModel):
    """Схема для выбора пункта меню."""
    type: Literal['menu_selection']
    section: str

class SubsectionSelection(BaseModel):
    """Схема для выбора подпункта меню."""
    type: Literal['subsection_selection']
    section: str
    subsection: str

# Можно добавить и другие схемы по мере необходимости

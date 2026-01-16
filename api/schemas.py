"""
Pydantic схемы для валидации данных API.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ========== Appeals (Обращения) ==========

class AppealBase(BaseModel):
    """Базовая схема обращения"""
    partner_code: Optional[str] = None
    phone: Optional[str] = None
    fio: Optional[str] = None
    telegram_id: int
    status: str = "новое"


class AppealCreate(AppealBase):
    """Схема для создания обращения"""
    pass


class AppealResponse(AppealBase):
    """Схема ответа с обращением"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AppealUpdate(BaseModel):
    """Схема для обновления обращения"""
    status: Optional[str] = None
    partner_code: Optional[str] = None
    phone: Optional[str] = None
    fio: Optional[str] = None


# ========== Messages (Сообщения) ==========

class MessageBase(BaseModel):
    """Базовая схема сообщения"""
    message_type: str = Field(..., description="Тип: user, ai, specialist")
    message_text: str


class MessageCreate(MessageBase):
    """Схема для создания сообщения"""
    pass


class MessageResponse(MessageBase):
    """Схема ответа с сообщением"""
    id: int
    appeal_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ========== Specialist Responses (Ответы специалистов) ==========

class SpecialistResponseCreate(BaseModel):
    """Схема для создания ответа специалиста"""
    response_text: str
    specialist_name: Optional[str] = None


class SpecialistResponseResponse(BaseModel):
    """Схема ответа с ответом специалиста"""
    id: int
    appeal_id: int
    response_text: str
    specialist_name: Optional[str] = None
    sent_at: datetime
    
    class Config:
        from_attributes = True


# ========== Auth (Авторизация) ==========

class AdminLogin(BaseModel):
    """Схема для входа администратора"""
    username: str
    password: str


class AdminResponse(BaseModel):
    """Схема ответа с данными администратора"""
    id: int
    username: str
    role: str
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Схема ответа с токеном"""
    access_token: str
    token_type: str = "bearer"

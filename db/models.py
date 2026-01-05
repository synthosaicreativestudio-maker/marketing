"""
SQLAlchemy модели для обращений.
Идентичная структура к Google Sheets таблице обращений.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import Base


class Appeal(Base):
    """
    Таблица обращений.
    Соответствует структуре Google Sheets таблицы обращений.
    """
    __tablename__ = 'appeals'
    
    id = Column(Integer, primary_key=True, index=True)
    # Данные пользователя (колонки A-D в Google Sheets)
    partner_code = Column(String(50), nullable=True)  # Код партнера (колонка A)
    phone = Column(String(20), nullable=True)  # Телефон партнера (колонка B)
    fio = Column(String(200), nullable=True)  # ФИО партнера (колонка C)
    telegram_id = Column(Integer, nullable=False, index=True)  # Telegram ID (колонка D)
    
    # Статус обращения (колонка F)
    status = Column(String(50), default='новое', nullable=False, index=True)
    # Возможные значения: 'новое', 'в_работе', 'передано_специалисту', 'ответ_ии', 'решено'
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Связи с другими таблицами
    messages = relationship("AppealMessage", back_populates="appeal", cascade="all, delete-orphan", order_by="AppealMessage.created_at")
    responses = relationship("SpecialistResponse", back_populates="appeal", cascade="all, delete-orphan", order_by="SpecialistResponse.sent_at")
    
    def __repr__(self):
        return f"<Appeal(id={self.id}, telegram_id={self.telegram_id}, status={self.status})>"


class AppealMessage(Base):
    """
    Сообщения в обращении (история диалога).
    Соответствует колонке E (текст_обращений) в Google Sheets, но структурировано.
    """
    __tablename__ = 'appeal_messages'
    
    id = Column(Integer, primary_key=True, index=True)
    appeal_id = Column(Integer, ForeignKey('appeals.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Тип сообщения: 'user', 'ai', 'specialist'
    message_type = Column(String(20), nullable=False)
    
    # Текст сообщения
    message_text = Column(Text, nullable=False)
    
    # Временная метка
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связь с обращением
    appeal = relationship("Appeal", back_populates="messages")
    
    def __repr__(self):
        return f"<AppealMessage(id={self.id}, appeal_id={self.appeal_id}, type={self.message_type})>"


class SpecialistResponse(Base):
    """
    Ответы специалистов.
    Соответствует колонке G (специалист_ответ) в Google Sheets.
    """
    __tablename__ = 'specialist_responses'
    
    id = Column(Integer, primary_key=True, index=True)
    appeal_id = Column(Integer, ForeignKey('appeals.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Текст ответа специалиста
    response_text = Column(Text, nullable=False)
    
    # Имя специалиста (опционально)
    specialist_name = Column(String(100), nullable=True)
    
    # Временная метка отправки
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связь с обращением
    appeal = relationship("Appeal", back_populates="responses")
    
    def __repr__(self):
        return f"<SpecialistResponse(id={self.id}, appeal_id={self.appeal_id})>"

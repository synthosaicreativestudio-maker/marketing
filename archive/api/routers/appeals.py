"""
API endpoints для работы с обращениями.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from db.database import get_db
from db.models import Appeal, AppealMessage, SpecialistResponse
from api.schemas import (
    AppealCreate, AppealResponse, AppealUpdate,
    MessageCreate, MessageResponse,
    SpecialistResponseCreate, SpecialistResponseResponse
)
from datetime import datetime

router = APIRouter()


@router.get("/", response_model=List[AppealResponse])
def get_appeals(
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    telegram_id: Optional[int] = Query(None, description="Фильтр по Telegram ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Получить список обращений с фильтрами.
    
    - **status**: Фильтр по статусу (новое, в_работе, передано_специалисту, ответ_ии, решено)
    - **telegram_id**: Фильтр по Telegram ID пользователя
    - **skip**: Количество записей для пропуска (пагинация)
    - **limit**: Максимальное количество записей (до 1000)
    """
    query = db.query(Appeal)
    
    if status:
        query = query.filter(Appeal.status == status)
    if telegram_id:
        query = query.filter(Appeal.telegram_id == telegram_id)
    
    # Сортировка по дате создания (новые сначала)
    query = query.order_by(Appeal.created_at.desc())
    
    appeals = query.offset(skip).limit(limit).all()
    return appeals


@router.get("/{appeal_id}", response_model=AppealResponse)
def get_appeal(appeal_id: int, db: Session = Depends(get_db)):
    """
    Получить детали обращения по ID.
    """
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    return appeal


@router.post("/", response_model=AppealResponse)
def create_appeal(appeal: AppealCreate, db: Session = Depends(get_db)):
    """
    Создать новое обращение.
    """
    db_appeal = Appeal(**appeal.dict())
    db.add(db_appeal)
    db.commit()
    db.refresh(db_appeal)
    return db_appeal


@router.put("/{appeal_id}", response_model=AppealResponse)
def update_appeal(
    appeal_id: int,
    appeal_update: AppealUpdate,
    db: Session = Depends(get_db)
):
    """
    Обновить обращение.
    """
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    
    # Обновляем только переданные поля
    update_data = appeal_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(appeal, field, value)
    
    appeal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appeal)
    return appeal


@router.patch("/{appeal_id}/status")
def update_status(
    appeal_id: int,
    status: str = Query(..., description="Новый статус"),
    db: Session = Depends(get_db)
):
    """
    Изменить статус обращения.
    """
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    
    appeal.status = status
    appeal.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Статус обновлен", "status": status}


# ========== Messages (Сообщения) ==========

@router.get("/{appeal_id}/messages", response_model=List[MessageResponse])
def get_appeal_messages(appeal_id: int, db: Session = Depends(get_db)):
    """
    Получить все сообщения обращения.
    """
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    
    messages = db.query(AppealMessage).filter(
        AppealMessage.appeal_id == appeal_id
    ).order_by(AppealMessage.created_at.asc()).all()
    
    return messages


@router.post("/{appeal_id}/messages", response_model=MessageResponse)
def add_message(
    appeal_id: int,
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Добавить сообщение в обращение.
    """
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    
    db_message = AppealMessage(
        appeal_id=appeal_id,
        **message.dict()
    )
    db.add(db_message)
    
    # Обновляем время обновления обращения
    appeal.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_message)
    return db_message


# ========== Specialist Responses (Ответы специалистов) ==========

@router.post("/{appeal_id}/response", response_model=SpecialistResponseResponse)
def add_specialist_response(
    appeal_id: int,
    response: SpecialistResponseCreate,
    db: Session = Depends(get_db)
):
    """
    Добавить ответ специалиста к обращению.
    """
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    
    # Создаем ответ специалиста
    db_response = SpecialistResponse(
        appeal_id=appeal_id,
        **response.dict()
    )
    db.add(db_response)
    
    # Добавляем сообщение в историю
    db_message = AppealMessage(
        appeal_id=appeal_id,
        message_type="specialist",
        message_text=f"👨‍💼 СПЕЦИАЛИСТ: {response.response_text}"
    )
    db.add(db_message)
    
    # Обновляем статус на "в_работе" если еще не установлен
    if appeal.status not in ["в_работе", "решено"]:
        appeal.status = "в_работе"
    
    appeal.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_response)
    return db_response


@router.get("/{appeal_id}/responses", response_model=List[SpecialistResponseResponse])
def get_appeal_responses(appeal_id: int, db: Session = Depends(get_db)):
    """
    Получить все ответы специалистов по обращению.
    """
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    
    responses = db.query(SpecialistResponse).filter(
        SpecialistResponse.appeal_id == appeal_id
    ).order_by(SpecialistResponse.sent_at.desc()).all()
    
    return responses

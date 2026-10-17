from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_session_factory
from identity.dependencies import get_current_user
from identity.schemas import AuthenticatedUser
from models.product_state import LearningProgress, SavedItem


router = APIRouter(prefix="/me", tags=["my-data"])
ItemType = Literal["bible_verse", "dictionary_entry", "translation"]


class SavedItemResponse(BaseModel):
    item_type: ItemType
    item_key: str
    created_at: datetime


class SavedItemsResponse(BaseModel):
    count: int
    items: list[SavedItemResponse]


class ProgressUpdate(BaseModel):
    percent: int = Field(ge=0, le=100)
    completed: bool = False


class ProgressResponse(ProgressUpdate):
    lesson_id: str
    updated_at: datetime


class ProgressListResponse(BaseModel):
    count: int
    items: list[ProgressResponse]


def get_product_session() -> Iterator[Session]:
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="Account storage is not configured.")
    with factory() as session:
        yield session


def validate_saved_key(item_type: ItemType, item_key: str) -> None:
    pattern = {
        "bible_verse": r"[1-9]\d*:[1-9]\d*:[1-9]\d*",
        "dictionary_entry": r"[1-9]\d*",
        "translation": r"[a-f0-9]{64}",
    }[item_type]
    if not re.fullmatch(pattern, item_key):
        raise HTTPException(status_code=422, detail="Invalid saved-item key for this type.")


def saved_response(item: SavedItem) -> SavedItemResponse:
    return SavedItemResponse(item_type=item.item_type, item_key=item.item_key, created_at=item.created_at)


def progress_response(item: LearningProgress) -> ProgressResponse:
    return ProgressResponse(lesson_id=item.lesson_id, percent=item.percent,
                            completed=item.completed, updated_at=item.updated_at)


@router.get("/saved", response_model=SavedItemsResponse)
def list_saved_items(
    limit: int = Query(100, ge=1, le=500),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_product_session),
) -> SavedItemsResponse:
    try:
        rows = session.scalars(
            select(SavedItem).where(SavedItem.user_id == user.user_id)
            .order_by(SavedItem.created_at.desc(), SavedItem.id.desc()).limit(limit)
        ).all()
        return SavedItemsResponse(count=len(rows), items=[saved_response(row) for row in rows])
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Account storage is unavailable.") from exc


@router.put("/saved/{item_type}/{item_key}", response_model=SavedItemResponse)
def save_item(
    item_type: ItemType,
    item_key: str = Path(..., min_length=1, max_length=160),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_product_session),
) -> SavedItemResponse:
    validate_saved_key(item_type, item_key)
    selector = (SavedItem.user_id == user.user_id, SavedItem.item_type == item_type, SavedItem.item_key == item_key)
    try:
        item = session.scalar(select(SavedItem).where(*selector))
        if item is None:
            item = SavedItem(user_id=user.user_id, item_type=item_type, item_key=item_key)
            session.add(item)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                item = session.scalar(select(SavedItem).where(*selector))
                if item is None:
                    raise
            else:
                session.refresh(item)
        return saved_response(item)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="Account storage is unavailable.") from exc


@router.delete("/saved/{item_type}/{item_key}", status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_item(
    item_type: ItemType,
    item_key: str = Path(..., min_length=1, max_length=160),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_product_session),
) -> Response:
    validate_saved_key(item_type, item_key)
    try:
        item = session.scalar(select(SavedItem).where(
            SavedItem.user_id == user.user_id, SavedItem.item_type == item_type, SavedItem.item_key == item_key
        ))
        if item is not None:
            session.delete(item)
            session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="Account storage is unavailable.") from exc


@router.get("/progress", response_model=ProgressListResponse)
def list_progress(
    limit: int = Query(100, ge=1, le=500),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_product_session),
) -> ProgressListResponse:
    try:
        rows = session.scalars(
            select(LearningProgress).where(LearningProgress.user_id == user.user_id)
            .order_by(LearningProgress.updated_at.desc(), LearningProgress.id.desc()).limit(limit)
        ).all()
        return ProgressListResponse(count=len(rows), items=[progress_response(row) for row in rows])
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Account storage is unavailable.") from exc


@router.put("/progress/{lesson_id}", response_model=ProgressResponse)
def put_progress(
    update: ProgressUpdate,
    lesson_id: str = Path(..., min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_product_session),
) -> ProgressResponse:
    selector = (LearningProgress.user_id == user.user_id, LearningProgress.lesson_id == lesson_id)
    try:
        row = session.scalar(select(LearningProgress).where(*selector))
        if row is None:
            row = LearningProgress(user_id=user.user_id, lesson_id=lesson_id,
                                   percent=update.percent, completed=update.completed)
            session.add(row)
        else:
            row.percent = update.percent
            row.completed = update.completed
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            row = session.scalar(select(LearningProgress).where(*selector))
            if row is None:
                raise
            row.percent = update.percent
            row.completed = update.completed
            session.commit()
        session.refresh(row)
        return progress_response(row)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="Account storage is unavailable.") from exc

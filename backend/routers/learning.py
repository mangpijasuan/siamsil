from __future__ import annotations

from fastapi import APIRouter

from api_schemas import LearningGroupsResponse
from services.data_loader import get_store

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/groups", response_model=LearningGroupsResponse)
def learning_groups():
    store = get_store()
    groups = store.learning_groups()
    return {
        "count": sum(len(items) for items in groups.values()),
        "groups": groups,
        "note": "Only teacher-reviewed daily-use phrases are published. The parallel corpus is not auto-published as lessons.",
    }

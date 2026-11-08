from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.db import get_session
from backend.profile_service import get_or_create_profile, profile_to_schema, update_profile
from backend.schemas import ProfileIn

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileIn)
def read_profile(session: Session = Depends(get_session)):
    return profile_to_schema(get_or_create_profile(session))


@router.put("/profile", response_model=ProfileIn)
def write_profile(data: ProfileIn, session: Session = Depends(get_session)):
    return profile_to_schema(update_profile(session, data))

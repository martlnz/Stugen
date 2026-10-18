from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.db.models import User
from app.schemas.user import MeOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user

from fastapi import APIRouter, Depends, HTTPException
from msflib.account.router import account_router, profile_router, create_account
from msflib.auth.router import router as auth_router
from msflib.account.eventbus import EventName as AccountEventName
from msflib.eventbus import emitter
from sqlmodel import Session

from app import models
from app.actions import account_action, profile_action
from app.api import deps
from app.api.api_v1.endpoints import admin, documents, handwriting_profiles
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(
    auth_router(
        get_session=deps.get_session,
        get_keystore=deps.get_keystore,
        get_current_account=deps.get_current_account,
        account_type=models.Account,
        account_read_type=models.AccountRead,
        settings=settings,
        active_statuses=[models.AccountStatus.active, models.AccountStatus.online],
        prefix="",
        tags=["auth"],
    )
)

api_router.include_router(
    account_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        settings=settings,
        account_type=models.Account,
        profile_type=models.Profile,
        account_read_type=models.AccountRead,
        account_create_type=models.UserRegister,
        account_action=account_action,
        profile_action=profile_action,
        open_registration_path="/register",
        prefix="",
        tags=["accounts"],
    )
)


@api_router.post("/open", response_model=models.AccountRead, status_code=201, tags=["accounts"])
def create_account_open_alias(
    *,
    session: Session = Depends(deps.get_session),
    data: models.UserRegister,
) -> models.Account:
    """Open account registration alias (compatible with MSFLib standard /open endpoint)."""
    if not settings.scope("ACCOUNT").USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Open account registration is forbidden on this server",
        )
    account = create_account(
        session,
        data=data,
        account_action=account_action,
        settings=settings,
    )
    emitter.emit_optional(
        AccountEventName.ACCOUNT_CREATED,
        account,
        {"session": session, "data": data},
    )
    return account

api_router.include_router(
    profile_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        get_current_active_account=deps.get_current_active_account,
        settings=settings,
        profile_type=models.Profile,
        account_type=models.Account,
        profile_read_type=models.ProfileRead,
        prefix="/profiles",
        tags=["profiles"],
    )
)

api_router.include_router(admin.router, prefix="/admin")
api_router.include_router(handwriting_profiles.router, prefix="/handwriting-profiles", tags=["handwriting-profiles"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])

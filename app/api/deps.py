import logging

from msflib.api.deps import get_keystore_factory, get_session_factory
from msflib.auth.deps import get_account_dependencies

from ..core.config import settings
from ..db.session import engine
from ..models import Account, AccountStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Session
get_session = get_session_factory(engine)

# Redis Keystore (falls back to MapStore if Redis server is not found).
get_keystore = get_keystore_factory(
    redis_host=settings.REDIS_HOST,
    redis_password=settings.REDIS_PASSWORD,
    redis_port=int(settings.REDIS_PORT) if settings.REDIS_PORT else 6379,
)

account_dependencies = get_account_dependencies(
    AccountModel=Account,
    oauth_token_url=f"{settings.API_V1_STR}/login",
    secret_key=settings.SECRET_KEY,
    active_statuses=[AccountStatus.active, AccountStatus.online],
    session_dep=get_session,
    keystore_dep=get_keystore,
)

get_current_account = account_dependencies.get_current_account
get_current_account_or_none = account_dependencies.get_current_account_or_none
get_current_active_account = account_dependencies.get_current_active_account
get_current_active_superuser = account_dependencies.get_current_active_superuser
RoleCheck = account_dependencies.RoleCheck


from fastapi import Depends
from sqlmodel import Session


def get_current_tenant_id(session: Session = Depends(get_session)) -> int:
    from msflib.tenancy.resolver import resolve_default_tenant_id
    from ..actions import tenant_action
    
    tid = resolve_default_tenant_id(session, create_if_missing=False)
    if tid is None:
        tenant = tenant_action.ensure_default_tenant(session, settings=settings.scope("TENANCY"))
        return tenant.id
    return tid

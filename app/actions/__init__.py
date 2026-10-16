from msflib.account.actions import AccountAction, ProfileAction
from msflib.tenancy import TenantAction
from msflib.workspaces.actions import UserAction, WorkspaceAction

from ..core.config import settings
from ..models import (
    Account,
    AccountCreate,
    AccountUpdate,
    Profile,
    ProfileCreate,
    ProfileUpdate,
    Tenant,
    TenantCreate,
    TenantUpdate,
    User,
    UserCreate,
    UserUpdate,
    Workspace,
    WorkspaceCreate,
    WorkspaceUpdate,
    HandwritingProfile,
    HandwritingProfileCreate,
    HandwritingProfileUpdate,
    HandwritingSample,
    HandwritingSampleCreate,
    Document,
    DocumentCreate,
    DocumentUpdate,
)
from msflib.actions import ModelAction

tenant_action = TenantAction[Tenant, TenantCreate, TenantUpdate]()

profile_action = ProfileAction[Profile, ProfileCreate, ProfileUpdate]()

account_action = AccountAction[Account, AccountCreate, AccountUpdate](
    settings=settings, profile_action=profile_action
)

workspace_action = WorkspaceAction[Workspace, WorkspaceCreate, WorkspaceUpdate](settings=settings)

user_action = UserAction[User, UserCreate, UserUpdate]()

handwriting_profile_action = ModelAction[
    HandwritingProfile, HandwritingProfileCreate, HandwritingProfileUpdate
]()

handwriting_sample_action = ModelAction[
    HandwritingSample, HandwritingSampleCreate, HandwritingSampleCreate
]()

document_action = ModelAction[Document, DocumentCreate, DocumentUpdate]()

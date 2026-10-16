from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator
from msflib.account.models import AccountRole, AccountStatus, ProfileCreate


class UserRegister(BaseModel):
    """
    Public registration schema for new user sign-up.
    Enforces minimum 8-character passwords, matching password confirmation,
    normalizes email, and strictly defaults role to normal user (AccountRole.user)
    preventing any privilege escalation.
    """
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters.")
    password_confirm: str = Field(..., min_length=8, description="Password confirmation must match password.")
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: AccountRole = AccountRole.user
    status: AccountStatus = AccountStatus.active
    username: Optional[str] = None
    profile: Optional[ProfileCreate] = None

    @model_validator(mode="after")
    def validate_password_and_normalize(self) -> "UserRegister":
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match.")

        # Security: strictly enforce standard user role and active status for public sign-up
        self.role = AccountRole.user
        self.status = AccountStatus.active
        self.username = str(self.email).lower()

        # Build profile if name fields are provided
        if not self.profile:
            fname = (self.first_name or "").strip()
            lname = (self.last_name or "").strip()
            if self.full_name and self.full_name.strip() and not (fname or lname):
                parts = self.full_name.strip().split(" ", 1)
                fname = parts[0].strip()
                lname = parts[1].strip() if len(parts) > 1 else ""
            if fname or lname:
                self.profile = ProfileCreate(first_name=fname, last_name=lname)

        return self

import argparse
import logging
import os
import sys

from app.actions import account_action
from app.core.config import settings
from app.db.session import Session, engine
from app.models import AccountUpdate

logger = logging.getLogger("app.reset_superuser")


def reset_superuser_password(
    email: str | None = None,
    new_password: str | None = None,
    session: Session | None = None,
) -> bool:
    """Safely reset the administrator password in the database without data loss.

    - Uses MSFLib's AccountAction.update, which hashes the new password with bcrypt.
    - Preserves account ID, tenant, workspace memberships, documents, and handwriting profiles.
    - Never prints or logs the plain password or hashed password.
    """
    if email is not None:
        target_email = email.strip()
        if not target_email:
            logger.error("Specified administrator email is empty.")
            return False
    else:
        target_email = (settings.FIRST_SUPERUSER or "").strip()
        if not target_email:
            logger.error("No administrator email specified and FIRST_SUPERUSER is unset.")
            return False

    if new_password is not None:
        target_password = new_password.strip()
    else:
        target_password = (
            os.getenv("RESET_SUPERUSER_PASSWORD")
            or settings.FIRST_SUPERUSER_PASSWORD
            or ""
        ).strip()

    if not target_password:
        logger.error(
            "No new password provided. Supply --password or set FIRST_SUPERUSER_PASSWORD / RESET_SUPERUSER_PASSWORD."
        )
        return False

    if len(target_password) < 8:
        logger.error("Password must be at least 8 characters long.")
        return False

    if target_password in {"\\", "\\\\", "password", "12345678"}:
        logger.error("Password appears to be an invalid placeholder or insecure value.")
        return False

    def _execute(s: Session) -> bool:
        account = account_action.get_by_email(s, email=target_email)
        if not account:
            logger.error("Administrator account with email '%s' was not found in the database.", target_email)
            return False

        account_action.update(
            s,
            model=account,
            data=AccountUpdate(new_password=target_password),
        )
        logger.info("Successfully updated password for administrator '%s'.", target_email)
        return True

    if session is not None:
        return _execute(session)
    else:
        with Session(engine) as s:
            return _execute(s)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(
        description="Safely reset the HandWriteMe-AI administrator password."
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Administrator email (defaults to FIRST_SUPERUSER environment setting).",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="New password (defaults to FIRST_SUPERUSER_PASSWORD / RESET_SUPERUSER_PASSWORD env vars).",
    )
    args = parser.parse_args()

    success = reset_superuser_password(email=args.email, new_password=args.password)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()

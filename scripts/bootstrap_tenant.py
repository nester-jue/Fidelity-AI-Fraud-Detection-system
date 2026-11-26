"""Create the first organisation and an administrator (tenant deployments).

Run once per tenant before onboarding users, for example:

    python scripts/bootstrap_tenant.py --name "Example Insurer" --slug example \
        --admin-username example.admin --admin-password '<strong password>' \
        --admin-email admin@example.invalid

The script refuses to run in single-tenant mode unless --allow-single is passed.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.auth import get_password_hash  # noqa: E402
from backend.app.core.config import settings  # noqa: E402
from backend.app.models.sqlalchemy_models import Organisation, RoleEnum, User  # noqa: E402
from backend.app.services import tenant as tenant_service  # noqa: E402
from backend.app.services.db import SessionLocal, init_db  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--admin-username", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--allow-single", action="store_true", help="Allow bootstrapping while tenant isolation is disabled")
    args = parser.parse_args()

    if not settings.TENANT_ISOLATION_ENABLED and not args.allow_single:
        raise SystemExit("Set TENANT_ISOLATION_ENABLED=true (or pass --allow-single) before bootstrapping a tenant.")
    if len(args.admin_password) < settings.PASSWORD_MIN_LENGTH:
        raise SystemExit(f"Administrator password must be at least {settings.PASSWORD_MIN_LENGTH} characters.")

    init_db()
    token = tenant_service.set_tenant(tenant_service.PUBLIC_ACCESS)
    db = SessionLocal()
    try:
        org = db.query(Organisation).filter(Organisation.slug == args.slug).first()
        if not org:
            org = Organisation(name=args.name, slug=args.slug, is_active=True)
            db.add(org)
            db.commit()
            db.refresh(org)
        existing = db.query(User).filter(User.username == args.admin_username).first()
        if existing:
            raise SystemExit(f"User '{args.admin_username}' already exists; no changes made.")
        admin = User(
            username=args.admin_username,
            full_name=f"{args.name} Administrator",
            email=args.admin_email.strip().lower(),
            hashed_password=get_password_hash(args.admin_password),
            role=RoleEnum.SYSTEM_ADMIN,
            organisation_id=org.id,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Created organisation '{org.name}' (id={org.id}) and administrator '{admin.username}'.")
    finally:
        db.close()
        tenant_service.reset_tenant(token)


if __name__ == "__main__":
    main()

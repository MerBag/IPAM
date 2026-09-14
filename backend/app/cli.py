import argparse
import sys

from ipaddress import IPv4Network
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.enums import UserRole
from app.models import Prefix, User
from app.security import hash_password
from app.services.ipam import create_prefix


def seed() -> int:
    if not settings.initial_admin_username or not settings.initial_admin_password:
        print("INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD are required for seeding", file=sys.stderr)
        return 2
    if len(settings.initial_admin_password) < 12:
        print("INITIAL_ADMIN_PASSWORD must contain at least 12 characters", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.username == settings.initial_admin_username))
        if admin is None:
            admin = User(
                username=settings.initial_admin_username,
                password_hash=hash_password(settings.initial_admin_password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            db.flush()
            print(f"Created initial admin user: {admin.username}")
        else:
            print(f"Initial admin user already exists: {admin.username}")

        if settings.initial_prefix:
            network = IPv4Network(settings.initial_prefix, strict=True)
            existing = db.scalar(select(Prefix).where(Prefix.cidr == str(network)))
            if existing is None:
                create_prefix(
                    db,
                    cidr=str(network),
                    description="Initial managed prefix",
                    location=None,
                    actor=admin,
                )
                print(f"Created initial prefix: {network}")
            else:
                print(f"Initial prefix already exists: {network}")
        db.commit()
        return 0
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="merbag IPAM application maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("seed", help="Create the initial admin and prefix idempotently")
    args = parser.parse_args()
    if args.command == "seed":
        return seed()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

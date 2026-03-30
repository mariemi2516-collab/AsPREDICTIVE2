from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Usuario
from app.security import get_password_hash


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update an administrator user.")
    parser.add_argument("--email", required=True, help="Administrator email")
    parser.add_argument("--password", required=True, help="Administrator password")
    parser.add_argument("--name", default="Administrador", help="Administrator display name")
    parser.add_argument(
        "--organization-key",
        default="default",
        help="Organization key to assign to the administrator",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with SessionLocal() as db:
        user = db.scalar(select(Usuario).where(Usuario.email == args.email))

        if user is None:
            user = Usuario(
                nombre=args.name,
                email=args.email,
                password_hash=get_password_hash(args.password),
                rol="administrador",
                organization_key=args.organization_key,
                estado=True,
            )
            db.add(user)
            action = "created"
        else:
            user.nombre = args.name
            user.password_hash = get_password_hash(args.password)
            user.rol = "administrador"
            user.organization_key = args.organization_key
            user.estado = True
            action = "updated"

        db.commit()
        print(
            f"Administrator {action}: {user.email} "
            f"(organization={user.organization_key}, role={user.rol})"
        )


if __name__ == "__main__":
    main()

"""Seed a device credential for a farm and print its key once.

There is no self-service device-registration API yet, so an operator uses this
script to insert a ``devices`` row with a freshly generated, high-entropy
credential and print that credential exactly once. Copy the printed key and
configure it onto the device out-of-band; it is stored raw in the database and
is not recoverable in plaintext from any other output here.

Usage (local, against the compose Postgres)::

    export MW_DATABASE_URL="postgresql+psycopg://moo:moo@localhost:5433/mooternity"

    # Create a new farm and a device under it:
    python -m scripts.seed_device --farm-name "North Pasture"

    # Or attach a device to an existing farm:
    python -m scripts.seed_device --farm-id 1b4e...uuid...

Running this against the private RDS instance (as a one-off Fargate task) is
documented in ``docs/deployment.md`` -> "Seeding a device credential".
"""

from __future__ import annotations

import argparse
import secrets
import sys
import uuid

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Device, Farm


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a device credential for a farm.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--farm-id",
        type=uuid.UUID,
        help="Attach the device to this existing farm (UUID).",
    )
    group.add_argument(
        "--farm-name",
        type=str,
        help="Create a new farm with this name and attach the device to it.",
    )
    return parser.parse_args(argv)


def seed_device(*, farm_id: uuid.UUID | None, farm_name: str | None) -> tuple[Device, str]:
    """Insert a device with a generated key; return the device and the raw key.

    Exactly one of ``farm_id`` / ``farm_name`` must be given. The raw key is
    returned so the caller can print it once; it is also what lands in the
    column, so there is nothing else to recover it from.
    """
    device_key = secrets.token_urlsafe(32)

    with SessionLocal() as session:
        if farm_name is not None:
            farm = Farm(name=farm_name)
            session.add(farm)
            session.flush()
        else:
            farm = session.scalar(select(Farm).where(Farm.id == farm_id))
            if farm is None:
                raise SystemExit(f"No farm with id {farm_id}.")

        device = Device(farm_id=farm.id, device_key=device_key)
        session.add(device)
        session.commit()
        session.refresh(device)

    return device, device_key


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    device, device_key = seed_device(farm_id=args.farm_id, farm_name=args.farm_name)

    print("Device seeded.")
    print(f"  device id : {device.id}")
    print(f"  farm id   : {device.farm_id}")
    print(f"  device key: {device_key}")
    print()
    print("Copy the device key now — it is stored raw and not printed again.")
    print("Configure it on the device as: Authorization: Bearer <device key>")
    return 0


if __name__ == "__main__":
    sys.exit(main())

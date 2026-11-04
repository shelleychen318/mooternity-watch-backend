"""Shared pytest fixtures and model factories for database-backed tests.

The ``db_session`` fixture skips when no database is reachable (keeping the
suite green without a Postgres service), creates the schema once per session,
and wraps each test in a transaction that is rolled back for isolation.

The ``make_*`` factories build the entity graph (farm -> device/user -> event
-> alert) so individual tests only construct what is unique to them.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.db import Base, engine
from app.models import Alert, Device, Event, Farm, User


@pytest.fixture(scope="session")
def _schema() -> Iterator[None]:
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError:
        pytest.skip("No database reachable; model tests skipped.")
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(_schema: None) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        # A failed flush (e.g. an IntegrityError test) may have already rolled
        # the transaction back; only roll back if it is still active.
        if transaction.is_active:
            transaction.rollback()
        connection.close()


# --- Model factories --------------------------------------------------------
# Each factory inserts (flushes) and returns the entity, creating any required
# parents when they are not supplied.


def make_farm(session: Session, *, name: str = "Test Farm") -> Farm:
    farm = Farm(name=name)
    session.add(farm)
    session.flush()
    return farm


def make_device(
    session: Session,
    *,
    farm: Farm | None = None,
    device_key: str = "dev_test_pi5",
) -> Device:
    farm = farm or make_farm(session)
    device = Device(farm_id=farm.id, device_key=device_key)
    session.add(device)
    session.flush()
    return device


def make_user(
    session: Session,
    *,
    farm: Farm | None = None,
    name: str = "Test User",
    phone: str = "+15550000000",
    email: str | None = None,
    role: str | None = None,
) -> User:
    farm = farm or make_farm(session)
    user = User(farm_id=farm.id, name=name, phone=phone, email=email, role=role)
    session.add(user)
    session.flush()
    return user


def make_event(
    session: Session,
    *,
    farm: Farm | None = None,
    device: Device | None = None,
    event_id: str = "evt_test_001",
    event_type: str = "calving_detected",
) -> Event:
    if device is None:
        device = make_device(session, farm=farm)
    farm = farm or session.get(Farm, device.farm_id)
    event = Event(
        event_id=event_id,
        farm_id=farm.id,
        device_id=device.id,
        event_type=event_type,
    )
    session.add(event)
    session.flush()
    return event


def make_alert(
    session: Session,
    *,
    event: Event | None = None,
) -> Alert:
    event = event or make_event(session)
    alert = Alert(farm_id=event.farm_id, event_id=event.id)
    session.add(alert)
    session.flush()
    return alert

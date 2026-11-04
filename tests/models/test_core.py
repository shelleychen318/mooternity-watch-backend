from __future__ import annotations

import uuid

from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session

from tests.conftest import make_device, make_farm, make_user


def test_uuid_primary_keys(db_session: Session, test_engine: Engine):
    insp = inspect(test_engine)
    for table in ("farms", "devices", "users"):
        pk = insp.get_pk_constraint(table)
        assert pk["constrained_columns"] == ["id"]
        id_col = next(c for c in insp.get_columns(table) if c["name"] == "id")
        assert "UUID" in str(id_col["type"]).upper()


def test_server_defaults_populate(db_session: Session):
    farm = make_farm(db_session)
    assert isinstance(farm.id, uuid.UUID)
    assert farm.created_at is not None


def test_entities_scope_to_their_farm(db_session: Session):
    farm = make_farm(db_session)
    device = make_device(db_session, farm=farm)
    user = make_user(db_session, farm=farm)
    assert device.farm_id == farm.id
    assert user.farm_id == farm.id

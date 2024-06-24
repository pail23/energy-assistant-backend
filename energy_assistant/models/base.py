"""Base class for Energy Assistant data models."""

import uuid
from collections.abc import Mapping
from typing import ClassVar

from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import CHAR, TypeDecorator

convention: Mapping[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type:ignore
        """Load the dialect implementation."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect) -> str | None:  # type:ignore
        """Process the bind parameters."""
        if value is None:
            return None
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value).hex
        # hexstring
        return f"{value.int:32x}"

    def process_result_value(self, value, dialect):  # type:ignore
        """Process the result value."""
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for energy assistant data models."""

    __abstract__ = True
    metadata = MetaData(naming_convention=convention)  # type: ignore

    type_annotation_map: ClassVar[dict] = {
        uuid.UUID: GUID,
    }

    def __repr__(self) -> str:
        """Representation of a data model object."""
        columns = ", ".join([f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_")])
        return f"<{self.__class__.__name__}({columns})>"

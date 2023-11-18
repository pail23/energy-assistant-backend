"""Schemas for home measurement api."""

from pydantic import BaseModel


class CreateModelResponse(BaseModel):
    """API Request for create the forecast model."""

    model: str


class TuneModelResponse(BaseModel):
    """API Request for tuning the forecast model."""

    model: str

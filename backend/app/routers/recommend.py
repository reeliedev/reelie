"""Recommendation routes (content-based)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import recommend as reco
from app.db import get_session
from app.serialize import normalize_product

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/similar/{handle}")
def similar(handle: str, session: Session = Depends(get_session)):
    return reco.similar_creators(handle, session)


@router.get("/using")
def using(brand: str, name: str, exclude: str | None = None,
          session: Session = Depends(get_session)):
    key = normalize_product(brand, name)
    return reco.creators_using(key, session, exclude_handle=exclude)

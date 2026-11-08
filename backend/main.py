"""Uvicorn entry point: python -m uvicorn backend.main:app --port 8000."""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel  # <--- Make sure this is imported
from typing import Optional
from sqlalchemy import text

from .transport_api import app

__all__ = ["app"]

class ActionPayload(BaseModel):
    action: Optional[str] = "tick"
    minutes: Optional[int] = 1
    trip_id: Optional[str] = None
    vehicle_id: Optional[str] = None
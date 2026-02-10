"""Pydantic models for Local Sidekick API."""

from pydantic import BaseModel, field_validator
from typing import Optional


class UserRegister(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SettingsUpdate(BaseModel):
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    max_notifications_per_day: Optional[int] = None
    camera_enabled: Optional[bool] = None
    sync_enabled: Optional[bool] = None


class SettingsResponse(BaseModel):
    working_hours_start: str = "09:00"
    working_hours_end: str = "19:00"
    max_notifications_per_day: int = 6
    camera_enabled: bool = True
    sync_enabled: bool = True


class FocusBlock(BaseModel):
    start: str
    end: str
    duration_min: int


class NotificationEntry(BaseModel):
    type: str
    time: str
    action: str


class DailyStatistics(BaseModel):
    date: str
    focused_minutes: float
    drowsy_minutes: float
    distracted_minutes: float
    away_minutes: float
    idle_minutes: float
    notification_count: int = 0
    notification_accepted: int = 0
    focus_blocks: list[FocusBlock] = []
    notifications: list[NotificationEntry] = []
    top_apps: list[str] = []


class ReportRequest(BaseModel):
    date: str
    focused_minutes: float
    drowsy_minutes: float
    distracted_minutes: float
    away_minutes: float
    idle_minutes: float
    notification_count: int = 0
    focus_blocks: list[FocusBlock] = []
    notifications: list[NotificationEntry] = []
    top_apps: list[str] = []


class DailyReport(BaseModel):
    summary: str
    highlights: list[str]
    concerns: list[str]
    tomorrow_tip: str

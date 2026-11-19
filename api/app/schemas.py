from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    is_admin: bool
    created_at: datetime


class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user: UserOut


class SeriesOut(BaseModel):
    id: int
    title: str
    speaker: str
    category: str
    description: str | None = None
    sort_order: int
    item_count: int


class SeriesDetail(BaseModel):
    series: SeriesOut
    items: list["ItemOut"]


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    series_id: int
    title: str
    index_no: int
    duration_s: float
    size_bytes: int


class ProgressIn(BaseModel):
    position_s: float


class ProgressOut(BaseModel):
    item_id: int
    position_s: float


class RequestIn(BaseModel):
    title: str
    notes: str | None = None


class RequestStatusIn(BaseModel):
    status: str


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    notes: str
    status: str
    created_at: datetime


SeriesDetail.model_rebuild()
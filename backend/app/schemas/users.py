import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str


class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False
    full_name: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserUpdate(UserBase):
    email: Optional[EmailStr]
    password: Optional[str] = Field(min_length=8, max_length=40)


class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserUpdateMe(BaseModel):
    email: Optional[EmailStr]
    full_name: Optional[str]


class UpdatePassword(BaseModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


class UserPublic(UserBase):
    id: uuid.UUID
    oauth_provider: Optional[str]


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int

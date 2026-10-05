from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str
    password: str


class FeedbackIn(BaseModel):
    message: str = Field(min_length=3, max_length=5000)
    category: Literal["general", "bug", "feature", "usability"] = "general"
    page_path: str | None = Field(default=None, max_length=500)
    external_key: str | None = Field(default=None, max_length=100)


class FeedbackUpdate(BaseModel):
    status: str | None = None
    tags: str | None = Field(default=None, max_length=500)
    assignee: str | None = Field(default=None, max_length=254)


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    problem: str | None = None
    acceptance_criteria: str | None = None
    open_questions: str | None = None
    status: str | None = None


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)

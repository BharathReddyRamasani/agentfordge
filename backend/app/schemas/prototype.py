"""Agent output contract: Product/UX & Prototype Build Agent (AGENT 3)."""

from typing import Literal

from pydantic import BaseModel, Field


class ScreenField(BaseModel):
    name: str
    label: str
    type: Literal["text", "email", "password", "date", "select", "textarea", "number"] = "text"
    options: list[str] = []


class StatItem(BaseModel):
    label: str
    value: str


class ScreenSection(BaseModel):
    type: Literal["hero", "stats", "cards", "list", "form", "detail", "chart"] = "cards"
    title: str = ""
    subtitle: str = ""
    items: list[str] = []
    fields: list[ScreenField] = []
    stats: list[StatItem] = []


class Screen(BaseModel):
    name: str
    title: str
    sections: list[ScreenSection] = []


class Theme(BaseModel):
    primary_color: str = "#4f46e5"
    accent_color: str = "#0ea5e9"
    background_color: str = "#f8fafc"


class PrototypeSpec(BaseModel):
    """Specification from which a runnable interactive HTML prototype is synthesized."""

    app_name: str = Field(min_length=1)
    tagline: str = ""
    theme: Theme = Theme()
    screens: list[Screen] = Field(min_length=2)
    navigation: list[str] = []
    user_flow: list[str] = []
    features: list[str] = []
    sample_data: dict = {}
    roles: list[str] = []

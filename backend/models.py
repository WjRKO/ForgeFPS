from typing import Optional
from pydantic import BaseModel, Field


class ChatMessageInput(BaseModel):
    message: str
    session_id: Optional[str] = None


class BuildInput(BaseModel):
    budget: int = Field(ge=300, le=15000)
    use_case: str
    resolution: str
    notes: Optional[str] = ""


class TrackComponentsInput(BaseModel):
    group: str
    components: list


class TrackInput(BaseModel):
    url: str
    target_price: Optional[float] = None


class ManualPriceInput(BaseModel):
    price: float


class TargetInput(BaseModel):
    target_price: float


class SearchInput(BaseModel):
    query: str


class PushSubInput(BaseModel):
    subscription: dict


class SpecsInput(BaseModel):
    data: Optional[dict] = None
    health: Optional[dict] = None
    startup: Optional[list] = None
    benchmark: Optional[dict] = None


class GoalInput(BaseModel):
    budget: int = Field(default=800, ge=50, le=10000)
    goal: str = "gaming e streaming"


class PcSpecsInput(BaseModel):
    data: dict
    source: Optional[str] = "manual"


class FpsInput(BaseModel):
    game: str
    resolution: str = "1080p"


class RoleInput(BaseModel):
    role: str


class TelemetryInput(BaseModel):
    sample: dict


class ProfileInput(BaseModel):
    game_name: str
    tweak_ids: list = []

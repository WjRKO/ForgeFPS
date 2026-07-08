from typing import Optional
from pydantic import BaseModel, Field


class ChatMessageInput(BaseModel):
    message: str
    session_id: Optional[str] = None
    lang: Optional[str] = "it"


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


class TitleInput(BaseModel):
    title: str


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
    games: Optional[list] = None
    running_apps: Optional[list] = None


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


class NetResultInput(BaseModel):
    result: dict


class ProfileInput(BaseModel):
    game_name: str
    tweak_ids: list = []


class AlertInput(BaseModel):
    enabled: bool = True
    cpu_max: int = Field(default=90, ge=40, le=110)
    gpu_max: int = Field(default=85, ge=40, le=110)


class PrematchInput(BaseModel):
    close_apps: list = []
    set_power: bool = True

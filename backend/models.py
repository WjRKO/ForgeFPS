from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatMessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=64)
    lang: Optional[str] = Field(default="it", max_length=5)


class BuildInput(BaseModel):
    budget: int = Field(ge=300, le=15000)
    use_case: str
    resolution: str
    notes: Optional[str] = ""


class TrackComponentsInput(BaseModel):
    group: str
    components: list[dict[str, Any]]


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
    subscription: dict[str, Any]


class SpecsInput(BaseModel):
    data: Optional[dict[str, Any]] = None
    health: Optional[dict[str, Any]] = None
    # Accetta sia list[str] (client legacy come .exe v0.7.x) sia list[dict] (client
    # ricchi). Normalizzato server-side in _normalize_startup prima di scrivere.
    startup: Optional[list[Any]] = None
    benchmark: Optional[dict[str, Any]] = None
    games: Optional[list[str]] = None
    running_apps: Optional[list[str]] = None
    boost_session: Optional[dict[str, Any]] = None


class GoalInput(BaseModel):
    budget: int = Field(default=800, ge=50, le=10000)
    goal: str = "gaming e streaming"


class PcSpecsInput(BaseModel):
    data: dict[str, Any]
    source: Optional[str] = "manual"


class FpsInput(BaseModel):
    game: str
    resolution: str = "1080p"


class RoleInput(BaseModel):
    role: str


class TelemetryInput(BaseModel):
    sample: dict[str, Any]


class NetResultInput(BaseModel):
    result: dict[str, Any]


class ProfileInput(BaseModel):
    game_name: str
    tweak_ids: list[str] = []


class AlertInput(BaseModel):
    enabled: bool = True
    cpu_max: int = Field(default=90, ge=40, le=110)
    gpu_max: int = Field(default=85, ge=40, le=110)


class PrematchInput(BaseModel):
    close_apps: list[str] = []
    set_power: bool = True


class BoosterInput(BaseModel):
    close_apps: list[str] = []
    set_power: bool = True
    boost_priority: bool = True
    purge_ram: bool = True


class BenchExplainInput(BaseModel):
    lang: str = "it"


class ReportPhaseInput(BaseModel):
    phase: str = Field(pattern="^(before|after)$")

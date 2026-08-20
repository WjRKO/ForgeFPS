from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


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
    services_audit: Optional[list[Any]] = None
    benchmark: Optional[dict[str, Any]] = None
    games: Optional[list[str]] = None
    running_apps: Optional[list[str]] = None
    boost_session: Optional[dict[str, Any]] = None

    @field_validator("startup", "services_audit", "games", "running_apps", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        # PS 5.1 ConvertTo-Json srotola gli array a 1 elemento in scalari -> wrap
        if v is None or isinstance(v, list):
            return v
        return [v]


class GoalInput(BaseModel):
    budget: int = Field(default=800, ge=50, le=10000)
    goal: str = "gaming e streaming"


class PcSpecsInput(BaseModel):
    data: dict[str, Any]
    source: Optional[str] = "manual"


class FpsInput(BaseModel):
    game: str
    resolution: str = "1080p"


class FpsUpgradeInput(BaseModel):
    game: str
    resolution: str = "1080p"
    upgrades: list[str] = []


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


class LabStartInput(BaseModel):
    risk_level: str = Field(default="medium", pattern="^(safe|medium)$")
    run_seconds: int = Field(default=90, ge=30, le=180)
    include_reboot: bool = True
    # Schema appaiato ON/OFF (default). False torna al confronto a blocchi:
    # meta' del tempo, ma con un effetto minimo rilevabile molto piu' alto.
    paired: bool = True


class LabRunInput(BaseModel):
    phase: str = Field(pattern="^(baseline|test|pair_on|pair_off|warmup|synergy_off|synergy_on|validation|recheck)$")
    tweak_id: Optional[str] = Field(default=None, max_length=50)
    run: dict[str, Any]


class AgentDiagInput(BaseModel):
    """Evento diagnostico dell'agent (non telemetria d'uso).

    Serve a decidere con i dati invece che a intuito: per esempio se la GUI web
    fallisca davvero abbastanza da giustificare il fallback WinForms, che oggi
    e' 451 righe che duplicano un sottoinsieme dell'interfaccia vera.
    """
    event: str = Field(pattern="^[a-z_]{3,40}$")
    detail: Optional[dict[str, Any]] = None


class LabCheckInput(BaseModel):
    reason: str = Field(pattern="^(bios_xmp|bios_rebar|bios_dual|driver_update|manual)$")


class LabEventInput(BaseModel):
    type: str = Field(max_length=40)
    data: Optional[dict[str, Any]] = None

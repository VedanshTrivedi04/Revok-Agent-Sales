"""Pydantic parameter models with min/max bounds for all rules (R3-02)."""

from pydantic import BaseModel, Field


class R01UsageDropParams(BaseModel):
    drop_pct: float = Field(default=30.0, ge=5.0, le=90.0)


class R02MeetingGapParams(BaseModel):
    gap_days: int = Field(default=21, ge=7, le=180)
    future_window: int = Field(default=14, ge=1, le=60)


class R03NoReplyParams(BaseModel):
    min_emails: int = Field(default=2, ge=1, le=10)
    wait_days: int = Field(default=7, ge=1, le=60)


class R04RenewalNearNoPlanParams(BaseModel):
    window: int = Field(default=60, ge=10, le=180)
    stage_idle_days: int = Field(default=30, ge=7, le=90)


class R05ChampionRiskParams(BaseModel):
    silent_days: int = Field(default=30, ge=7, le=180)
    signal_window: int = Field(default=60, ge=7, le=180)
    min_conf: float = Field(default=0.6, ge=0.0, le=1.0)


class R06NegativeSentimentParams(BaseModel):
    min_signals: int = Field(default=2, ge=1, le=10)
    window_days: int = Field(default=21, ge=7, le=90)
    escalation_conf: float = Field(default=0.7, ge=0.0, le=1.0)


class R07CompetitorMentionParams(BaseModel):
    window_days: int = Field(default=45, ge=7, le=180)
    min_conf: float = Field(default=0.6, ge=0.0, le=1.0)


class R08SeatUnderuseParams(BaseModel):
    min_util: float = Field(default=0.5, ge=0.05, le=0.95)
    min_seats: int = Field(default=5, ge=1, le=1000)


class R09SingleThreadedParams(BaseModel):
    max_contacts: int = Field(default=1, ge=1, le=5)


class R10NoNextStepParams(BaseModel):
    idle_days: int = Field(default=14, ge=3, le=90)


class R11PricingBudgetParams(BaseModel):
    window_days: int = Field(default=45, ge=7, le=180)
    min_conf: float = Field(default=0.6, ge=0.0, le=1.0)


class X01SeatSaturationParams(BaseModel):
    threshold: float = Field(default=0.9, ge=0.5, le=1.5)


class X02UsageGrowthParams(BaseModel):
    growth_pct: float = Field(default=30.0, ge=5.0, le=200.0)
    min_current_au: float = Field(default=10.0, ge=1.0, le=500.0)


class X03UpgradeIntentParams(BaseModel):
    window_days: int = Field(default=45, ge=7, le=180)
    min_conf: float = Field(default=0.6, ge=0.0, le=1.0)
    explicit_conf: float = Field(default=0.85, ge=0.5, le=1.0)


class X04NewStakeholdersParams(BaseModel):
    min_new_contacts: int = Field(default=2, ge=1, le=10)
    window_days: int = Field(default=30, ge=7, le=90)


class X05RenewalStrongHealthParams(BaseModel):
    renewal_window: int = Field(default=90, ge=10, le=180)
    min_seat_util: float = Field(default=0.8, ge=0.5, le=1.0)

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


BudgetStyle = Literal["budget", "midrange", "luxury"]


class LineItem(BaseModel):
  model_config = ConfigDict(extra="forbid")
  name: str
  amount: float = Field(..., ge=0)

  @field_validator("name")
  @classmethod
  def non_empty(cls, v: str) -> str:
    v = v.strip()
    if not v:
      raise ValueError("line item name must not be empty")
    return v


class CategoryEstimate(BaseModel):
  model_config = ConfigDict(extra="forbid")

  low: float = Field(..., ge=0)
  base: float = Field(..., ge=0)
  high: float = Field(..., ge=0)

  line_items: List[LineItem] = Field(default_factory=list)
  assumptions: List[str] = Field(default_factory=list)
  confidence: float = Field(..., ge=0, le=1)

  @field_validator("base")
  @classmethod
  def base_ge_low(cls, v: float, info):
    low = info.data.get("low")
    if low is not None and v < low:
      raise ValueError("base must be >= low")
    return v

  @field_validator("high")
  @classmethod
  def high_ge_base(cls, v: float, info):
    base = info.data.get("base")
    if base is not None and v < base:
      raise ValueError("high must be >= base")
    return v


class Meta(BaseModel):
  model_config = ConfigDict(extra="forbid")

  trip_title: str
  origin: str
  destination: str
  start_date: str
  end_date: str
  days: Optional[int] = Field(default=None, ge=0)
  nights: Optional[int] = Field(default=None, ge=0)
  travelers: int = Field(..., ge=1)
  currency: str
  budget_style: BudgetStyle


class Assumptions(BaseModel):
  model_config = ConfigDict(extra="forbid")

  meals_per_day: Optional[float] = Field(default=None, ge=0)
  local_transport_days_ratio: Optional[float] = Field(default=None, ge=0, le=1)
  activity_days_ratio: Optional[float] = Field(default=None, ge=0, le=1)
  notes: List[str] = Field(default_factory=list)


class Estimates(BaseModel):
  model_config = ConfigDict(extra="forbid")

  flights: CategoryEstimate
  stay: CategoryEstimate
  transport: CategoryEstimate
  food: CategoryEstimate
  activities: CategoryEstimate
  docs_fees: CategoryEstimate


class Totals(BaseModel):
  model_config = ConfigDict(extra="forbid")

  low: float = Field(..., ge=0)
  base: float = Field(..., ge=0)
  high: float = Field(..., ge=0)
  per_person_base: float = Field(..., ge=0)

  @field_validator("high")
  @classmethod
  def high_ge_base(cls, v: float, info):
    base = info.data.get("base")
    if base is not None and v < base:
      raise ValueError("totals.high must be >= totals.base")
    return v


class Contingency(BaseModel):
  model_config = ConfigDict(extra="forbid")

  buffer_rate_used: float = Field(..., ge=0, le=1)
  base_subtotal: float = Field(..., ge=0)
  buffer_amount: float = Field(..., ge=0)
  total_with_buffer: float = Field(..., ge=0)


class ValidationBlock(BaseModel):
  model_config = ConfigDict(extra="forbid")

  validated: bool
  issues: List[str] = Field(default_factory=list)
  recommendations: List[str] = Field(default_factory=list)
  confidence: float = Field(..., ge=0, le=1)


class TravelBudgetEstimateV1(BaseModel):
  model_config = ConfigDict(extra="forbid")

  meta: Meta
  assumptions: Assumptions
  estimates: Estimates
  totals: Totals
  contingency: Contingency
  validation: ValidationBlock

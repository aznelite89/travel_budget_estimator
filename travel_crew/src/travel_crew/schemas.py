from __future__ import annotations

from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


BudgetStyle = Literal["budget", "midrange", "luxury"]


def _coerce_float(v: Union[int, float, str]) -> float:
  if isinstance(v, (int, float)):
    return float(v)
  s = str(v).strip()
  if not s:
    raise ValueError("expected a number")
  return float(s)


class LineItem(BaseModel):
  model_config = ConfigDict(extra="ignore")
  name: str
  amount: float = Field(..., ge=0)

  @field_validator("name")
  @classmethod
  def non_empty(cls, v: str) -> str:
    v = v.strip()
    if not v:
      raise ValueError("line item name must not be empty")
    return v

  @field_validator("amount", mode="before")
  @classmethod
  def amount_float(cls, v: Union[int, float, str]) -> float:
    return _coerce_float(v)


class SampleItem(BaseModel):
  model_config = ConfigDict(extra="ignore")

  label: str
  price_text: Optional[str] = None
  currency: Optional[str] = None
  url: Optional[str] = None


class CategoryEstimate(BaseModel):
  model_config = ConfigDict(extra="ignore")

  low: float = Field(..., ge=0)
  base: float = Field(..., ge=0)
  high: float = Field(..., ge=0)

  line_items: List[LineItem] = Field(default_factory=list)
  assumptions: List[str] = Field(default_factory=list)
  confidence: float = Field(..., ge=0, le=1)
  samples: List[SampleItem] = Field(default_factory=list)

  @field_validator("low", "base", "high", "confidence", mode="before")
  @classmethod
  def numeric_float(cls, v: Union[int, float, str]) -> float:
    return _coerce_float(v)

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
  model_config = ConfigDict(extra="ignore")

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

  @field_validator("travelers", mode="before")
  @classmethod
  def travelers_int(cls, v: Union[int, str]) -> int:
    if isinstance(v, int):
      return v
    return int(float(str(v).strip()))

  @field_validator("budget_style", mode="before")
  @classmethod
  def budget_style_lower(cls, v: Union[str, object]) -> str:
    s = str(v).strip().lower()
    if s not in ("budget", "midrange", "luxury"):
      raise ValueError("budget_style must be one of: budget, midrange, luxury")
    return s

  @field_validator("days", "nights", mode="before")
  @classmethod
  def optional_int(cls, v: Union[int, str, None]) -> Optional[int]:
    if v is None or v == "":
      return None
    if isinstance(v, int):
      return v
    return int(float(str(v).strip()))


class Assumptions(BaseModel):
  model_config = ConfigDict(extra="ignore")

  meals_per_day: Optional[float] = Field(default=None, ge=0)
  local_transport_days_ratio: Optional[float] = Field(default=None, ge=0, le=1)
  activity_days_ratio: Optional[float] = Field(default=None, ge=0, le=1)
  notes: List[str] = Field(default_factory=list)

  @field_validator("meals_per_day", "local_transport_days_ratio", "activity_days_ratio", mode="before")
  @classmethod
  def optional_float(cls, v: Union[int, float, str, None]) -> Optional[float]:
    if v is None or v == "":
      return None
    return _coerce_float(v)


class Estimates(BaseModel):
  model_config = ConfigDict(extra="ignore")

  flights: CategoryEstimate
  stay: CategoryEstimate
  transport: CategoryEstimate
  food: CategoryEstimate
  activities: CategoryEstimate
  docs_fees: CategoryEstimate


class Totals(BaseModel):
  model_config = ConfigDict(extra="ignore")

  low: float = Field(..., ge=0)
  base: float = Field(..., ge=0)
  high: float = Field(..., ge=0)
  per_person_base: float = Field(..., ge=0)

  @field_validator("low", "base", "high", "per_person_base", mode="before")
  @classmethod
  def numeric_float(cls, v: Union[int, float, str]) -> float:
    return _coerce_float(v)

  @field_validator("high")
  @classmethod
  def high_ge_base(cls, v: float, info):
    base = info.data.get("base")
    if base is not None and v < base:
      raise ValueError("totals.high must be >= totals.base")
    return v


class Contingency(BaseModel):
  model_config = ConfigDict(extra="ignore")

  buffer_rate_used: float = Field(..., ge=0, le=1)
  base_subtotal: float = Field(..., ge=0)
  buffer_amount: float = Field(..., ge=0)
  total_with_buffer: float = Field(..., ge=0)

  @field_validator("buffer_rate_used", "base_subtotal", "buffer_amount", "total_with_buffer", mode="before")
  @classmethod
  def numeric_float(cls, v: Union[int, float, str]) -> float:
    return _coerce_float(v)


class ValidationBlock(BaseModel):
  model_config = ConfigDict(extra="ignore")

  validated: bool
  issues: List[str] = Field(default_factory=list)
  recommendations: List[str] = Field(default_factory=list)
  confidence: float = Field(..., ge=0, le=1)

  @field_validator("confidence", mode="before")
  @classmethod
  def confidence_float(cls, v: Union[int, float, str]) -> float:
    return _coerce_float(v)


class TravelBudgetEstimateV1(BaseModel):
  model_config = ConfigDict(extra="ignore")

  meta: Meta
  assumptions: Assumptions
  estimates: Estimates
  totals: Totals
  contingency: Contingency
  validation: ValidationBlock

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Type

from amadeus import Client, ResponseError
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class AmadeusFlightOffersInput(BaseModel):
  """Input schema for Amadeus flight offers search."""

  origin: str = Field(..., description="Origin IATA code, e.g. KUL")
  destination: str = Field(..., description="Destination IATA code, e.g. NRT")
  start_date: str = Field(..., description="Departure date YYYY-MM-DD")
  end_date: str = Field(..., description="Return date YYYY-MM-DD")
  travelers: int = Field(..., ge=1, description="Number of adult travelers")
  currency: str = Field(..., description="Currency code, e.g. MYR")


class AmadeusFlightOffersTool(BaseTool):
  """Query Amadeus Flight Offers Search for real flight price samples."""

  name: str = "amadeus_flight_offers"
  description: str = (
    "Use this tool to fetch sample round-trip flight offers and prices from the "
    "Amadeus Self-Service APIs. Always provide origin/destination IATA codes, "
    "departure/return dates, number of travelers, and currency. The tool returns "
    "JSON with query_used and samples that you must map into estimates.flights."
  )
  args_schema: Type[BaseModel] = AmadeusFlightOffersInput

  def __init__(self, **data: Any):
    super().__init__(**data)

    api_key = os.getenv("AMADEUS_API_KEY")
    api_secret = os.getenv("AMADEUS_API_SECRET")
    env = (os.getenv("AMADEUS_ENV") or "test").strip().lower()
    hostname = "production" if env.startswith("prod") else "test"

    self._config_error: str | None = None
    if not api_key or not api_secret:
      self._config_error = (
        "Amadeus credentials missing: set AMADEUS_API_KEY and AMADEUS_API_SECRET. "
        "Using heuristic estimates instead."
      )
      self._client = None
    else:
      self._client = Client(
        client_id=api_key,
        client_secret=api_secret,
        hostname=hostname,
      )

  def _run(
    self,
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int,
    currency: str,
  ) -> str:
    query_used: Dict[str, Any] = {
      "origin": origin,
      "destination": destination,
      "start_date": start_date,
      "end_date": end_date,
      "travelers": travelers,
      "currency": currency,
    }

    if self._config_error or self._client is None:
      return json.dumps(
        {
          "query_used": query_used,
          "error": self._config_error or "Amadeus client not initialised.",
        },
        ensure_ascii=False,
      )

    try:
      response = self._client.shopping.flight_offers_search.get(
        originLocationCode=origin,
        destinationLocationCode=destination,
        departureDate=start_date,
        returnDate=end_date,
        adults=travelers,
        currencyCode=currency,
        max=10,
      )
    except ResponseError as e:
      return json.dumps(
        {
          "query_used": query_used,
          "error": f"Amadeus Flight Offers Search failed: {e}",
        },
        ensure_ascii=False,
      )
    except Exception as e:  # pragma: no cover - defensive
      return json.dumps(
        {
          "query_used": query_used,
          "error": f"Unexpected error calling Amadeus: {e}",
        },
        ensure_ascii=False,
      )

    offers: List[Dict[str, Any]] = []
    if isinstance(response.data, list):
      offers = [o for o in response.data if isinstance(o, dict)]

    samples: List[Dict[str, Any]] = []
    for offer in offers[:5]:
      price = offer.get("price", {}) or {}
      total = price.get("grandTotal") or price.get("total")
      currency_code = price.get("currency") or currency

      label_parts: List[str] = []
      validating = offer.get("validatingAirlineCodes") or []
      if validating:
        label_parts.append(str(validating[0]))

      itineraries = offer.get("itineraries") or []
      if itineraries:
        first_itin = itineraries[0] or {}
        segments = first_itin.get("segments") or []
        if segments:
          first_seg = segments[0] or {}
          last_seg = segments[-1] or {}
          o_code = (first_seg.get("departure") or {}).get("iataCode")
          d_code = (last_seg.get("arrival") or {}).get("iataCode")
          if o_code and d_code:
            label_parts.append(f"{o_code}-{d_code}")

      label = " ".join(label_parts).strip() or "Flight offer"

      samples.append(
        {
          "label": label,
          "price_text": str(total) if total is not None else None,
          "currency": str(currency_code) if currency_code else None,
          "url": None,
        }
      )

    payload: Dict[str, Any] = {
      "query_used": query_used,
      "offer_count": len(offers),
      "samples": samples,
    }

    return json.dumps(payload, ensure_ascii=False)


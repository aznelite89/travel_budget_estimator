from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Type

from crewai.tools import BaseTool
from crewai_tools import SerperDevTool
from pydantic import BaseModel, Field


class _DomainSearchInput(BaseModel):
    """Generic input schema for domain-scoped Serper search tools."""

    query: str = Field(
        ...,
        description=(
            "Natural language search query. The tool will automatically constrain "
            "results to a specific site (e.g. cheapflights.com.my or agoda.com)."
        ),
    )


class _BaseDomainSerperTool(BaseTool):
    """Base helper for Serper-backed, domain-scoped search tools."""

    args_schema: Type[BaseModel] = _DomainSearchInput
    _domain: str

    def __init__(self, **data):
        super().__init__(**data)
        # Instantiate the underlying SerperDevTool once per tool instance.
        self._serper = SerperDevTool()

    def _run(self, query: str) -> str:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return (
                "Serper-based web search is unavailable because SERPER_API_KEY is not "
                "set in the environment. Fall back to heuristic estimates and clearly "
                "note this limitation in your assumptions."
            )

        site_query = f"site:{self._domain} {query}".strip()

        try:
            result = self._serper.run(search_query=site_query)
        except Exception as e:
            return json.dumps(
                {
                    "query_used": site_query,
                    "error": (
                        f"Serper-based web search for domain '{self._domain}' failed "
                        f"with error: {e}. Fall back to heuristic estimates and clearly "
                        "note this limitation in your assumptions."
                     ),
                },
                ensure_ascii=False,
            )

        payload: Dict[str, Any] = {"query_used": site_query}

        data: Any = result
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except Exception:
                data = None
        elif not isinstance(result, dict):
            # Best-effort stringification for unexpected shapes
            try:
                data = json.loads(json.dumps(result, default=str))
            except Exception:
                data = None

        samples: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            for item in (data.get("organic") or [])[:5]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or ""
                link = item.get("link") or item.get("url") or ""
                snippet = item.get("snippet") or item.get("description") or ""
                price_text = None
                if isinstance(item.get("price"), (str, int, float)):
                    price_text = str(item["price"])

                if title or link or snippet:
                    samples.append(
                        {
                            "label": str(title) if title else snippet[:80],
                            "price_text": price_text,
                            "currency": None,
                            "url": str(link) if link else None,
                        }
                    )

        if samples:
            payload["samples"] = samples
        else:
            payload["raw"] = result

        return json.dumps(payload, ensure_ascii=False)


class CheapflightsSearchTool(_BaseDomainSerperTool):
    """Search Cheapflights via Serper for flight pricing signals."""

    name: str = "cheapflights_search"
    description: str = (
        "Use this tool to search Cheapflights (cheapflights.com.my) for real flight "
        "price ranges between given origins and destinations and travel dates. "
        "Provide queries like 'Kuala Lumpur to Tokyo flights April 10-18 2026 MYR'."
    )
    _domain: str = "cheapflights.com.my"


class AgodaStaySearchTool(_BaseDomainSerperTool):
    """Search Agoda via Serper for accommodation pricing signals."""

    name: str = "agoda_stay_search"
    description: str = (
        "Use this tool to search Agoda (agoda.com) for real accommodation nightly "
        "price ranges in a destination for specific dates and budget style. "
        "Provide queries like 'Tokyo hotels April 10-18 2026 midrange MYR'."
    )
    _domain: str = "agoda.com"


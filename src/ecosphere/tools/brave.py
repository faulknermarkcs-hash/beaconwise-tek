from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def brave_web_search(query: str, count: int = 5) -> Dict[str, Any]:
    key = os.getenv("BRAVE_API_KEY", "").strip()
    if not key:
        return {"ok": False, "error": "missing_BRAVE_API_KEY"}

    params = {"q": query, "count": int(count)}
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": key,
    }

    try:
        r = requests.get(BRAVE_ENDPOINT, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return {"ok": False, "error": f"http_{r.status_code}", "body": r.text[:500]}
        data = r.json()

        # Normalize to a simple list of results
        results: List[Dict[str, str]] = []
        for item in (data.get("web", {}).get("results", []) or [])[:count]:
            results.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "snippet": str(item.get("description", "")),
                }
            )

        return {"ok": True, "query": query, "results": results}
    except Exception as e:
        return {"ok": False, "error": f"exception:{type(e).__name__}", "detail": str(e)[:200]}

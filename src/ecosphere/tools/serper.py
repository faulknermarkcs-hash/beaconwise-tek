from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


SERPER_ENDPOINT = "https://google.serper.dev/search"


def serper_search(query: str, num: int = 5) -> Dict[str, Any]:
    key = os.getenv("SERPER_API_KEY", "").strip()
    if not key:
        return {"ok": False, "error": "missing_SERPER_API_KEY"}

    payload = {"q": query, "num": int(num)}
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}

    try:
        r = requests.post(SERPER_ENDPOINT, json=payload, headers=headers, timeout=15)
        if r.status_code != 200:
            return {"ok": False, "error": f"http_{r.status_code}", "body": r.text[:500]}
        data = r.json()

        results: List[Dict[str, str]] = []
        for item in (data.get("organic", []) or [])[:num]:
            results.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("link", "")),
                    "snippet": str(item.get("snippet", "")),
                }
            )

        return {"ok": True, "query": query, "results": results}
    except Exception as e:
        return {"ok": False, "error": f"exception:{type(e).__name__}", "detail": str(e)[:200]}

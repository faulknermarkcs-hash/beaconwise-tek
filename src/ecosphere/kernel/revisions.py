from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ecosphere.utils.stable import stable_hash


@dataclass(frozen=True)
class Revision:
    step: Optional[int]
    text: str
    text_hash16: str


def append_revision(payload: Dict[str, Any], step: Optional[int], text: str) -> Dict[str, Any]:
    new_payload = dict(payload)
    hist: List[Dict[str, Any]] = list(new_payload.get("revision_history", []))

    text_hash16 = stable_hash(text)[:16]
    hist.append({"step": step, "text_hash16": text_hash16})
    new_payload["revision_history"] = hist
    return new_payload


def render_revision_block(payload: Dict[str, Any]) -> str:
    hist = payload.get("revision_history", [])[-10:]
    if not hist:
        return ""
    lines = ["Revisions applied (latest first):"]
    for item in reversed(hist):
        step = item.get("step")
        h = item.get("text_hash16", "")
        if step is None:
            lines.append(f"- (revision hash {h})")
        else:
            lines.append(f"- Step {step}: (revision hash {h})")
    return "\n".join(lines)

"""ecosphere.deployment.mode — Brick 11 deployment mode helpers."""

from __future__ import annotations

import os


def deployment_mode() -> str:
    return (os.getenv("ECOSPHERE_DEPLOYMENT_MODE") or "saas").lower()

from __future__ import annotations

import os


def env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


class Settings:
    PROVIDER = env("ECOSPHERE_PROVIDER", "mock").lower()
    MODEL = env("ECOSPHERE_MODEL", "mock-llm")

    EMBEDDINGS = env("ECOSPHERE_EMBEDDINGS", "local").lower()
    EMBEDDINGS_MODEL = env("ECOSPHERE_EMBEDDINGS_MODEL", "local-mini")

    STAGE2_THRESHOLD = float(env("ECOSPHERE_STAGE2_THRESHOLD", "0.50"))

    ALIGN_FAST = float(env("ECOSPHERE_ALIGN_FAST", "0.85"))
    ALIGN_STANDARD = float(env("ECOSPHERE_ALIGN_STANDARD", "0.90"))
    ALIGN_HIGH = float(env("ECOSPHERE_ALIGN_HIGH", "0.95"))

    TOKENLEN_FAST = int(env("ECOSPHERE_TOKENLEN_FAST", "4"))
    TOKENLEN_STANDARD = int(env("ECOSPHERE_TOKENLEN_STANDARD", "4"))
    TOKENLEN_HIGH = int(env("ECOSPHERE_TOKENLEN_HIGH", "6"))

    EPACK_STORE_PATH = env("ECOSPHERE_EPACK_STORE_PATH", ".ecosphere_epacks.jsonl")
    PERSIST_EPACKS = env("ECOSPHERE_PERSIST_EPACKS", "1") == "1"

    REDACT_MODE = env("ECOSPHERE_REDACT_MODE", "hash")  # off|hash



    # Citation governance

    CITATION_VERIFY = env("ECOSPHERE_CITATION_VERIFY", "0") == "1"
    CITATION_VERIFY_MAX = int(env("ECOSPHERE_CITATION_VERIFY_MAX", "5"))
    CITATION_VERIFY_TIMEOUT_S = int(env("ECOSPHERE_CITATION_VERIFY_TIMEOUT_S", "8"))

    REQUIRE_EVIDENCE_CITATIONS = env("ECOSPHERE_REQUIRE_EVIDENCE_CITATIONS", "1") == "1"
    AUTO_APPEND_CITATION_NOTICE = env("ECOSPHERE_AUTO_APPEND_CITATION_NOTICE", "1") == "1"

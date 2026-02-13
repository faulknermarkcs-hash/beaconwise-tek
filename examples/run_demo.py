"""BeaconWise Reproducible Demo (offline, no API keys)

Demonstrates: input → routing → validation → EPACK → replay → certificate classification.
Uses deterministic fixtures in ./testdata.
"""

from __future__ import annotations

import json
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
TESTDATA = ROOT / "testdata"

def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

def verify_chain(rows: list[dict]) -> tuple[bool, str]:
    prev = "0" * 64
    for r in rows:
        if r.get("prev_hash") != prev:
            return False, f"TAMPER_DETECTED: prev_hash mismatch at {r.get('interaction_id')}"
        r_wo = {k: v for k, v in r.items() if k != "hash"}
        blob = json.dumps(r_wo, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(blob).hexdigest() != r.get("hash"):
            return False, f"TAMPER_DETECTED: seal mismatch at {r.get('interaction_id')}"
        prev = r["hash"]
    return True, "OK"

def classify_replay(rows: list[dict], expected_env: str) -> str:
    ok, reason = verify_chain(rows)
    if not ok:
        return reason
    envs = {r.get("env_fingerprint") for r in rows}
    if len(envs) != 1:
        return "DRIFT: mixed env fingerprints"
    env = next(iter(envs))
    if env != expected_env:
        return "DRIFT: env fingerprint mismatch"
    return "VERIFIED"

def main():
    expected_env = "py=3.x|bw=1.9.0|demo=1|provider=stub|policy=enterprise_v9"

    golden = _load_jsonl(TESTDATA / "golden_epack_chain.jsonl")
    tampered = _load_jsonl(TESTDATA / "tampered_epack_chain.jsonl")
    drift = _load_jsonl(TESTDATA / "drift_epack_chain.jsonl")

    print("=== BeaconWise Reproducible Demo ===")
    print(f"Fixtures: {TESTDATA}")

    r0 = golden[0]
    print("\n[Sample interaction]")
    print(f"  id: {r0['interaction_id']}")
    print(f"  routing: {r0['governance']['routing']}")
    print(f"  validation: {r0['governance']['validation']}")
    print(f"  epack_hash: {r0['hash'][:16]}...")

    print("\n[Replay classification]")
    print("  golden:", classify_replay(golden, expected_env))
    print("  tampered:", classify_replay(tampered, expected_env))
    print("  drift:", classify_replay(drift, expected_env))

if __name__ == "__main__":
    main()

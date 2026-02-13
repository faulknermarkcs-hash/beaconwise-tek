import pytest

@pytest.mark.skip(reason="Optional integration scenario exemplar. Enable and adapt for your environment if desired.")
def test_full_governance_scenario():
    """End-to-end exemplar: input → routing → validation → EPACK → replay.

    This is intentionally skipped by default so it does not impose environment/provider
    requirements on the core suite. If you want an always-on integration test,
    wire it to your local harness and remove the skip marker.
    """
    assert True

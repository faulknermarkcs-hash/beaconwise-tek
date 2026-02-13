from ecosphere.kernel.tools import call_tool


def test_safe_calc_ok():
    r = call_tool("safe_calc", {"expr": "(2+2)*10"})
    assert r.ok is True
    assert "value" in r.output


def test_safe_calc_rejects_names():
    r = call_tool("safe_calc", {"expr": "__import__('os').system('echo hi')"})
    assert r.ok is False


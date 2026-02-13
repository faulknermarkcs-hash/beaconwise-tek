from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict

from ecosphere.utils.stable import stable_hash
from ecosphere.tools.brave import brave_web_search
from ecosphere.tools.serper import serper_search


@dataclass
class ToolResult:
    ok: bool
    tool: str
    args_hash: str
    output: Dict[str, Any]


def _args_hash(tool: str, args: Dict[str, Any]) -> str:
    # Deterministic binding for EPACK auditability
    return stable_hash({"tool": tool, "args": args})


# ============================================================
# Tool: safe_calc (deterministic, sandboxed)
# ============================================================

def safe_calc(expr: str) -> ToolResult:
    """
    Safe calculator: allows digits and basic operators only.
    Uses AST-based evaluation — no eval().
    """
    import ast
    import operator

    allowed = set("0123456789.+-*/() ")
    args_h = _args_hash("safe_calc", {"expr": expr})

    if not isinstance(expr, str) or not expr.strip():
        return ToolResult(ok=False, tool="safe_calc", args_hash=args_h, output={"error": "empty_expr"})

    if any(ch not in allowed for ch in expr):
        return ToolResult(ok=False, tool="safe_calc", args_hash=args_h, output={"error": "invalid_chars"})

    _OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def _eval_node(node):
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval_node(node.operand))
        raise ValueError(f"unsupported_node:{type(node).__name__}")

    try:
        tree = ast.parse(expr.strip(), mode="eval")
        val = _eval_node(tree)
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            return ToolResult(ok=False, tool="safe_calc", args_hash=args_h, output={"error": "nonfinite"})
        return ToolResult(ok=True, tool="safe_calc", args_hash=args_h, output={"value": float(val)})
    except ZeroDivisionError:
        return ToolResult(ok=False, tool="safe_calc", args_hash=args_h, output={"error": "division_by_zero"})
    except Exception:
        return ToolResult(ok=False, tool="safe_calc", args_hash=args_h, output={"error": "eval_failed"})


# ============================================================
# Tool: web_search_brave (Brave Search API)
# ============================================================

def web_search_brave(query: str, count: int = 5) -> ToolResult:
    q = (query or "").strip()
    c = int(count) if isinstance(count, (int, float, str)) else 5
    c = max(1, min(10, c))  # limit for determinism + cost control

    args = {"query": q, "count": c}
    args_h = _args_hash("web_search_brave", args)

    if not q:
        return ToolResult(ok=False, tool="web_search_brave", args_hash=args_h, output={"ok": False, "error": "empty_query"})

    out = brave_web_search(query=q, count=c)

    # keep payload small and consistent
    if isinstance(out, dict) and "results" in out and isinstance(out["results"], list):
        out["results"] = out["results"][:c]

    return ToolResult(ok=bool(out.get("ok")), tool="web_search_brave", args_hash=args_h, output=out if isinstance(out, dict) else {"ok": False, "error": "bad_response"})


# ============================================================
# Tool: web_search_serper (Google Serper API)
# ============================================================

def web_search_serper(query: str, num: int = 5) -> ToolResult:
    q = (query or "").strip()
    n = int(num) if isinstance(num, (int, float, str)) else 5
    n = max(1, min(10, n))  # limit

    args = {"query": q, "num": n}
    args_h = _args_hash("web_search_serper", args)

    if not q:
        return ToolResult(ok=False, tool="web_search_serper", args_hash=args_h, output={"ok": False, "error": "empty_query"})

    out = serper_search(query=q, num=n)

    if isinstance(out, dict) and "results" in out and isinstance(out["results"], list):
        out["results"] = out["results"][:n]

    return ToolResult(ok=bool(out.get("ok")), tool="web_search_serper", args_hash=args_h, output=out if isinstance(out, dict) else {"ok": False, "error": "bad_response"})


# ============================================================
# Aliases (engine.py expects brave_search/serper_search)
# ============================================================

def brave_search(q: str, count: int = 5) -> ToolResult:
    # Alias wrapper: normalize to underlying implementation
    return web_search_brave(query=q, count=count)


def serper_search_tool(q: str, num: int = 5) -> ToolResult:
    # Alias wrapper: normalize to underlying implementation
    return web_search_serper(query=q, num=num)


# ============================================================
# Allowlist + dispatcher
# ============================================================

ALLOWLIST = {
    # calc
    "safe_calc": safe_calc,

    # canonical names (your original)
    "web_search_brave": web_search_brave,
    "web_search_serper": web_search_serper,

    # aliases (engine.py)
    "brave_search": brave_search,
    "serper_search": serper_search_tool,
}


def _get_str(args: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        if k in args and args[k] is not None:
            return str(args[k])
    return ""


def _get_int(args: Dict[str, Any], default: int, *keys: str) -> int:
    for k in keys:
        if k in args and args[k] is not None:
            try:
                return int(args[k])
            except Exception:
                return default
    return default


def call_tool(tool: str, args: Dict[str, Any]) -> ToolResult:
    """
    Single choke point for all tools.
    Must remain allowlist-based.
    """
    if tool not in ALLOWLIST:
        return ToolResult(
            ok=False,
            tool=tool,
            args_hash=_args_hash(tool, args or {}),
            output={"error": "tool_not_allowed"},
        )

    args = args or {}

    # --- safe_calc ---
    if tool == "safe_calc":
        expr = _get_str(args, "expr")
        return safe_calc(expr)

    # --- brave search ---
    if tool in ("web_search_brave", "brave_search"):
        q = _get_str(args, "q", "query")
        c = _get_int(args, 5, "count", "num")
        # dispatch to canonical underlying function for consistent tool naming/hashing
        if tool == "brave_search":
            return brave_search(q=q, count=c)
        return web_search_brave(query=q, count=c)

    # --- serper search ---
    if tool in ("web_search_serper", "serper_search"):
        q = _get_str(args, "q", "query")
        n = _get_int(args, 5, "num", "count")
        if tool == "serper_search":
            return serper_search_tool(q=q, num=n)
        return web_search_serper(query=q, num=n)

    # Should be unreachable due to allowlist
    return ToolResult(ok=False, tool=tool, args_hash=_args_hash(tool, args), output={"error": "not_implemented"})

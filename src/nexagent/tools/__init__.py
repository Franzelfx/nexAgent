"""Built-in example tools for the agent."""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """Return the current UTC time. Useful for time-aware tasks."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely and return the result.

    Args:
        expression: A mathematical expression like '2 + 2' or '(3 * 4) / 2'.
    """
    import ast
    import operator as op

    allowed_ops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.Mod: op.mod,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](_eval(node.operand))
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    tree = ast.parse(expression, mode="eval")
    result = _eval(tree)
    return str(result)


# Registry: add new tools here and they are auto-discovered by the graph
ALL_TOOLS = [get_current_time, calculator]

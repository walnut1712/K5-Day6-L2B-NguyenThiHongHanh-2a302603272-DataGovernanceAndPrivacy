"""Small, safe evaluator for the declarative T09 privacy policy."""
from __future__ import annotations

import ast
from collections.abc import Mapping


_DECISION_PRECEDENCE = {"GO": 0, "REWORK": 1, "HOLD": 2}


def _value(node: ast.AST, case: Mapping):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "null":
            return None
        if node.id in ("true", "True"):
            return True
        if node.id in ("false", "False"):
            return False
        return case.get(node.id)
    if isinstance(node, ast.Attribute):
        path = []
        current = node
        while isinstance(current, ast.Attribute):
            path.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            raise ValueError(f"unsupported policy field path: {ast.dump(node)}")
        path.append(current.id)
        result = case
        for part in reversed(path):
            result = result.get(part) if isinstance(result, Mapping) else None
        return result
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = [_value(item, case) for item in node.elts]
        return set(values) if isinstance(node, ast.Set) else values
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _value(node.operand, case)
    if isinstance(node, ast.BoolOp):
        values = (_value(item, case) for item in node.values)
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
    if isinstance(node, ast.Compare):
        left = _value(node.left, case)
        for op, comparator in zip(node.ops, node.comparators):
            right = _value(comparator, case)
            if isinstance(op, ast.Eq):
                matched = left == right
            elif isinstance(op, ast.NotEq):
                matched = left != right
            elif isinstance(op, ast.In):
                matched = left in right
            elif isinstance(op, ast.NotIn):
                matched = left not in right
            elif isinstance(op, ast.Is):
                matched = left is right
            elif isinstance(op, ast.IsNot):
                matched = left is not right
            elif isinstance(op, ast.Gt):
                matched = left is not None and left > right
            elif isinstance(op, ast.GtE):
                matched = left is not None and left >= right
            elif isinstance(op, ast.Lt):
                matched = left is not None and left < right
            elif isinstance(op, ast.LtE):
                matched = left is not None and left <= right
            else:
                raise ValueError(f"unsupported policy comparison: {type(op).__name__}")
            if not matched:
                return False
            left = right
        return True
    raise ValueError(f"unsupported policy expression: {ast.dump(node)}")


def matches(condition: str, case: Mapping) -> bool:
    """Evaluate the policy's intentionally small expression language."""
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid policy condition {condition!r}") from exc
    return bool(_value(tree.body, case))


def decide_case(case: Mapping, policy: Mapping) -> dict:
    rules = policy.get("rules")
    if not isinstance(rules, list):
        raise ValueError("privacy policy must contain a rules list")

    applicable = []
    market = case.get("market")
    market_covered = False
    for rule in rules:
        required = ("id", "markets", "when", "decision", "reason_code", "source")
        missing = [key for key in required if key not in rule]
        if missing:
            raise ValueError(f"privacy policy rule is missing fields {missing}: {rule!r}")
        if "*" not in rule["markets"] and market not in rule["markets"]:
            continue
        if market in rule["markets"]:
            market_covered = True
        status = str(rule["decision"]).upper()
        if status not in _DECISION_PRECEDENCE:
            raise ValueError(f"invalid decision {status!r} in rule {rule['id']}")
        if matches(str(rule["when"]), case):
            applicable.append(rule)

    status = max(
        (str(rule["decision"]).upper() for rule in applicable),
        key=lambda decision: _DECISION_PRECEDENCE[decision],
        default="GO",
    )
    reason_codes = list(dict.fromkeys(rule["reason_code"] for rule in applicable))
    if not reason_codes:
        reason_codes = ["NO_MATCHING_RISK"]
    risk_flags = [c for c in reason_codes if c != "NO_MATCHING_RISK"]
    if not market_covered:
        risk_flags.append("NO_MARKET_RULES")
    if (case.get("transfer") or {}).get("cross_border"):
        risk_flags.insert(0, "CROSS_BORDER_TRANSFER")
    sources = [
        f"{rule['id']}: {rule['source'].get('doc', '')} {rule['source'].get('ref', '')}".strip()
        for rule in applicable
    ]
    return {
        "decision": status,
        "reason_codes": ";".join(reason_codes),
        "rule_ids": ";".join(rule["id"] for rule in applicable) or "NONE",
        "source_refs": ";".join(sources) or "none",
        "risk_flags": ";".join(dict.fromkeys(risk_flags)),
        "score": {"GO": 0.0, "REWORK": 0.7, "HOLD": 1.0}[status],
    }

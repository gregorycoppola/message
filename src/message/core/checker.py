"""
Grammar for .logic files.

Validates semantic representation files structurally.
"""

import re
from dataclasses import dataclass


@dataclass
class CheckError:
    line: int
    message: str


def check_file(filepath: str) -> list[CheckError]:
    """Check a .logic file for structural validity."""
    errors = []
    entities = {}
    bound_vars = {}
    saw_query = False

    with open(filepath) as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Nothing after query
        if saw_query:
            errors.append(CheckError(i, "Content after query line"))
            continue

        # Query: ? pred(...) or ? not pred(...)
        if line.startswith("? "):
            saw_query = True
            query = line[2:].strip()
            if query.startswith("not "):
                query = query[4:].strip()
            errors.extend(_check_pred(query, i, entities, {}))
            continue

        # Entity declaration: entity NAME : e
        if line.startswith("entity "):
            parts = line.split()
            if len(parts) < 4 or parts[2] != ":":
                errors.append(CheckError(i, "Bad entity syntax: expected 'entity NAME : e'"))
                continue
            name = parts[1]
            typ = parts[3]
            if name in entities:
                errors.append(CheckError(i, f"Duplicate entity: {name}"))
            entities[name] = typ
            continue

        # Rule: rule [bindings] (weight): premises -> conclusion
        if line.startswith("rule"):
            errors.extend(_check_rule(line, i, entities))
            continue

        # Fact: pred(...) or not pred(...)
        fact = line
        if fact.startswith("not "):
            fact = fact[4:].strip()
        if "(" in fact:
            errors.extend(_check_pred(fact, i, entities, {}))
            continue

        errors.append(CheckError(i, f"Unrecognized statement: {line}"))

    if not saw_query:
        errors.append(CheckError(len(lines), "Missing query (? ...) at end"))

    return errors


def _check_pred(text: str, line_num: int, entities: dict, bound_vars: dict) -> list[CheckError]:
    """Check a predicate call.
    
    Formats:
      pred()                           — zero-arg proposition
      pred(role: value, role: value)   — named roles
      pred(arg1, arg2)                 — positional args (legacy)
    """
    errors = []

    # Zero-argument proposition
    match = re.match(r'(\w+)\(\s*\)', text)
    if match:
        return errors

    # Predicate with arguments
    match = re.match(r'(\w+)\((.+)\)', text, re.DOTALL)
    if not match:
        errors.append(CheckError(line_num, f"Bad predicate syntax: {text}"))
        return errors

    args_str = match.group(2)
    args = _split_args(args_str)
    scope = {**entities, **bound_vars}

    for arg in args:
        arg = arg.strip()
        
        # Named role: role: value
        if ":" in arg:
            role_name, value = arg.split(":", 1)
            role_name = role_name.strip()
            value = value.strip()

            if not role_name:
                errors.append(CheckError(line_num, "Empty role name"))
                continue

            # Nested predicate
            if "(" in value:
                errors.extend(_check_pred(value, line_num, entities, bound_vars))
            # Entity or variable reference
            elif value not in scope:
                errors.append(CheckError(line_num, f"Unknown value: {value}"))
        
        # Positional argument (legacy)
        else:
            if arg not in scope:
                errors.append(CheckError(line_num, f"Unknown argument: {arg}"))

    return errors


def _check_rule(line: str, line_num: int, entities: dict) -> list[CheckError]:
    """Check a rule.
    
    Formats:
      rule [x:e, y:e]: premise & premise -> conclusion
      rule [x:e] (0.7): premise -> conclusion
      rule: premise -> conclusion  (ground rule)
    """
    errors = []
    bound_vars = {}

    rest = line[4:].strip()  # strip "rule"

    # Parse optional variable bindings [x:e, y:e]
    if rest.startswith("["):
        depth = 0
        end = 0
        for i, ch in enumerate(rest):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end == 0:
            errors.append(CheckError(line_num, "Unmatched [ in rule bindings"))
            return errors

        bindings_str = rest[1:end]
        rest = rest[end + 1:].strip()

        for binding in _split_args(bindings_str):
            binding = binding.strip()
            if ":" not in binding:
                errors.append(CheckError(line_num, f"Bad binding: {binding}"))
                continue
            var, typ = binding.split(":", 1)
            var = var.strip()
            typ = typ.strip()
            if not var:
                errors.append(CheckError(line_num, "Empty variable name"))
                continue
            bound_vars[var] = typ

    # Parse optional weight (0.7)
    if rest.startswith("("):
        try:
            weight_end = rest.index(")")
            weight_str = rest[1:weight_end].strip()
            float(weight_str)
            rest = rest[weight_end + 1:].strip()
        except (ValueError, IndexError):
            errors.append(CheckError(line_num, "Bad rule weight"))

    # Strip leading colon
    if rest.startswith(":"):
        rest = rest[1:].strip()

    # Must have ->
    if "->" not in rest:
        errors.append(CheckError(line_num, "Rule missing ->"))
        return errors

    premise_str, conclusion_str = rest.split("->", 1)

    # Check premises
    for pred_text in _split_on_ampersand(premise_str):
        pred_text = pred_text.strip()
        if pred_text.startswith("not "):
            pred_text = pred_text[4:].strip()
        if "(" in pred_text:
            errors.extend(_check_pred(pred_text, line_num, entities, bound_vars))

    # Check conclusion
    conc = conclusion_str.strip()
    if conc.startswith("not "):
        conc = conc[4:].strip()
    if "(" in conc:
        errors.extend(_check_pred(conc, line_num, entities, bound_vars))

    return errors


def _split_args(s: str) -> list[str]:
    """Split on commas respecting nested parens and brackets."""
    parts = []
    depth = 0
    current = ""
    for ch in s:
        if ch in "([":
            depth += 1
            current += ch
        elif ch in ")]":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    return parts


def _split_on_ampersand(s: str) -> list[str]:
    """Split on & respecting nested parens and brackets."""
    parts = []
    depth = 0
    current = ""
    for ch in s:
        if ch in "([":
            depth += 1
            current += ch
        elif ch in ")]":
            depth -= 1
            current += ch
        elif ch == "&" and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    return parts
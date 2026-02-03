"""Validate .logic files structurally."""
import re
from dataclasses import dataclass


@dataclass
class CheckError:
    line: int
    message: str


def check_file(filepath: str, version: str = "horn1") -> list[CheckError]:
    """Route to the appropriate checker based on DSL version."""
    if version == "horn2":
        return _check_horn2(filepath)
    return _check_horn1(filepath)


# ──────────────────────────────────────────────
# horn1 checker (original, positional arguments)
# ──────────────────────────────────────────────

def _check_horn1(filepath: str) -> list[CheckError]:
    errors = []
    entities = {}
    saw_query = False

    with open(filepath) as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if saw_query:
            errors.append(CheckError(i, "Content after query line"))
            continue
        if line.startswith("? "):
            saw_query = True
            errors.extend(_h1_check_pred(line[2:].strip(), i, entities))
            if "&" in line or "->" in line:
                errors.append(CheckError(i, "Query must be a simple proposition"))
            continue
        if line.startswith("entity "):
            parts = line.split()
            if len(parts) < 4 or parts[2] != ":":
                errors.append(CheckError(i, "Bad entity syntax"))
                continue
            name = parts[1]
            if name in entities:
                errors.append(CheckError(i, f"Duplicate entity: {name}"))
            entities[name] = parts[3]
            continue
        if line.startswith("rule "):
            errors.extend(_h1_check_rule(line, i, entities))
            continue
        if "(" in line:
            errors.extend(_h1_check_pred(line, i, entities))
            continue
        errors.append(CheckError(i, f"Unrecognized statement: {line}"))

    if not saw_query:
        errors.append(CheckError(len(lines), "Missing query (? ...) at end"))

    return errors


def _h1_check_pred(text, line_num, entities):
    errors = []
    match = re.match(r'(\w+)\((.+)\)', text)
    if not match:
        errors.append(CheckError(line_num, f"Bad predicate syntax: {text}"))
        return errors
    for arg in match.group(2).split(","):
        arg = arg.strip()
        if arg not in entities:
            errors.append(CheckError(line_num, f"Unknown entity: {arg}"))
    return errors


def _h1_check_rule(line, line_num, entities):
    errors = []
    bracket = re.search(r'\[(.+?)\]', line)
    if not bracket:
        errors.append(CheckError(line_num, "Rule missing variable bindings"))
        return errors
    bound_vars = {}
    for binding in bracket.group(1).split(","):
        binding = binding.strip()
        if ":" not in binding:
            errors.append(CheckError(line_num, f"Bad binding: {binding}"))
            continue
        var, typ = binding.split(":", 1)
        bound_vars[var.strip()] = typ.strip()
    after = line.split("]", 1)[1]
    if ":" in after:
        after = after.split(":", 1)[1]
    if "->" not in after:
        errors.append(CheckError(line_num, "Rule missing ->"))
        return errors
    scope = {**entities, **bound_vars}
    for pred_match in re.finditer(r'(\w+)\(([^)]+)\)', after):
        for arg in pred_match.group(2).split(","):
            if arg.strip() not in scope:
                errors.append(CheckError(line_num, f"Unbound argument: {arg.strip()}"))
    return errors


# ──────────────────────────────────────────────
# horn2 checker (named roles, negation, weights)
# ──────────────────────────────────────────────

def _check_horn2(filepath: str) -> list[CheckError]:
    errors = []
    entities = {}
    saw_query = False

    with open(filepath) as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if saw_query:
            errors.append(CheckError(i, "Content after query line"))
            continue

        # Query
        if line.startswith("? "):
            saw_query = True
            query = line[2:].strip()
            # Strip negation prefix for checking
            if query.startswith("not "):
                query = query[4:].strip()
            errors.extend(_h2_check_pred(query, i, entities, {}))
            continue

        # Entity declaration
        if line.startswith("entity "):
            parts = line.split()
            if len(parts) < 4 or parts[2] != ":":
                errors.append(CheckError(i, "Bad entity syntax: expected 'entity NAME : e'"))
                continue
            name = parts[1]
            typ = parts[3]
            if typ != "e":
                errors.append(CheckError(i, f"Entity type must be 'e', got '{typ}'"))
            if name in entities:
                errors.append(CheckError(i, f"Duplicate entity: {name}"))
            entities[name] = typ
            continue

        # Rule
        if line.startswith("rule"):
            errors.extend(_h2_check_rule(line, i, entities))
            continue

        # Fact (possibly negated)
        fact = line
        if fact.startswith("not "):
            fact = fact[4:].strip()
        if "(" in fact:
            errors.extend(_h2_check_pred(fact, i, entities, {}))
            continue

        errors.append(CheckError(i, f"Unrecognized statement: {line}"))

    if not saw_query:
        errors.append(CheckError(len(lines), "Missing query (? ...) at end"))

    return errors


def _h2_check_pred(text, line_num, entities, bound_vars):
    """Check a predicate call with named roles: pred(role: val, role: val)
    or zero-arg: pred()
    or nested: pred(role: inner_pred(role: val))
    """
    errors = []

    # Zero-argument proposition
    match = re.match(r'(\w+)\(\s*\)', text)
    if match:
        return errors

    # Named-role predicate
    match = re.match(r'(\w+)\((.+)\)', text, re.DOTALL)
    if not match:
        errors.append(CheckError(line_num, f"Bad predicate syntax: {text}"))
        return errors

    pred_name = match.group(1)
    args_str = match.group(2)

    # Split arguments respecting nested parens
    args = _split_args(args_str)
    scope = {**entities, **bound_vars}

    for arg in args:
        arg = arg.strip()
        if ":" not in arg:
            errors.append(CheckError(line_num, f"Missing role name in: {arg}"))
            continue
        role_name, value = arg.split(":", 1)
        role_name = role_name.strip()
        value = value.strip()

        if not role_name:
            errors.append(CheckError(line_num, f"Empty role name"))
            continue

        # Value is a nested predicate call
        if "(" in value:
            errors.extend(_h2_check_pred(value, line_num, entities, bound_vars))
        # Value is an entity or bound variable
        elif value not in scope:
            errors.append(CheckError(line_num, f"Unknown value: {value}"))

    return errors


def _h2_check_rule(line, line_num, entities):
    """Check a horn2 rule.

    Formats:
      rule [x:e, y:e]: PREMISE & PREMISE -> CONCLUSION
      rule [x:e] (0.7): PREMISE -> CONCLUSION
      rule: PREMISE -> CONCLUSION  (ground rule, no variables)
    """
    errors = []
    bound_vars = {}

    rest = line[4:].strip()  # strip "rule"

    # Parse optional variable bindings
    if rest.startswith("["):
        # Find matching close bracket, respecting nesting
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

        # Parse bindings, respecting bracket types
        bindings = _split_args(bindings_str)
        for binding in bindings:
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

    # Parse optional weight
    if rest.startswith("("):
        weight_end = rest.index(")")
        weight_str = rest[1:weight_end].strip()
        try:
            float(weight_str)
        except ValueError:
            errors.append(CheckError(line_num, f"Bad rule weight: {weight_str}"))
        rest = rest[weight_end + 1:].strip()

    # Strip leading colon
    if rest.startswith(":"):
        rest = rest[1:].strip()

    # Must have ->
    if "->" not in rest:
        errors.append(CheckError(line_num, "Rule missing ->"))
        return errors

    premise_str, conclusion_str = rest.split("->", 1)
    premise_str = premise_str.strip()
    conclusion_str = conclusion_str.strip()

    # Check premises
    for pred_text in _split_on_ampersand(premise_str):
        pred_text = pred_text.strip()
        if pred_text.startswith("not "):
            pred_text = pred_text[4:].strip()
        if "(" in pred_text:
            errors.extend(_h2_check_pred(pred_text, line_num, entities, bound_vars))

    # Check conclusion
    conc = conclusion_str.strip()
    if conc.startswith("not "):
        conc = conc[4:].strip()
    if "(" in conc:
        errors.extend(_h2_check_pred(conc, line_num, entities, bound_vars))

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
"""
Grammar for .logic files.

Validates semantic representation files structurally.
"""

import re
from dataclasses import dataclass, field


@dataclass
class CheckError:
    line: int
    message: str


@dataclass
class PredicateDecl:
    name: str
    roles: dict[str, str]  # role_name -> type


def check_file(filepath: str) -> list[CheckError]:
    """Check a .logic file for structural validity."""
    errors = []
    predicates: dict[str, PredicateDecl] = {}
    entities: dict[str, str] = {}
    saw_entity = False
    saw_sentence = False
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

        # Predicate declaration: predicate NAME {role: type, ...}
        if line.startswith("predicate "):
            if saw_entity or saw_sentence:
                errors.append(CheckError(i, "Predicate declarations must come before entities and sentences"))
                continue
            errors.extend(_parse_predicate_decl(line, i, predicates))
            continue

        # Entity declaration: entity NAME : e
        if line.startswith("entity "):
            if saw_sentence:
                errors.append(CheckError(i, "Entity declarations must come before sentences"))
                continue
            saw_entity = True
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

        # Query: ? pred(...) or ? not pred(...)
        if line.startswith("? "):
            saw_sentence = True
            saw_query = True
            query = line[2:].strip()
            if query.startswith("not "):
                query = query[4:].strip()
            errors.extend(_check_pred(query, i, predicates, entities, {}))
            continue

        # Rule: rule [bindings] (weight): premises -> conclusion
        if line.startswith("rule"):
            saw_sentence = True
            errors.extend(_check_rule(line, i, predicates, entities))
            continue

        # Fact: pred(...) or not pred(...)
        fact = line
        if fact.startswith("not "):
            fact = fact[4:].strip()
        if "(" in fact:
            saw_sentence = True
            errors.extend(_check_pred(fact, i, predicates, entities, {}))
            continue

        errors.append(CheckError(i, f"Unrecognized statement: {line}"))

    if not saw_query:
        errors.append(CheckError(len(lines), "Missing query (? ...) at end"))

    return errors


def _parse_predicate_decl(line: str, line_num: int, predicates: dict) -> list[CheckError]:
    """Parse: predicate NAME {role: type, role: type, ...}"""
    errors = []

    # Match: predicate NAME {ROLES} or predicate NAME {}
    match = re.match(r'predicate\s+(\w+)\s*\{([^}]*)\}', line)
    if not match:
        errors.append(CheckError(line_num, f"Bad predicate declaration: {line}"))
        return errors

    name = match.group(1)
    roles_str = match.group(2).strip()

    if name in predicates:
        errors.append(CheckError(line_num, f"Duplicate predicate: {name}"))
        return errors

    roles = {}
    if roles_str:
        for part in _split_args(roles_str):
            part = part.strip()
            if ":" not in part:
                errors.append(CheckError(line_num, f"Bad role in predicate declaration: {part}"))
                continue
            role_name, role_type = part.split(":", 1)
            role_name = role_name.strip()
            role_type = role_type.strip()
            if role_name in roles:
                errors.append(CheckError(line_num, f"Duplicate role: {role_name}"))
                continue
            roles[role_name] = role_type

    predicates[name] = PredicateDecl(name=name, roles=roles)
    return errors


def _check_pred(text: str, line_num: int, predicates: dict, entities: dict, bound_vars: dict) -> list[CheckError]:
    """Check a predicate call.

    Formats:
      pred()                           — zero-arg proposition
      pred(role: value, role: value)   — named roles
    """
    errors = []

    # Zero-argument proposition: pred()
    match = re.match(r'(\w+)\(\s*\)', text)
    if match:
        pred_name = match.group(1)
        if pred_name not in predicates:
            errors.append(CheckError(line_num, f"Undeclared predicate: {pred_name}"))
        elif predicates[pred_name].roles:
            errors.append(CheckError(line_num, f"Predicate {pred_name} expects roles: {list(predicates[pred_name].roles.keys())}"))
        return errors

    # Predicate with arguments: pred(role: value, ...)
    match = re.match(r'(\w+)\((.+)\)', text, re.DOTALL)
    if not match:
        errors.append(CheckError(line_num, f"Bad predicate syntax: {text}"))
        return errors

    pred_name = match.group(1)
    args_str = match.group(2)

    # Check predicate is declared
    if pred_name not in predicates:
        errors.append(CheckError(line_num, f"Undeclared predicate: {pred_name}"))
        return errors

    decl = predicates[pred_name]
    args = _split_args(args_str)
    scope = {**entities, **bound_vars}

    # Track which roles we've seen
    seen_roles = set()

    for arg in args:
        arg = arg.strip()

        if ":" not in arg:
            errors.append(CheckError(line_num, f"Missing role name in: {arg}"))
            continue

        role_name, value = arg.split(":", 1)
        role_name = role_name.strip()
        value = value.strip()

        if not role_name:
            errors.append(CheckError(line_num, "Empty role name"))
            continue

        # Check role exists in declaration
        if role_name not in decl.roles:
            errors.append(CheckError(line_num, f"Unknown role '{role_name}' for predicate {pred_name}"))
            continue

        if role_name in seen_roles:
            errors.append(CheckError(line_num, f"Duplicate role: {role_name}"))
            continue
        seen_roles.add(role_name)

        expected_type = decl.roles[role_name]

        # Value is a nested predicate call (for s-typed roles)
        if "(" in value:
            if expected_type != "s" and not expected_type.startswith("["):
                errors.append(CheckError(line_num, f"Role '{role_name}' expects {expected_type}, got a predicate"))
            errors.extend(_check_pred(value, line_num, predicates, entities, bound_vars))
        # Value is a predicate name (for higher-order roles like [e, e])
        elif expected_type.startswith("["):
            if value not in predicates:
                errors.append(CheckError(line_num, f"Unknown predicate: {value}"))
            # TODO: validate arity matches expected_type
        # Value is an entity or variable
        else:
            if value not in scope:
                errors.append(CheckError(line_num, f"Unknown value: {value}"))
            # TODO: validate type matches expected_type

    # Check all required roles are present
    missing = set(decl.roles.keys()) - seen_roles
    if missing:
        errors.append(CheckError(line_num, f"Missing roles for {pred_name}: {missing}"))

    return errors


def _check_rule(line: str, line_num: int, predicates: dict, entities: dict) -> list[CheckError]:
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
            errors.extend(_check_pred(pred_text, line_num, predicates, entities, bound_vars))

    # Check conclusion
    conc = conclusion_str.strip()
    if conc.startswith("not "):
        conc = conc[4:].strip()
    if "(" in conc:
        errors.extend(_check_pred(conc, line_num, predicates, entities, bound_vars))

    return errors


def _split_args(s: str) -> list[str]:
    """Split on commas respecting nested parens and brackets."""
    parts = []
    depth = 0
    current = ""
    for ch in s:
        if ch in "([{":
            depth += 1
            current += ch
        elif ch in ")]}":
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
        if ch in "([{":
            depth += 1
            current += ch
        elif ch in ")]}":
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
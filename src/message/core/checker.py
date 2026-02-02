"""Validate .logic files structurally."""
import re
from dataclasses import dataclass


@dataclass
class CheckError:
    line: int
    message: str


def check_file(filepath: str) -> list[CheckError]:
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
            errors.extend(_check_pred_call(line[2:].strip(), i, entities))
            if "&" in line or "->" in line:
                errors.append(CheckError(i, "Query must be a simple proposition"))
            continue
        if line.startswith("entity "):
            parts = line.split()
            if len(parts) < 4 or parts[2] != ":":
                errors.append(CheckError(i, "Bad entity syntax: expected 'entity NAME : TYPE'"))
                continue
            name = parts[1]
            if name in entities:
                errors.append(CheckError(i, f"Duplicate entity: {name}"))
            entities[name] = parts[3]
            continue
        if line.startswith("rule "):
            errors.extend(_check_rule(line, i, entities))
            continue
        if "(" in line:
            errors.extend(_check_pred_call(line, i, entities))
            continue
        errors.append(CheckError(i, f"Unrecognized statement: {line}"))

    if not saw_query:
        errors.append(CheckError(len(lines), "Missing query (? ...) at end of file"))

    return errors


def _check_pred_call(text, line_num, entities):
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


def _check_rule(line, line_num, entities):
    errors = []
    bracket = re.search(r'\[(.+?)\]', line)
    if not bracket:
        errors.append(CheckError(line_num, "Rule missing variable bindings [v:T, ...]"))
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
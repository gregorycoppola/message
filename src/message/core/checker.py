"""
Validate .logic files against a DSL spec.
"""

from dataclasses import dataclass
from message.core.dsl import DSLSpec


@dataclass
class CheckError:
    line: int
    message: str


def check_file(spec: DSLSpec, filepath: str) -> list[CheckError]:
    """Validate a .logic file against a DSL spec."""
    errors = []
    
    with open(filepath) as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        
        if not line or line.startswith("#"):
            continue
        
        line_errors = check_line(spec, line, i)
        errors.extend(line_errors)
    
    return errors


def check_line(spec: DSLSpec, line: str, line_num: int) -> list[CheckError]:
    """Check a single line against the DSL spec."""
    errors = []
    
    # Entity declaration
    if line.startswith("entity "):
        parts = line.split()
        if len(parts) >= 4 and parts[2] == ":":
            type_name = parts[3]
            if type_name not in spec.types:
                errors.append(CheckError(line_num, f"Unknown type: {type_name}"))
        return errors
    
    # Rule
    if line.startswith(("rule ", "always ", "usually ", "sometimes ",
                        "often ", "likely ", "unlikely ", "rarely ", "never ")):
        quantifier = line.split()[0]
        if quantifier != "rule" and quantifier not in spec.quantifiers:
            errors.append(CheckError(line_num, f"Unknown quantifier: {quantifier}"))
        return errors
    
    # Query
    if line.startswith("? "):
        return errors
    
    # Fact — check predicate name
    if "(" in line:
        pred_name = line.split("(")[0].strip()
        # Predicate is either declared or ad-hoc (open world)
        # For now just note if it's not declared
        if pred_name not in spec.predicates:
            errors.append(CheckError(line_num, f"Undeclared predicate: {pred_name} (not in DSL)"))
    
    return errors
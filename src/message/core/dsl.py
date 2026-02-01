"""
DSL version management.

Each version is a standalone .dsl file that completely specifies
a semantic representation language.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


DSL_DIR = Path(__file__).parent.parent.parent.parent / "dsl"


@dataclass
class DSLType:
    name: str
    parent: str | None = None


@dataclass
class DSLRole:
    name: str
    domain: str
    range: str


@dataclass
class DSLPredicate:
    name: str
    roles: list[tuple[str, str]]  # [(role_name, type), ...]


@dataclass
class DSLQuantifier:
    name: str
    weight: float


@dataclass
class DSLSpec:
    """A complete DSL specification."""
    name: str
    description: str
    raw: str
    types: dict[str, DSLType] = field(default_factory=dict)
    roles: dict[str, DSLRole] = field(default_factory=dict)
    predicates: dict[str, DSLPredicate] = field(default_factory=dict)
    quantifiers: dict[str, DSLQuantifier] = field(default_factory=dict)
    constants: dict[str, str] = field(default_factory=dict)  # name -> type


def list_versions() -> list[dict]:
    """List all available DSL versions."""
    if not DSL_DIR.exists():
        return []
    
    versions = []
    for f in sorted(DSL_DIR.glob("*.dsl")):
        spec = _parse_spec(f)
        if spec:
            versions.append({
                "name": spec.name,
                "description": spec.description,
            })
    
    return versions


def load_version(version: str) -> DSLSpec | None:
    """Load a specific DSL version."""
    path = DSL_DIR / f"{version}.dsl"
    if not path.exists():
        return None
    return _parse_spec(path)


def _parse_spec(path: Path) -> DSLSpec | None:
    """Parse a .dsl file into a DSLSpec."""
    text = path.read_text()
    name = path.stem
    description = ""
    
    spec = DSLSpec(name=name, description="", raw=text)
    
    for line in text.split("\n"):
        line = line.strip()
        
        if not line or line.startswith("#"):
            # Extract description from first comment
            if line.startswith("# ") and not spec.description:
                spec.description = line[2:]
            continue
        
        parts = line.split()
        if not parts:
            continue
        
        keyword = parts[0]
        
        if keyword == "type":
            _parse_type(spec, parts[1:])
        elif keyword == "role":
            _parse_role(spec, parts[1:])
        elif keyword == "predicate":
            _parse_predicate(spec, line)
        elif keyword == "quantifier":
            _parse_quantifier(spec, parts[1:])
        elif keyword == "constant":
            _parse_constant(spec, parts[1:])
    
    return spec


def _parse_type(spec: DSLSpec, parts: list[str]):
    """Parse: type name [extends parent]"""
    name = parts[0]
    parent = None
    if len(parts) >= 3 and parts[1] == "extends":
        parent = parts[2]
    spec.types[name] = DSLType(name=name, parent=parent)


def _parse_role(spec: DSLSpec, parts: list[str]):
    """Parse: role name : domain -> range"""
    # role agent : event -> entity
    name = parts[0]
    # Skip ':'
    domain = parts[2]
    # Skip '->'
    range_type = parts[4]
    spec.roles[name] = DSLRole(name=name, domain=domain, range=range_type)


def _parse_predicate(spec: DSLSpec, line: str):
    """Parse: predicate name(role: type, role: type)"""
    import re
    match = re.match(r"predicate\s+(\w+)\((.*)\)", line)
    if not match:
        return
    name = match.group(1)
    roles_str = match.group(2)
    roles = []
    for part in roles_str.split(","):
        part = part.strip()
        if ":" in part:
            rname, rtype = part.split(":", 1)
            roles.append((rname.strip(), rtype.strip()))
    spec.predicates[name] = DSLPredicate(name=name, roles=roles)


def _parse_quantifier(spec: DSLSpec, parts: list[str]):
    """Parse: quantifier name = weight"""
    name = parts[0]
    # Skip '='
    weight = float(parts[2])
    spec.quantifiers[name] = DSLQuantifier(name=name, weight=weight)


def _parse_constant(spec: DSLSpec, parts: list[str]):
    """Parse: constant name : type"""
    name = parts[0]
    # Skip ':'
    type_name = parts[2]
    spec.constants[name] = type_name
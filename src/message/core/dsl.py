"""
DSL version management.

Each version is a standalone .dsl file that completely specifies
a semantic representation language.
"""

import re
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
    roles: list[tuple[str, str]]  # [(role_name, type_str), ...]
    type_sig: str = ""            # e.g. "[e, e]" or "[s, e]"
    arg_types: list[str] = field(default_factory=list)  # e.g. ["e", "e"]


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

    spec = DSLSpec(name=name, description="", raw=text)

    for line in text.split("\n"):
        line = line.strip()

        if not line or line.startswith("#"):
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
    name = parts[0]
    domain = parts[2]
    range_type = parts[4]
    spec.roles[name] = DSLRole(name=name, domain=domain, range=range_type)


def _parse_predicate(spec: DSLSpec, line: str):
    """Parse predicate declarations in both formats.

    horn1: predicate name(role: type, role: type)
    horn2: predicate name : [type, ...] { role: type, role: type }
    """
    # Try horn2 format: predicate NAME : [TYPE, ...] { ROLES }
    match = re.match(
        r'predicate\s+(\w+)\s*:\s*(\[[^\]]*(?:\[[^\]]*\][^\]]*)*\])\s*\{([^}]*)\}',
        line,
    )
    if match:
        name = match.group(1)
        type_sig = match.group(2).strip()
        roles_str = match.group(3).strip()
        arg_types = _parse_type_sig(type_sig)
        roles = _parse_roles_str(roles_str)
        spec.predicates[name] = DSLPredicate(
            name=name, roles=roles, type_sig=type_sig, arg_types=arg_types,
        )
        return

    # Try horn2 format without roles: predicate NAME : [TYPE, ...]
    match = re.match(r'predicate\s+(\w+)\s*:\s*(\[[^\]]*\])', line)
    if match:
        name = match.group(1)
        type_sig = match.group(2).strip()
        arg_types = _parse_type_sig(type_sig)
        spec.predicates[name] = DSLPredicate(
            name=name, roles=[], type_sig=type_sig, arg_types=arg_types,
        )
        return

    # Try horn1 format: predicate name(role: type, ...)
    match = re.match(r"predicate\s+(\w+)\((.*)\)", line)
    if match:
        name = match.group(1)
        roles = _parse_roles_str(match.group(2))
        spec.predicates[name] = DSLPredicate(name=name, roles=roles)
        return


def _parse_type_sig(sig: str) -> list[str]:
    """Parse a type signature like '[e, e]' or '[[e,e], e, e]' into arg types."""
    inner = sig.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1].strip()

    if not inner:
        return []

    # Split on commas, respecting nested brackets
    args = []
    depth = 0
    current = ""
    for ch in inner:
        if ch == "[":
            depth += 1
            current += ch
        elif ch == "]":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        args.append(current.strip())

    return args


def _parse_roles_str(roles_str: str) -> list[tuple[str, str]]:
    """Parse 'role: type, role: type' into [(role, type), ...]."""
    roles = []
    # Split respecting nested brackets
    parts = []
    depth = 0
    current = ""
    for ch in roles_str:
        if ch == "[":
            depth += 1
            current += ch
        elif ch == "]":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())

    for part in parts:
        if ":" in part:
            rname, rtype = part.split(":", 1)
            roles.append((rname.strip(), rtype.strip()))
    return roles


def _parse_quantifier(spec: DSLSpec, parts: list[str]):
    """Parse: quantifier name = weight"""
    name = parts[0]
    weight = float(parts[2])
    spec.quantifiers[name] = DSLQuantifier(name=name, weight=weight)


def _parse_constant(spec: DSLSpec, parts: list[str]):
    """Parse: constant name : type"""
    name = parts[0]
    type_name = parts[2]
    spec.constants[name] = type_name
"""
Lexicon parser — reads .lexicon files into structured data.

A lexicon file declares predicates (with typed roles) and entities,
each with optional surface forms and a gloss.

Format:
    predicate NAME {role: type, role: type}
      forms: word1, word2, word3
      "gloss string"

    entity NAME : e
      forms: Word1, word2
      "gloss string"
"""

import re
from dataclasses import dataclass, field


@dataclass
class PredicateEntry:
    name: str
    roles: dict[str, str]  # role_name -> type
    forms: list[str] = field(default_factory=list)
    gloss: str = ""

    @property
    def role_signature(self) -> str:
        """e.g. '{theme:e}' or '{agent:e,patient:e}'"""
        parts = ",".join(f"{r}:{t}" for r, t in self.roles.items())
        return "{" + parts + "}"

    @property
    def type_str(self) -> str:
        """e.g. '[e]' or '[e,e]'"""
        types = list(self.roles.values())
        return "[" + ",".join(types) + "]"


@dataclass
class EntityEntry:
    name: str
    typ: str  # usually "e"
    forms: list[str] = field(default_factory=list)
    gloss: str = ""


@dataclass
class Lexicon:
    predicates: dict[str, PredicateEntry] = field(default_factory=dict)
    entities: dict[str, EntityEntry] = field(default_factory=dict)

    # Index: surface form (lowercased) -> (canonical_name, "predicate"|"entity")
    _form_index: dict[str, tuple[str, str]] = field(default_factory=dict)

    def build_index(self):
        """Build the surface form -> canonical name index."""
        self._form_index = {}
        for name, pred in self.predicates.items():
            forms = pred.forms if pred.forms else [name]
            for form in forms:
                self._form_index[form.lower()] = (name, "predicate")
        for name, ent in self.entities.items():
            forms = ent.forms if ent.forms else [name]
            for form in forms:
                self._form_index[form.lower()] = (name, "entity")

    def lookup(self, surface: str) -> tuple[str, str] | None:
        """Look up a surface form. Returns (canonical_name, category) or None."""
        return self._form_index.get(surface.lower())

    def get_type(self, canonical: str) -> str | None:
        """Get the type string for a canonical name."""
        if canonical in self.predicates:
            return self.predicates[canonical].role_signature
        if canonical in self.entities:
            return "e"
        return None

    def get_predicate(self, name: str) -> PredicateEntry | None:
        return self.predicates.get(name)

    def get_entity(self, name: str) -> EntityEntry | None:
        return self.entities.get(name)


def parse_lexicon(text: str) -> Lexicon:
    """Parse a .lexicon file into a Lexicon."""
    lexicon = Lexicon()
    lines = text.strip().split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line or line.startswith("#"):
            i += 1
            continue

        # Predicate declaration
        if line.startswith("predicate "):
            pred, i = _parse_predicate(lines, i)
            if pred:
                lexicon.predicates[pred.name] = pred
            continue

        # Entity declaration
        if line.startswith("entity "):
            ent, i = _parse_entity(lines, i)
            if ent:
                lexicon.entities[ent.name] = ent
            continue

        i += 1

    lexicon.build_index()
    return lexicon


def parse_lexicon_file(path: str) -> Lexicon:
    """Parse a .lexicon file from a file path."""
    with open(path) as f:
        return parse_lexicon(f.read())


def _parse_predicate(lines: list[str], i: int) -> tuple[PredicateEntry | None, int]:
    """Parse a predicate declaration + optional forms + gloss."""
    line = lines[i].strip()
    match = re.match(r'predicate\s+(\w+)\s*\{([^}]*)\}', line)
    if not match:
        return None, i + 1

    name = match.group(1)
    roles_str = match.group(2).strip()

    roles = {}
    if roles_str:
        for part in roles_str.split(","):
            part = part.strip()
            if ":" in part:
                role_name, role_type = part.split(":", 1)
                roles[role_name.strip()] = role_type.strip()

    forms = []
    gloss = ""
    i += 1

    # Check for indented continuation lines (forms, gloss)
    while i < len(lines):
        next_line = lines[i]
        if not next_line.startswith("  ") and not next_line.startswith("\t"):
            break
        next_line = next_line.strip()
        if next_line.startswith("forms:"):
            forms_str = next_line[6:].strip()
            forms = [f.strip() for f in forms_str.split(",") if f.strip()]
            i += 1
        elif next_line.startswith('"') and next_line.endswith('"'):
            gloss = next_line[1:-1]
            i += 1
        else:
            break

    return PredicateEntry(name=name, roles=roles, forms=forms, gloss=gloss), i


def _parse_entity(lines: list[str], i: int) -> tuple[EntityEntry | None, int]:
    """Parse an entity declaration + optional forms + gloss."""
    line = lines[i].strip()
    parts = line.split()
    if len(parts) < 4 or parts[2] != ":":
        return None, i + 1

    name = parts[1]
    typ = parts[3]

    forms = []
    gloss = ""
    i += 1

    while i < len(lines):
        next_line = lines[i]
        if not next_line.startswith("  ") and not next_line.startswith("\t"):
            break
        next_line = next_line.strip()
        if next_line.startswith("forms:"):
            forms_str = next_line[6:].strip()
            forms = [f.strip() for f in forms_str.split(",") if f.strip()]
            i += 1
        elif next_line.startswith('"') and next_line.endswith('"'):
            gloss = next_line[1:-1]
            i += 1
        else:
            break

    return EntityEntry(name=name, typ=typ, forms=forms, gloss=gloss), i
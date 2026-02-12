"""
Core logical primitives for QBBN.

Tier 1 - Atoms: Type, RoleLabel, Entity
Tier 2 - Simple compositions: Constant, Variable
Tier 3 - Predicates (can be nested for intensionality)
Tier 4 - Substitution and grounding
"""

from dataclasses import dataclass
from typing import Dict, Union


# === Tier 1: Atoms ===

@dataclass(frozen=True)
class Type:
    name: str


@dataclass(frozen=True)
class RoleLabel:
    name: str


@dataclass(frozen=True)
class Entity:
    id: str


# === Tier 2: Simple Compositions ===

@dataclass(frozen=True)
class Constant:
    entity: Entity
    type: Type


@dataclass(frozen=True)
class Variable:
    type: Type
    name: str


Argument = Union[Constant, Variable, "Predicate"]


# === Tier 3: Predicates ===

@dataclass(frozen=True)
class Predicate:
    function_name: str
    roles: tuple[tuple[RoleLabel, Argument], ...]
    negated: bool = False

    @property
    def is_grounded(self) -> bool:
        for _, arg in self.roles:
            if isinstance(arg, Variable):
                return False
            if isinstance(arg, Predicate) and not arg.is_grounded:
                return False
        return True

    @property
    def variables(self) -> frozenset[Variable]:
        vars = set()
        for _, arg in self.roles:
            if isinstance(arg, Variable):
                vars.add(arg)
            elif isinstance(arg, Predicate):
                vars.update(arg.variables)
        return frozenset(vars)

    def substitute(self, bindings: Dict[Variable, Constant]) -> "Predicate":
        new_roles = []
        for role, arg in self.roles:
            if isinstance(arg, Variable) and arg in bindings:
                new_roles.append((role, bindings[arg]))
            elif isinstance(arg, Predicate):
                new_roles.append((role, arg.substitute(bindings)))
            else:
                new_roles.append((role, arg))
        return Predicate(self.function_name, tuple(new_roles), self.negated)

    def to_dict(self) -> dict:
        roles_list = []
        for role, arg in self.roles:
            if isinstance(arg, Constant):
                roles_list.append({
                    "role": role.name,
                    "type": "constant",
                    "entity": arg.entity.id,
                    "entity_type": arg.type.name,
                })
            elif isinstance(arg, Variable):
                roles_list.append({
                    "role": role.name,
                    "type": "variable",
                    "var_type": arg.type.name,
                    "var_name": arg.name,
                })
            elif isinstance(arg, Predicate):
                roles_list.append({
                    "role": role.name,
                    "type": "predicate",
                    "predicate": arg.to_dict(),
                })
        return {
            "function_name": self.function_name,
            "roles": roles_list,
            "negated": self.negated,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Predicate":
        roles = []
        for r in d["roles"]:
            role = RoleLabel(r["role"])
            if r["type"] == "constant":
                arg = Constant(Entity(r["entity"]), Type(r["entity_type"]))
            elif r["type"] == "variable":
                arg = Variable(Type(r["var_type"]), r["var_name"])
            elif r["type"] == "predicate":
                arg = Predicate.from_dict(r["predicate"])
            roles.append((role, arg))
        return cls(d["function_name"], tuple(roles), d.get("negated", False))


Proposition = Predicate
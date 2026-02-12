"""
Horn clauses for QBBN.
"""

import hashlib
from dataclasses import dataclass
from itertools import product

from message.core.logic import (
    Type, Constant, Variable, Predicate
)


def clause_hash(clause: "HornClause") -> str:
    canonical = clause.canonical_tuple()
    return hashlib.sha256(repr(canonical).encode()).hexdigest()[:10]


@dataclass
class HornClause:
    premises: tuple[Predicate, ...]
    conclusion: Predicate
    variables: tuple[Variable, ...]
    weight: float = 1.0

    @property
    def is_fact(self) -> bool:
        return len(self.premises) == 0

    @property
    def is_grounded(self) -> bool:
        for p in self.premises:
            if not p.is_grounded:
                return False
        return self.conclusion.is_grounded

    def canonical_tuple(self) -> tuple:
        def arg_to_str(arg) -> str:
            if isinstance(arg, Constant):
                return arg.entity.id
            elif isinstance(arg, Variable):
                return f"?{arg.name}"
            elif isinstance(arg, Predicate):
                return repr(pred_tuple(arg))
            else:
                return str(arg)

        def pred_tuple(p: Predicate) -> tuple:
            neg = "!" if p.negated else ""
            roles = tuple(sorted((r.name, arg_to_str(a)) for r, a in p.roles))
            return (neg + p.function_name, roles)

        if self.is_fact:
            return ("fact", pred_tuple(self.conclusion))
        else:
            body = tuple(pred_tuple(p) for p in self.premises)
            return ("rule", pred_tuple(self.conclusion), body)

    @property
    def hash(self) -> str:
        return clause_hash(self)

    def ground(self, bindings: dict[Variable, Constant]) -> "HornClause":
        new_premises = tuple(p.substitute(bindings) for p in self.premises)
        new_conclusion = self.conclusion.substitute(bindings)
        return HornClause(new_premises, new_conclusion, (), self.weight)


@dataclass
class KnowledgeBase:
    entities: dict[str, Constant]
    types: dict[str, Type]
    clauses: list[HornClause]
    predicates: dict[str, object] = None

    def __post_init__(self):
        if self.predicates is None:
            self.predicates = {}

    def entities_of_type(self, type_name: str) -> list[Constant]:
        return [c for c in self.entities.values() if c.type.name == type_name]

    def add_fact(self, pred: Predicate) -> None:
        clause = HornClause(premises=(), conclusion=pred, variables=(), weight=1.0)
        self.clauses.append(clause)

    def add_rule(self, premises: list[Predicate], conclusion: Predicate,
                 variables: list[Variable], weight: float = 1.0) -> None:
        clause = HornClause(
            premises=tuple(premises),
            conclusion=conclusion,
            variables=tuple(variables),
            weight=weight,
        )
        self.clauses.append(clause)

    def ground_all(self) -> list[HornClause]:
        grounded = []
        for clause in self.clauses:
            if clause.is_fact:
                grounded.append(clause)
            elif not clause.variables:
                grounded.append(clause)
            else:
                for binding in self._all_bindings(clause.variables):
                    grounded.append(clause.ground(binding))
        return grounded

    def _all_bindings(self, variables: tuple[Variable, ...]) -> list[dict[Variable, Constant]]:
        if not variables:
            return [{}]
        domains = []
        for var in variables:
            entities = self.entities_of_type(var.type.name)
            if not entities:
                return []
            domains.append(entities)
        bindings = []
        for combo in product(*domains):
            binding = {var: const for var, const in zip(variables, combo)}
            bindings.append(binding)
        return bindings

    @classmethod
    def from_logical_document(cls, doc) -> "KnowledgeBase":
        kb = cls(
            entities=dict(doc.entities),
            types=dict(doc.types),
            clauses=[],
            predicates=dict(doc.predicates) if hasattr(doc, 'predicates') else {},
        )
        for prop in doc.propositions:
            kb.add_fact(prop)
        for rule in doc.rules:
            kb.add_rule(
                premises=rule.premises,
                conclusion=rule.conclusion,
                variables=rule.variables,
                weight=rule.weight,
            )
        return kb
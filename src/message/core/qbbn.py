"""
QBBN Factor Graph.

Bipartite factor graph with:
- Variable nodes: propositions (p) and groups (g)
- Factor nodes: Ψ_and (deterministic), Ψ_or (learned), Ψ_neg (deterministic)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from message.core.horn import KnowledgeBase as HornKB


DEBUG = False


def debug(*args):
    if DEBUG:
        print("[QBBN]", *args)


class NodeType(Enum):
    PROPOSITION = "proposition"
    GROUP = "group"


class FactorType(Enum):
    AND = "and"
    OR = "or"
    NEG = "neg"


@dataclass
class Variable:
    id: str
    node_type: NodeType
    formula: Optional[str] = None
    conjunct_ids: tuple[str, ...] = ()
    conclusion_id: Optional[str] = None
    rule_id: Optional[str] = None
    belief: list[float] = field(default_factory=lambda: [0.5, 0.5])
    is_evidence: bool = False
    evidence_value: Optional[bool] = None

    def set_evidence(self, value: bool):
        self.is_evidence = True
        self.evidence_value = value
        self.belief = [0.0, 1.0] if value else [1.0, 0.0]

    @property
    def prob(self) -> float:
        return self.belief[1]

    @property
    def is_proposition(self) -> bool:
        return self.node_type == NodeType.PROPOSITION

    @property
    def is_group(self) -> bool:
        return self.node_type == NodeType.GROUP


@dataclass
class Factor:
    id: str
    factor_type: FactorType
    input_ids: list[str]
    output_id: str
    weights: dict[str, float] = field(default_factory=dict)
    messages: dict[str, list[float]] = field(default_factory=dict)

    def init_messages(self):
        for var_id in self.all_var_ids:
            self.messages[var_id] = [1.0, 1.0]

    @property
    def all_var_ids(self) -> list[str]:
        return self.input_ids + [self.output_id]


@dataclass
class Rule:
    id: str
    premise_patterns: list[str]
    conclusion_pattern: str
    variables: list[tuple[str, str]]
    weight: float = 1.0


def get_positive_formula(formula: str) -> str:
    if formula.startswith("not "):
        return formula[4:]
    return formula


def get_negated_formula(formula: str) -> str:
    if formula.startswith("not "):
        return formula[4:]
    return f"not {formula}"


def is_negated_formula(formula: str) -> bool:
    return formula.startswith("not ")


@dataclass
class QBBNGraph:
    variables: dict[str, Variable] = field(default_factory=dict)
    factors: dict[str, Factor] = field(default_factory=dict)
    rules: dict[str, Rule] = field(default_factory=dict)
    var_to_factors: dict[str, list[str]] = field(default_factory=dict)
    prop_to_groups: dict[str, list[str]] = field(default_factory=dict)
    formula_to_id: dict[str, str] = field(default_factory=dict)
    neg_pairs: set[tuple[str, str]] = field(default_factory=set)
    _p_count: int = 0
    _g_count: int = 0
    _and_count: int = 0
    _or_count: int = 0
    _neg_count: int = 0
    _r_count: int = 0
    query_id: Optional[str] = None

    def add_proposition(self, formula: str) -> Variable:
        if formula in self.formula_to_id:
            return self.variables[self.formula_to_id[formula]]
        self._p_count += 1
        pid = f"p{self._p_count}"
        prop = Variable(id=pid, node_type=NodeType.PROPOSITION, formula=formula)
        self.variables[pid] = prop
        self.formula_to_id[formula] = pid
        self.var_to_factors[pid] = []
        self.prop_to_groups[pid] = []
        return prop

    def add_group(self, premise_ids: list[str], conclusion_id: str, rule_id: str) -> Variable:
        self._g_count += 1
        gid = f"g{self._g_count}"
        group = Variable(id=gid, node_type=NodeType.GROUP, conjunct_ids=tuple(premise_ids), conclusion_id=conclusion_id, rule_id=rule_id)
        self.variables[gid] = group
        self.var_to_factors[gid] = []
        self.prop_to_groups[conclusion_id].append(gid)
        return group

    def add_and_factor(self, premise_ids: list[str], group_id: str) -> Factor:
        self._and_count += 1
        fid = f"and{self._and_count}"
        factor = Factor(id=fid, factor_type=FactorType.AND, input_ids=premise_ids, output_id=group_id)
        factor.init_messages()
        self.factors[fid] = factor
        for pid in premise_ids:
            self.var_to_factors[pid].append(fid)
        self.var_to_factors[group_id].append(fid)
        return factor

    def add_or_factor(self, group_ids: list[str], conclusion_id: str, weights: dict[str, float] = None) -> Factor:
        self._or_count += 1
        fid = f"or{self._or_count}"
        if weights is None:
            weights = {gid: 1.0 for gid in group_ids}
        factor = Factor(id=fid, factor_type=FactorType.OR, input_ids=group_ids, output_id=conclusion_id, weights=weights)
        factor.init_messages()
        self.factors[fid] = factor
        for gid in group_ids:
            self.var_to_factors[gid].append(fid)
        self.var_to_factors[conclusion_id].append(fid)
        return factor

    def add_neg_factor(self, pos_id: str, neg_id: str) -> Factor:
        pair = (min(pos_id, neg_id), max(pos_id, neg_id))
        if pair in self.neg_pairs:
            return None
        self.neg_pairs.add(pair)
        self._neg_count += 1
        fid = f"neg{self._neg_count}"
        factor = Factor(id=fid, factor_type=FactorType.NEG, input_ids=[pos_id], output_id=neg_id)
        factor.init_messages()
        self.factors[fid] = factor
        self.var_to_factors[pos_id].append(fid)
        self.var_to_factors[neg_id].append(fid)
        return factor

    def add_rule(self, premise_patterns: list[str], conclusion_pattern: str, variables: list[tuple[str, str]], weight: float = 1.0) -> Rule:
        self._r_count += 1
        rid = f"r{self._r_count}"
        rule = Rule(id=rid, premise_patterns=premise_patterns, conclusion_pattern=conclusion_pattern, variables=variables, weight=weight)
        self.rules[rid] = rule
        return rule

    def add_grounded_rule(self, premise_formulas: list[str], conclusion_formula: str, rule_id: str) -> Variable:
        premise_ids = [self.add_proposition(f).id for f in premise_formulas]
        conc = self.add_proposition(conclusion_formula)
        group = self.add_group(premise_ids, conc.id, rule_id)
        self.add_and_factor(premise_ids, group.id)
        return group

    def build_or_factors(self):
        for prop_id, group_ids in self.prop_to_groups.items():
            if not group_ids:
                continue
            weights = {}
            for gid in group_ids:
                group = self.variables[gid]
                if group.rule_id in self.rules:
                    weights[gid] = self.rules[group.rule_id].weight
                else:
                    weights[gid] = 1.0
            self.add_or_factor(group_ids, prop_id, weights)

    def build_neg_factors(self):
        formulas = list(self.formula_to_id.keys())
        for formula in formulas:
            if is_negated_formula(formula):
                pos_formula = get_positive_formula(formula)
                if pos_formula in self.formula_to_id:
                    pos_id = self.formula_to_id[pos_formula]
                    neg_id = self.formula_to_id[formula]
                    self.add_neg_factor(pos_id, neg_id)

    def set_evidence(self, formula: str, value: bool):
        if formula in self.formula_to_id:
            self.variables[self.formula_to_id[formula]].set_evidence(value)

    def set_query(self, formula: str):
        if formula in self.formula_to_id:
            self.query_id = self.formula_to_id[formula]

    @classmethod
    def from_query(cls, kb: "HornKB", query: str, max_depth: int = 10) -> "QBBNGraph":
        from message.core.logical_lang import format_predicate
        graph = cls()
        query_prop = graph.add_proposition(query)
        graph.query_id = query_prop.id
        grounded = list(kb.ground_all())
        positive_facts: set[str] = set()
        negative_facts: set[str] = set()
        clauses_by_conclusion: dict[str, list] = {}
        clauses_by_premise: dict[str, list] = {}
        for clause in grounded:
            if clause.is_fact:
                conc = clause.conclusion
                formula = format_predicate(conc)
                if conc.negated:
                    pos_formula = get_positive_formula(formula)
                    negative_facts.add(pos_formula)
                    graph.add_proposition(formula)
                    graph.set_evidence(formula, True)
                else:
                    positive_facts.add(formula)
            else:
                conc_formula = format_predicate(clause.conclusion)
                if conc_formula not in clauses_by_conclusion:
                    clauses_by_conclusion[conc_formula] = []
                clauses_by_conclusion[conc_formula].append(clause)
                for prem in clause.premises:
                    prem_formula = format_predicate(prem)
                    if prem_formula not in clauses_by_premise:
                        clauses_by_premise[prem_formula] = []
                    clauses_by_premise[prem_formula].append(clause)
        added_rules: set[str] = set()
        to_expand = [query]
        expanded = set()
        depth = 0
        while to_expand and depth < max_depth:
            next_expand = []
            for formula in to_expand:
                if formula in expanded:
                    continue
                expanded.add(formula)
                graph.add_proposition(formula)
                if formula in positive_facts:
                    graph.set_evidence(formula, True)
                if formula in negative_facts:
                    graph.set_evidence(formula, False)
                backward_clauses = clauses_by_conclusion.get(formula, [])
                for clause in backward_clauses:
                    prem_formulas = [format_predicate(p) for p in clause.premises]
                    conc_formula = format_predicate(clause.conclusion)
                    rule_sig = f"{','.join(sorted(prem_formulas))}|{conc_formula}"
                    if rule_sig not in added_rules:
                        added_rules.add(rule_sig)
                        var_decls = [(v.name, v.type.name) for v in clause.variables]
                        rule = graph.add_rule(prem_formulas, conc_formula, var_decls, clause.weight)
                        graph.add_grounded_rule(prem_formulas, conc_formula, rule.id)
                    for pf in prem_formulas:
                        if pf not in expanded:
                            next_expand.append(pf)
                forward_clauses = clauses_by_premise.get(formula, [])
                for clause in forward_clauses:
                    prem_formulas = [format_predicate(p) for p in clause.premises]
                    conc_formula = format_predicate(clause.conclusion)
                    rule_sig = f"{','.join(sorted(prem_formulas))}|{conc_formula}"
                    if rule_sig not in added_rules:
                        added_rules.add(rule_sig)
                        var_decls = [(v.name, v.type.name) for v in clause.variables]
                        rule = graph.add_rule(prem_formulas, conc_formula, var_decls, clause.weight)
                        graph.add_grounded_rule(prem_formulas, conc_formula, rule.id)
                    if conc_formula not in expanded:
                        next_expand.append(conc_formula)
                    for pf in prem_formulas:
                        if pf not in expanded:
                            next_expand.append(pf)
            to_expand = next_expand
            depth += 1
        graph.build_or_factors()
        graph.build_neg_factors()
        return graph

    def propositions(self) -> list[Variable]:
        return [v for v in self.variables.values() if v.is_proposition]

    def groups(self) -> list[Variable]:
        return [v for v in self.variables.values() if v.is_group]

    def prob(self, formula: str) -> float:
        if formula in self.formula_to_id:
            return self.variables[self.formula_to_id[formula]].prob
        return 0.0

    def stats(self) -> dict:
        props = self.propositions()
        return {
            "propositions": len(props),
            "groups": len(self.groups()),
            "and_factors": len([f for f in self.factors.values() if f.factor_type == FactorType.AND]),
            "or_factors": len([f for f in self.factors.values() if f.factor_type == FactorType.OR]),
            "neg_factors": len([f for f in self.factors.values() if f.factor_type == FactorType.NEG]),
            "rules": len(self.rules),
            "evidence": sum(1 for p in props if p.is_evidence),
        }
"""
Belief propagation for QBBN graphs.
"""

import math
from dataclasses import dataclass, field
from message.core.qbbn import QBBNGraph, FactorType, NodeType


DEBUG = False


def debug(*args):
    if DEBUG:
        print("[BP]", *args)


@dataclass
class BPTrace:
    iterations: list[dict[str, float]] = field(default_factory=list)


def belief_propagation(
    graph: QBBNGraph,
    iterations: int = 20,
    damping: float = 0.5,
    tolerance: float = 1e-6,
) -> BPTrace:
    trace = BPTrace()
    pi: dict[str, list[float]] = {}
    lam: dict[str, list[float]] = {}
    for var in graph.variables.values():
        if var.is_evidence:
            if var.evidence_value:
                pi[var.id] = [0.0, 1.0]
                lam[var.id] = [0.0, 1.0]
            else:
                pi[var.id] = [1.0, 0.0]
                lam[var.id] = [1.0, 0.0]
        else:
            pi[var.id] = [0.5, 0.5]
            lam[var.id] = [1.0, 1.0]
    and_factors = [f for f in graph.factors.values() if f.factor_type == FactorType.AND]
    or_factors = [f for f in graph.factors.values() if f.factor_type == FactorType.OR]
    neg_factors = [f for f in graph.factors.values() if f.factor_type == FactorType.NEG]

    def compute_belief(var_id):
        p0 = pi[var_id][0] * lam[var_id][0]
        p1 = pi[var_id][1] * lam[var_id][1]
        total = p0 + p1
        if total > 0:
            return p1 / total
        return 0.5

    trace.iterations.append({v.id: compute_belief(v.id) for v in graph.variables.values()})

    for iteration in range(iterations):
        old_beliefs = {v.id: compute_belief(v.id) for v in graph.variables.values()}

        # FORWARD: propositions -> AND -> groups
        for factor in and_factors:
            prob_all_true = 1.0
            for p_id in factor.input_ids:
                prob_all_true *= pi[p_id][1]
            g_id = factor.output_id
            if not graph.variables[g_id].is_evidence:
                pi[g_id] = [1.0 - prob_all_true, prob_all_true]

        # FORWARD: groups -> OR -> propositions
        for factor in or_factors:
            p_id = factor.output_id
            if graph.variables[p_id].is_evidence:
                continue
            base_leak = 0.001
            prob_not_caused = 1.0 - base_leak
            for g_id in factor.input_ids:
                weight = factor.weights.get(g_id, 99.0)
                g_prob = pi[g_id][1]
                if weight >= 50:
                    leak = 0.0
                elif weight <= -50:
                    leak = 1.0
                else:
                    leak = math.exp(-weight)
                prob_not_caused *= (1.0 - g_prob) + g_prob * leak
            prob_true = 1.0 - prob_not_caused
            pi[p_id] = [1.0 - prob_true, prob_true]

        # NEG forward
        for factor in neg_factors:
            pos_id = factor.input_ids[0]
            neg_id = factor.output_id
            if graph.variables[neg_id].is_evidence and not graph.variables[pos_id].is_evidence:
                pi[pos_id] = [pi[neg_id][1], pi[neg_id][0]]
            elif graph.variables[pos_id].is_evidence and not graph.variables[neg_id].is_evidence:
                pi[neg_id] = [pi[pos_id][1], pi[pos_id][0]]

        # BACKWARD: OR -> groups
        for factor in or_factors:
            p_id = factor.output_id
            lam_p = lam[p_id]
            for g_id in factor.input_ids:
                if graph.variables[g_id].is_evidence:
                    continue
                weight = factor.weights.get(g_id, 99.0)
                if weight >= 50:
                    lam_g_0 = lam_p[0] + lam_p[1]
                    lam_g_1 = lam_p[1]
                else:
                    leak = math.exp(-weight)
                    lam_g_0 = lam_p[0] + lam_p[1]
                    lam_g_1 = lam_p[0] * leak + lam_p[1]
                lam[g_id] = [lam_g_0, lam_g_1]

        # BACKWARD: AND -> propositions
        for factor in and_factors:
            g_id = factor.output_id
            lam_g = lam[g_id]
            for i, p_id in enumerate(factor.input_ids):
                if graph.variables[p_id].is_evidence:
                    continue
                other_prob_true = 1.0
                for j, other_p_id in enumerate(factor.input_ids):
                    if j != i:
                        other_prob_true *= pi[other_p_id][1]
                lam_p_1 = other_prob_true * lam_g[1] + (1 - other_prob_true) * lam_g[0]
                lam_p_0 = 0 * lam_g[1] + 1 * lam_g[0]
                lam[p_id] = [lam_p_0, lam_p_1]

        # NEG backward
        for factor in neg_factors:
            pos_id = factor.input_ids[0]
            neg_id = factor.output_id
            if not graph.variables[pos_id].is_evidence:
                lam_neg = lam[neg_id]
                lam[pos_id] = [lam_neg[1], lam_neg[0]]
            if not graph.variables[neg_id].is_evidence:
                lam_pos = lam[pos_id]
                lam[neg_id] = [lam_pos[1], lam_pos[0]]

        # UPDATE BELIEFS
        for var in graph.variables.values():
            if var.is_evidence:
                continue
            p0 = pi[var.id][0] * lam[var.id][0]
            p1 = pi[var.id][1] * lam[var.id][1]
            total = p0 + p1
            if total > 0:
                prob = p1 / total
            else:
                prob = 0.5
            old_prob = old_beliefs[var.id]
            new_prob = damping * old_prob + (1 - damping) * prob
            var.belief = [1.0 - new_prob, new_prob]

        trace.iterations.append({v.id: compute_belief(v.id) for v in graph.variables.values()})

        new_beliefs = {v.id: v.prob for v in graph.variables.values()}
        max_diff = max(abs(new_beliefs[v.id] - old_beliefs[v.id]) for v in graph.variables.values())

        if max_diff < tolerance:
            break

    return trace
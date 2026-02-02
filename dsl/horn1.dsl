# horn1 — Basic Horn clauses with typed entities and binary predicates
#
# The simplest logic: entities, facts, rules, queries.
# All predicates are binary positional: pred(arg1, arg2)
# Rules can have multiple premises joined by &
# Variables are typed; type constrains grounding domain
# No roles, no events, no time, no degree, no modality, no negation

# === Entity declaration ===
# entity NAME : TYPE

# === Types (open — any string is a valid type) ===
# type is declared implicitly by entity declarations

# === Facts ===
# PREDICATE(ARG1, ARG2)
# Both args must be declared entities or class constants

# === Rules ===
# rule [VAR:TYPE, ...]: PRED(A,B) & PRED(C,D) -> PRED(E,F)
# Variables ground over entities of matching type
# & joins premises into AND gate

# === Queries ===
# ? PREDICATE(ARG1, ARG2)
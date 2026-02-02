# horn2 — Typed semantic roles with negation, modality, and weighted rules
#
# Extends horn1 with:
# - Two base types: e (entity) and s (sentence)
# - Named semantic roles on predicates: pred(role: value, role: value)
# - Type signatures using square bracket notation: [e, e], [s, e], etc.
# - Negation prefix: not pred(...)
# - Weighted rules: rule [x:e] (0.7): premise -> conclusion
# - Intensional verbs: predicates of type [s, e] holding propositions as data
# - Sentence operators: predicates of type [s]
# - Ground rules: rule: fact1 -> fact2 (no variables)
# - Zero-argument propositions: raining()
# - Higher order predicates: [[e,e], e, e] (predicates taking predicates)
# - Inequality: not_equal(theme: x, reference: y) built-in

# === Base types ===
type e    # entity — an individual thing
type s    # sentence — a proposition / truth value

# === Type notation ===
# [e]              property of one entity
# [e, e]           relation between two entities
# [e, e, e]        ternary relation
# [e, e, e, e]     quaternary relation
# [s]              sentence operator (necessary, possible)
# [s, e]           intensional verb (believe, want, can, should)
# [[e,e], e, e]    higher order (each_other)

# === Entity declaration ===
# entity NAME : e

# === Predicate declaration (optional, for type checking) ===
# predicate NAME : [TYPE, ...] { role: TYPE, role: TYPE, ... }

# === Facts ===
# PRED(role: value, role: value)
# not PRED(role: value, role: value)
# Values must be declared entities, or nested sentences for s-typed roles

# === Zero-argument propositions ===
# PRED()

# === Rules ===
# rule [VAR:TYPE, ...]: PREMISE & PREMISE -> CONCLUSION
# rule [VAR:TYPE, ...] (WEIGHT): PREMISE -> CONCLUSION
# rule: GROUND_PREMISE -> GROUND_CONCLUSION

# === Queries ===
# ? PRED(role: value, role: value)
# ? not PRED(role: value, role: value)

# === Built-in predicates ===
predicate not_equal : [e, e] { theme: e, reference: e }
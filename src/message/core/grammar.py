"""
Grammar rules for mapping typed token sequences to logical forms.

Each rule has:
  - A name
  - A pattern: sequence of typed slots and keywords
  - A semantic template: how to produce the logical output

Pattern elements:
  - "$x:e"              — match a token that resolves to an entity
  - "$P:{theme:e}"      — match a token that resolves to a predicate with these roles
  - "$V:{agent:e,patient:e}" — match a binary predicate
  - "COP"               — match a copular verb
  - "ALL"               — match a universal quantifier
  - "IF"                — match conditional marker
  - "THEN"              — match consequent marker
  - "AND"               — match conjunction
  - "LIT:word"          — match a literal word exactly
  - "_"                 — match and ignore any single token
"""

import re
from dataclasses import dataclass, field


# Grammar keywords — surface forms that map to grammar symbols
KEYWORDS = {
    "COP": {"is", "are", "was", "were", "am", "be"},
    "ALL": {"all", "every"},
    "IF": {"if", "when", "whenever"},
    "THEN": {"then"},
    "AND": {"and", "&"},
    "NOT": {"not", "never", "no"},
    "A": {"a", "an"},
    "SOMEONE": {"someone", "somebody", "anyone"},
}

# Reverse index: surface form -> keyword
KEYWORD_INDEX = {}
for kw, forms in KEYWORDS.items():
    for form in forms:
        KEYWORD_INDEX[form.lower()] = kw

# Ignored tokens — matched by "_" or skipped
IGNORED = {".", ",", "!", "?", "the", "it", "they", "he", "she", "them", "to", "of", "than"}


@dataclass
class PatternSlot:
    """A single slot in a grammar rule pattern."""
    kind: str  # "var", "keyword", "ignore", "lit"
    name: str | None = None  # variable name like "$x", "$P", "$V"
    type_constraint: str | None = None  # "e" or "{theme:e}" or "{agent:e,patient:e}"
    keyword: str | None = None  # "COP", "ALL", etc.
    literal: str | None = None  # for LIT:word — exact word match


@dataclass
class GrammarRule:
    """A grammar rule: pattern → semantic template."""
    name: str
    pattern: list[PatternSlot]
    template: str  # semantic output template with $variables
    output_type: str = "fact"  # "fact" or "rule"

    def __repr__(self):
        slots = []
        for s in self.pattern:
            if s.kind == "var":
                slots.append(f"{s.name}:{s.type_constraint}")
            elif s.kind == "keyword":
                slots.append(s.keyword)
            elif s.kind == "lit":
                slots.append(f"'{s.literal}'")
            else:
                slots.append("_")
        return f"Rule({self.name}: {' '.join(slots)} → {self.template})"


def _slot(spec: str) -> PatternSlot:
    """Parse a pattern slot specification."""
    if spec == "_":
        return PatternSlot(kind="ignore")
    if spec.startswith("$"):
        # Variable: $x:e or $P:{theme:e}
        if ":" in spec:
            name, type_str = spec.split(":", 1)
            return PatternSlot(kind="var", name=name, type_constraint=type_str)
        return PatternSlot(kind="var", name=spec)
    if spec.startswith("LIT:"):
        return PatternSlot(kind="lit", literal=spec[4:].lower())
    # Keyword
    return PatternSlot(kind="keyword", keyword=spec)


def _rule(name: str, pattern_str: str, template: str, output_type: str = "fact") -> GrammarRule:
    """Convenience: build a rule from a pattern string."""
    slots = [_slot(s) for s in pattern_str.split()]
    return GrammarRule(name=name, pattern=slots, template=template, output_type=output_type)


# ============================================================
# THE GRAMMAR
# ============================================================

GRAMMAR: list[GrammarRule] = [
    # --- Copular facts: "Bob is a poodle" ---
    _rule("copular_fact",
          "$x:e COP _ $P:{theme:e}",
          "$P(theme: $x)",
          "fact"),

    # --- Copular facts without article: "Bob is mortal" ---
    _rule("copular_fact_bare",
          "$x:e COP $P:{theme:e}",
          "$P(theme: $x)",
          "fact"),

    # --- Negated copular fact: "Zeus is not mortal" ---
    _rule("negated_copular_fact",
          "$x:e COP NOT $P:{theme:e}",
          "not $P(theme: $x)",
          "fact"),

    # --- Copular universal: "All men are mortal" ---
    _rule("copular_universal",
          "ALL $P:{theme:e} COP $Q:{theme:e}",
          "always [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    # --- Negated universal: "No gods are mortal" ---
    _rule("negated_universal",
          "NOT $P:{theme:e} COP $Q:{theme:e}",
          "never [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    # --- Copular generic: "A sparrow is a bird" ---
    _rule("copular_generic",
          "A $P:{theme:e} COP _ $Q:{theme:e}",
          "always [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    # --- Prepositional copular fact: "Alice is taller than Bob" / "Paris is north of Lyon" / "The ball is in the box" ---
    _rule("prepositional_copular_fact",
          "$x:e COP $V:{theme:e,reference:e} $y:e",
          "$V(theme: $x, reference: $y)",
          "fact"),

    # --- Copular identity: "Clark Kent is Superman" ---
    _rule("copular_identity",
          "$x:e COP $y:e",
          "identity(theme: $x, reference: $y)",
          "fact"),

    # --- Transitive fact: "Jack trusts Jill" ---
    _rule("transitive_fact",
          "$x:e $V:{agent:e,patient:e} $y:e",
          "$V(agent: $x, patient: $y)",
          "fact"),

    # --- Intransitive predicate fact: "Superman can fly" ---
    _rule("intransitive_fact",
          "$x:e $P:{theme:e}",
          "$P(theme: $x)",
          "fact"),

    # --- Reciprocal conditional: "If two P V each other, they are R" ---
    _rule("reciprocal_conditional",
          "IF _ $P:{theme:e} $V:{agent:e,patient:e} LIT:each LIT:other _ COP $R:{agent:e,patient:e}",
          "always [x:e, y:e]: $P(theme: x) & $P(theme: y) & $V(agent: x, patient: y) & $V(agent: y, patient: x) -> $R(agent: x, patient: y)",
          "rule"),

    # --- Conditional symmetry: "If X is R to Y, then Y is R to X" ---
    _rule("conditional_symmetry",
          "IF $x:e COP $V:{agent:e,patient:e} $y:e THEN $y2:e COP $V2:{agent:e,patient:e} $x2:e",
          "always [x:e, y:e]: $V(agent: x, patient: y) -> $V(agent: y, patient: x)",
          "rule"),

    # --- Conditional transitivity (explicit): "If X is in Y and Y is in Z, then X is in Z" ---
    _rule("conditional_transitivity",
          "IF $a:e COP $V:{theme:e,reference:e} $b:e AND $c:e COP $V2:{theme:e,reference:e} $d:e THEN $e:e COP $V3:{theme:e,reference:e} $f:e",
          "always [x:e, y:e, z:e]: $V(theme: x, reference: y) & $V(theme: y, reference: z) -> $V(theme: x, reference: z)",
          "rule"),

    # --- Zero-arg fact: "It is raining" ---
    _rule("zero_arg_fact",
          "$P:{}",
          "$P()",
          "fact"),
]


def match_sentence(tokens: list[str], lexicon) -> list[dict]:
    """Try all grammar rules against a token sequence. Returns list of matches."""
    matches = []
    for rule in GRAMMAR:
        bindings = _try_match(rule.pattern, tokens, lexicon)
        if bindings is not None:
            output = _apply_template(rule.template, bindings)
            matches.append({
                "rule": rule,
                "bindings": bindings,
                "output": output,
                "output_type": rule.output_type,
            })
    return matches


def _try_match(pattern: list[PatternSlot], tokens: list[str], lexicon) -> dict | None:
    """Try to match a pattern against tokens. Returns bindings or None."""
    bindings = {}
    return _match_recursive(pattern, 0, tokens, 0, bindings, lexicon)


def _match_recursive(pattern, pi, tokens, ti, bindings, lexicon) -> dict | None:
    """Recursive pattern matcher with backtracking."""
    # Skip trailing ignored tokens — but NOT if next pattern slot is _ or lit
    skip_ignored = True
    if pi < len(pattern) and pattern[pi].kind in ("ignore", "lit"):
        skip_ignored = False

    if skip_ignored:
        while ti < len(tokens) and _clean(tokens[ti]) in IGNORED:
            ti += 1

    # Both exhausted — success
    if pi >= len(pattern) and ti >= len(tokens):
        return dict(bindings)

    # Pattern exhausted but tokens remain
    if pi >= len(pattern):
        while ti < len(tokens) and _clean(tokens[ti]) in IGNORED:
            ti += 1
        return dict(bindings) if ti >= len(tokens) else None

    # Tokens exhausted but pattern remains
    if ti >= len(tokens):
        return None

    slot = pattern[pi]
    token = _clean(tokens[ti])

    if slot.kind == "ignore":
        # Match any single token
        return _match_recursive(pattern, pi + 1, tokens, ti + 1, bindings, lexicon)

    elif slot.kind == "lit":
        # Match exact literal word
        if token == slot.literal:
            return _match_recursive(pattern, pi + 1, tokens, ti + 1, bindings, lexicon)
        # Try skipping ignored token
        if token in IGNORED:
            return _match_recursive(pattern, pi, tokens, ti + 1, bindings, lexicon)
        return None

    elif slot.kind == "keyword":
        expected_forms = KEYWORDS.get(slot.keyword, set())
        if token in expected_forms:
            return _match_recursive(pattern, pi + 1, tokens, ti + 1, bindings, lexicon)
        if token in IGNORED:
            return _match_recursive(pattern, pi, tokens, ti + 1, bindings, lexicon)
        return None

    elif slot.kind == "var":
        # Try to match token(s) against lexicon using multi-word lookup
        lookup = lexicon.lookup_at(tokens, ti)
        if lookup:
            canonical, category, consumed = lookup

            # Check type constraint
            if slot.type_constraint:
                actual_type = lexicon.get_type(canonical)
                if actual_type == slot.type_constraint:
                    # Bind variable
                    bindings[slot.name] = (canonical, actual_type)
                    result = _match_recursive(pattern, pi + 1, tokens, ti + consumed, bindings, lexicon)
                    if result is not None:
                        return result
                    # Backtrack
                    del bindings[slot.name]
            else:
                # No type constraint — accept any lexicon match
                actual_type = lexicon.get_type(canonical)
                bindings[slot.name] = (canonical, actual_type)
                result = _match_recursive(pattern, pi + 1, tokens, ti + consumed, bindings, lexicon)
                if result is not None:
                    return result
                del bindings[slot.name]

        # No lexicon match or type mismatch — try skipping as ignored
        if token in IGNORED:
            return _match_recursive(pattern, pi, tokens, ti + 1, bindings, lexicon)

        return None

    return None


def _clean(token: str) -> str:
    """Lowercase and strip trailing punctuation."""
    return token.lower().rstrip(".,!?;:")


def _apply_template(template: str, bindings: dict) -> str:
    """Fill in a semantic template with bound values."""
    result = template
    for var_name, (canonical, _) in bindings.items():
        result = result.replace(var_name, canonical)
    return result
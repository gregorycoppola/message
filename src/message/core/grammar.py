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
  - "_"                 — match and ignore any single token
"""

import re
from dataclasses import dataclass, field


# Grammar keywords — surface forms that map to grammar symbols
KEYWORDS = {
    "COP": {"is", "are", "was", "were", "am", "be"},
    "ALL": {"all", "every", "each"},
    "IF": {"if", "when", "whenever"},
    "THEN": {"then", ","},
    "AND": {"and", "&"},
    "NOT": {"not", "never", "no"},
    "A": {"a", "an"},
}

# Reverse index: surface form -> keyword
KEYWORD_INDEX = {}
for kw, forms in KEYWORDS.items():
    for form in forms:
        KEYWORD_INDEX[form.lower()] = kw

# Ignored tokens — matched by "_" or skipped
IGNORED = {".", ",", "!", "?", "the", "it", "they", "he", "she", "them"}


@dataclass
class PatternSlot:
    """A single slot in a grammar rule pattern."""
    kind: str  # "var", "keyword", "ignore"
    name: str | None = None  # variable name like "$x", "$P", "$V"
    type_constraint: str | None = None  # "e" or "{theme:e}" or "{agent:e,patient:e}"
    keyword: str | None = None  # "COP", "ALL", etc.


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

    # --- Copular universal: "All men are mortal" ---
    _rule("copular_universal",
          "ALL $P:{theme:e} COP $Q:{theme:e}",
          "always [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    # --- Copular universal with article: "All poodles are dogs" ---
    # (same pattern — "poodles" and "dogs" are both {theme:e})

    # --- Copular generic: "A sparrow is a bird" ---
    _rule("copular_generic",
          "A $P:{theme:e} COP _ $Q:{theme:e}",
          "always [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    # --- Transitive fact: "Jack trusts Jill" ---
    _rule("transitive_fact",
          "$x:e $V:{agent:e,patient:e} $y:e",
          "$V(agent: $x, patient: $y)",
          "fact"),

    # --- Transitive fact with article: "Mary loves a man" ---
    # TODO: need to handle indefinite objects

    # --- Three-place fact: "John threw a rock at the window" ---
    # TODO: prepositions as role markers

    # --- Conditional with copular: "If X is Y, then Z" ---
    # TODO: complex conditionals

    # --- Intransitive fact: "It is raining" ---
    _rule("zero_arg_fact",
          "$P:{}",
          "$P()",
          "fact"),
]


def match_sentence(tokens: list[str], lexicon) -> list[dict]:
    """Try all grammar rules against a token sequence. Returns list of matches.

    Each match is:
        {
            "rule": GrammarRule,
            "bindings": {var_name: (canonical, type)},
            "output": str  — the derived logical form
        }
    """
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
    """Try to match a pattern against tokens. Returns bindings or None.

    Uses backtracking to handle ignored tokens (articles, punctuation).
    """
    bindings = {}
    return _match_recursive(pattern, 0, tokens, 0, bindings, lexicon)


def _match_recursive(pattern, pi, tokens, ti, bindings, lexicon) -> dict | None:
    """Recursive pattern matcher with backtracking."""
    # Skip trailing ignored tokens
    while ti < len(tokens) and tokens[ti].lower().rstrip(".,!?") in IGNORED:
        ti += 1

    # Both exhausted — success
    if pi >= len(pattern) and ti >= len(tokens):
        return dict(bindings)

    # Pattern exhausted but tokens remain (skip trailing punctuation/ignored)
    if pi >= len(pattern):
        while ti < len(tokens) and tokens[ti].lower().rstrip(".,!?") in IGNORED:
            ti += 1
        return dict(bindings) if ti >= len(tokens) else None

    # Tokens exhausted but pattern remains
    if ti >= len(tokens):
        return None

    slot = pattern[pi]
    token = tokens[ti].lower().rstrip(".,!?")

    if slot.kind == "ignore":
        # Match any single token
        return _match_recursive(pattern, pi + 1, tokens, ti + 1, bindings, lexicon)

    elif slot.kind == "keyword":
        # Check if token is this keyword
        expected_forms = KEYWORDS.get(slot.keyword, set())
        if token in expected_forms:
            return _match_recursive(pattern, pi + 1, tokens, ti + 1, bindings, lexicon)
        # Also try skipping an ignored token first
        if token in IGNORED:
            return _match_recursive(pattern, pi, tokens, ti + 1, bindings, lexicon)
        return None

    elif slot.kind == "var":
        # Try to match token against lexicon
        lookup = lexicon.lookup(token)
        if not lookup:
            # Not in lexicon — try skipping as ignored
            if token in IGNORED:
                return _match_recursive(pattern, pi, tokens, ti + 1, bindings, lexicon)
            return None

        canonical, category = lookup

        # Check type constraint
        if slot.type_constraint:
            actual_type = lexicon.get_type(canonical)
            if actual_type != slot.type_constraint:
                # Type mismatch — try skipping as ignored
                if token in IGNORED:
                    return _match_recursive(pattern, pi, tokens, ti + 1, bindings, lexicon)
                return None

        # Bind variable
        actual_type = lexicon.get_type(canonical)
        bindings[slot.name] = (canonical, actual_type)
        result = _match_recursive(pattern, pi + 1, tokens, ti + 1, bindings, lexicon)
        if result is not None:
            return result
        # Backtrack
        del bindings[slot.name]

        # Try skipping this token as ignored
        if token in IGNORED:
            return _match_recursive(pattern, pi, tokens, ti + 1, bindings, lexicon)

        return None

    return None


def _apply_template(template: str, bindings: dict) -> str:
    """Fill in a semantic template with bound values."""
    result = template
    for var_name, (canonical, _) in bindings.items():
        result = result.replace(var_name, canonical)
    return result
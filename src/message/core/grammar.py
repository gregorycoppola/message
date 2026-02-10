"""
Grammar engine — pattern matching and semantic template application.

Pattern elements:
  - "$x:e"              — match a token that resolves to an entity
  - "$P:{theme:e}"      — match a token that resolves to a predicate with these roles
  - "$V:{agent:e,patient:e}" — match a binary predicate
  - "COP"               — match a copular verb
  - "ALL"               — match a universal quantifier
  - "IF"                — match conditional marker
  - "THEN"              — match consequent marker
  - "AND"               — match conjunction
  - "NOT"               — match negation
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
    "NOT": {"not", "never", "no", "n't"},
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
    name: str | None = None
    type_constraint: str | None = None
    keyword: str | None = None
    literal: str | None = None


@dataclass
class GrammarRule:
    """A grammar rule: pattern → semantic template."""
    name: str
    pattern: list[PatternSlot]
    template: str
    output_type: str = "fact"

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
        if ":" in spec:
            name, type_str = spec.split(":", 1)
            return PatternSlot(kind="var", name=name, type_constraint=type_str)
        return PatternSlot(kind="var", name=spec)
    if spec.startswith("LIT:"):
        return PatternSlot(kind="lit", literal=spec[4:].lower())
    return PatternSlot(kind="keyword", keyword=spec)


def _rule(name: str, pattern_str: str, template: str, output_type: str = "fact") -> GrammarRule:
    """Build a rule from a pattern string."""
    slots = [_slot(s) for s in pattern_str.split()]
    return GrammarRule(name=name, pattern=slots, template=template, output_type=output_type)


def match_sentence(tokens: list[str], lexicon) -> list[dict]:
    """Try all grammar rules against a token sequence. Returns list of matches."""
    from message.core.rules import GRAMMAR

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
    skip_ignored = True
    if pi < len(pattern) and pattern[pi].kind in ("ignore", "lit"):
        skip_ignored = False

    if skip_ignored:
        while ti < len(tokens) and _clean(tokens[ti]) in IGNORED:
            ti += 1

    if pi >= len(pattern) and ti >= len(tokens):
        return dict(bindings)

    if pi >= len(pattern):
        while ti < len(tokens) and _clean(tokens[ti]) in IGNORED:
            ti += 1
        return dict(bindings) if ti >= len(tokens) else None

    if ti >= len(tokens):
        return None

    slot = pattern[pi]
    token = _clean(tokens[ti])

    if slot.kind == "ignore":
        return _match_recursive(pattern, pi + 1, tokens, ti + 1, bindings, lexicon)

    elif slot.kind == "lit":
        if token == slot.literal:
            return _match_recursive(pattern, pi + 1, tokens, ti + 1, bindings, lexicon)
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
        lookup = lexicon.lookup_at(tokens, ti)
        if lookup:
            canonical, category, consumed = lookup

            if slot.type_constraint:
                actual_type = lexicon.get_type(canonical)
                if actual_type == slot.type_constraint:
                    bindings[slot.name] = (canonical, actual_type)
                    result = _match_recursive(pattern, pi + 1, tokens, ti + consumed, bindings, lexicon)
                    if result is not None:
                        return result
                    del bindings[slot.name]
            else:
                actual_type = lexicon.get_type(canonical)
                bindings[slot.name] = (canonical, actual_type)
                result = _match_recursive(pattern, pi + 1, tokens, ti + consumed, bindings, lexicon)
                if result is not None:
                    return result
                del bindings[slot.name]

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
"""
Grammar rules — the GRAMMAR list.

Each rule maps a typed token pattern to a semantic template.
"""
from message.core.grammar import _rule


GRAMMAR = [
    # --- Copular facts: "Bob is a poodle" ---
    _rule("copular_fact",
          "$x:e COP A $P:{theme:e}",
          "$P(theme: $x)",
          "fact"),

    _rule("copular_fact_bare",
          "$x:e COP $P:{theme:e}",
          "$P(theme: $x)",
          "fact"),

    _rule("negated_copular_fact",
          "$x:e COP NOT $P:{theme:e}",
          "not $P(theme: $x)",
          "fact"),

    # --- Copular universals ---
    _rule("copular_universal",
          "ALL $P:{theme:e} COP $Q:{theme:e}",
          "always [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    _rule("negated_universal",
          "NOT $P:{theme:e} COP $Q:{theme:e}",
          "never [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    _rule("copular_generic",
          "A $P:{theme:e} COP A $Q:{theme:e}",
          "always [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    # --- Prepositional copular: "Alice is taller than Bob" ---
    _rule("prepositional_copular_fact",
          "$x:e COP $V:{theme:e,reference:e} $y:e",
          "$V(theme: $x, reference: $y)",
          "fact"),

    # --- Identity: "Clark Kent is Superman" ---
    _rule("copular_identity",
          "$x:e COP $y:e",
          "identity(theme: $x, reference: $y)",
          "fact"),

    # --- Transitive: "Jack trusts Jill" ---
    _rule("transitive_fact",
          "$x:e $V:{agent:e,patient:e} $y:e",
          "$V(agent: $x, patient: $y)",
          "fact"),

    # --- Intransitive: "Superman flies" ---
    _rule("intransitive_fact",
          "$x:e $P:{theme:e}",
          "$P(theme: $x)",
          "fact"),

    # --- Reciprocal conditional: "If two P V each other, they are R" ---
    _rule("reciprocal_conditional",
          "IF _ $P:{theme:e} $V:{agent:e,patient:e} LIT:each LIT:other _ COP $R:{agent:e,patient:e}",
          "always [x:e, y:e]: $P(theme: x) & $P(theme: y) & $V(agent: x, patient: y) & $V(agent: y, patient: x) -> $R(agent: x, patient: y)",
          "rule"),

    # --- Conditional prepositional copular: "If a man is king of a country, he is successful" ---
    _rule("conditional_prep_copular",
          "IF A $P:{theme:e} COP $V:{theme:e,reference:e} A $Q:{theme:e} _ COP $R:{theme:e}",
          "always [x:e, c:e]: $P(theme: x) & $V(theme: x, reference: c) & $Q(theme: c) -> $R(theme: x)",
          "rule"),

    # --- Conditional transitive: "If a girl loves a man, she is ambitious" ---
    _rule("conditional_transitive",
          "IF A $P:{theme:e} $V:{agent:e,patient:e} A $Q:{theme:e} _ COP $R:{theme:e}",
          "always [x:e, y:e]: $P(theme: x) & $V(agent: x, patient: y) & $Q(theme: y) -> $R(theme: x)",
          "rule"),

    # --- Conditional someone copular: "If someone is funny, they are liked" ---
    _rule("conditional_someone_copular",
          "IF SOMEONE COP $P:{theme:e} _ COP $Q:{theme:e}",
          "always [x:e]: $P(theme: x) -> $Q(theme: x)",
          "rule"),

    # --- Conditional symmetry: "If X is R to Y, then Y is R to X" ---
    _rule("conditional_symmetry",
          "IF $x:e COP $V:{agent:e,patient:e} $y:e THEN $y2:e COP $V2:{agent:e,patient:e} $x2:e",
          "always [x:e, y:e]: $V(agent: x, patient: y) -> $V(agent: y, patient: x)",
          "rule"),

    # --- Conditional transitivity: "If X is in Y and Y is in Z, then X is in Z" ---
    _rule("conditional_transitivity",
          "IF $a:e COP $V:{theme:e,reference:e} $b:e AND $c:e COP $V2:{theme:e,reference:e} $d:e THEN $e:e COP $V3:{theme:e,reference:e} $f:e",
          "always [x:e, y:e, z:e]: $V(theme: x, reference: y) & $V(theme: y, reference: z) -> $V(theme: x, reference: z)",
          "rule"),

    # --- Zero-arg fact ---
    _rule("zero_arg_fact",
          "$P:{}",
          "$P()",
          "fact"),

    # --- Conditional symmetry (theme/reference): "If John is married to Mary, then Mary is married to John" ---
_rule("conditional_symmetry_prep",
      "IF $x:e COP $V:{theme:e,reference:e} $y:e THEN $y2:e COP $V2:{theme:e,reference:e} $x2:e",
      "always [x:e, y:e]: $V(theme: x, reference: y) -> $V(theme: y, reference: x)",
      "rule"),
]

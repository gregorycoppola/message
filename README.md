# message

A semantic representation toolkit with two test suites covering a natural language → logic → inference pipeline.

## Coverage Tests

### Syntax: `message coverage parse`

Tests the **grammar-based parser** — takes natural language documents and lexicons, applies pattern-matching grammar rules, and verifies that the correct logical forms (facts) are derived.

- **Input**: `.document` (natural language sentences) + `.lexicon` (word definitions with syntactic categories and forms)
- **Output**: Logical facts like `trust(agent: jack, patient: jill)`
- **Location**: `coverage/syntax/` — 12 tests, 33 sentences, 33 gold facts
- **What it validates**: Tokenization, lexicon lookup, grammar rule matching, fact generation

### Inference: `message coverage verify`

Tests the **QBBN inference engine** — takes hand-written logical facts, rules, and queries, builds a factor graph, runs belief propagation, and checks that the correct yes/no/unknown answer is derived.

- **Input**: `.lexicon` (predicate/entity declarations) + `.facts` (propositions and rules) + `.query` (what to infer) + `.expected` (yes/no/unknown)
- **Output**: Posterior probability via belief propagation
- **Location**: `coverage/inference/` — 44 tests across 22 categories
- **What it validates**: Logical parsing, Horn clause grounding, QBBN graph construction, noisy-OR belief propagation, negation, modality, quantifier scope

## Architecture

```
document + lexicon ──→ [grammar/parser] ──→ facts
                                              │
                            facts + query ──→ [QBBN inference] ──→ P(query)
```

The syntax layer (`message.core.grammar`, `parser`, `lexicon`) handles language → logic.
The inference layer (`message.core.logical_lang`, `horn`, `qbbn`, `qbbn_bp`) handles logic → probability.

## Usage

```bash
# Run syntax tests (grammar parser)
message coverage parse

# Run inference tests (QBBN belief propagation)
message coverage verify

# Parse a single document
message parse path/to/test.document path/to/test.lexicon -f path/to/test.facts
```

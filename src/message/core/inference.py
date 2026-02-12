"""
Inference engine: lexicon + facts + query -> QBBN -> answer.
"""

import sys
from pathlib import Path


def strip_glosses(text: str) -> str:
    """Remove gloss lines from lexicon text."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if line.startswith("  ") and stripped.startswith('"'):
            continue
        lines.append(line)
    return "\n".join(lines)


def run_inference(lexicon_text: str, facts_text: str, query_text: str) -> tuple[float | None, dict]:
    """Run inference on lexicon + facts + query. Returns (query_prob, beliefs)."""
    from message.core.logical_lang import parse_logical, format_predicate
    from message.core.horn import KnowledgeBase
    from message.core.qbbn import QBBNGraph
    from message.core.qbbn_bp import belief_propagation

    clean_lexicon = strip_glosses(lexicon_text)
    combined = clean_lexicon + "\n\n" + facts_text + "\n\n" + query_text

    doc = parse_logical(combined)
    kb = KnowledgeBase.from_logical_document(doc)

    if not doc.queries:
        return None, {}

    query_formula = format_predicate(doc.queries[0])
    graph = QBBNGraph.from_query(kb, query_formula)
    trace = belief_propagation(graph, iterations=20, damping=0.5)
    query_prob = graph.prob(query_formula)

    beliefs = {}
    for prop in graph.propositions():
        if prop.formula:
            beliefs[prop.formula] = prop.prob

    return query_prob, beliefs


def verify_all(coverage_dir: str, verbose: bool = False):
    """Verify all inference tests in a coverage directory."""
    root = Path(coverage_dir)
    results = []

    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue

        for facts_file in sorted(group_dir.glob("*.facts")):
            test_name = facts_file.stem
            test_path = group_dir / test_name

            lexicon_file = test_path.with_suffix(".lexicon")
            query_file = test_path.with_suffix(".query")
            expected_file = test_path.with_suffix(".expected")

            if not all(f.exists() for f in [lexicon_file, query_file, expected_file]):
                results.append((f"{group_dir.name}/{test_name}", "skip", "missing files"))
                continue

            lexicon_text = lexicon_file.read_text().strip()
            facts_text = facts_file.read_text().strip()
            query_text = query_file.read_text().strip()
            expected_answer = expected_file.read_text().strip()

            try:
                query_prob, beliefs = run_inference(lexicon_text, facts_text, query_text)

                if query_prob is not None:
                    if query_prob > 0.9:
                        answer = "yes"
                    elif query_prob < 0.1:
                        answer = "no"
                    else:
                        answer = "unknown"

                    if answer == expected_answer:
                        results.append((f"{group_dir.name}/{test_name}", "pass", f"P={query_prob:.3f}"))
                    else:
                        results.append((f"{group_dir.name}/{test_name}", "fail", f"got {answer}, expected {expected_answer}"))
                else:
                    results.append((f"{group_dir.name}/{test_name}", "fail", "no result"))

            except Exception as e:
                results.append((f"{group_dir.name}/{test_name}", "error", str(e)[:50]))

    # Print results
    passed = sum(1 for _, status, _ in results if status == "pass")
    failed = sum(1 for _, status, _ in results if status == "fail")
    errors = sum(1 for _, status, _ in results if status == "error")
    skipped = sum(1 for _, status, _ in results if status == "skip")

    print(f"{'═' * 60}")
    print(f"  Coverage Verification: {len(results)} tests")
    print(f"{'═' * 60}")

    for name, status, detail in results:
        if status == "pass":
            print(f"  ✅ {name:<40} {detail}")
        elif status == "fail":
            print(f"  ❌ {name:<40} {detail}")
        elif status == "error":
            print(f"  💥 {name:<40} {detail}")
        else:
            print(f"  ⊘  {name:<40} {detail}")

    print(f"{'═' * 60}")
    print(f"  ✅ Pass: {passed}  ❌ Fail: {failed}  💥 Error: {errors}  ⊘ Skip: {skipped}")
    print(f"{'═' * 60}")

    if failed > 0 or errors > 0:
        sys.exit(1)
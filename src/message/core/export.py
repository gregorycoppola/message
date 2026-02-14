"""
Export coverage test data and results as JSON for the visualizer.
"""
import json
from pathlib import Path


def export_parse_results(coverage_dir: str) -> dict:
    """Run all syntax coverage tests and return structured JSON."""
    from message.core.coverage import scan_tests, run_parse_coverage
    from message.core.lexicon import parse_lexicon
    from message.core.parser import parse_document

    tests = scan_tests(coverage_dir)
    parse_results = run_parse_coverage(tests)

    output = {
        "type": "parse",
        "summary": {
            "total_tests": len(parse_results),
            "passing": sum(1 for r in parse_results if r.fully_passing),
            "total_sentences": sum(r.total_sentences for r in parse_results if not r.skipped),
            "parsed_sentences": sum(r.parsed_sentences for r in parse_results if not r.skipped),
            "total_gold_facts": sum(r.total_gold_facts for r in parse_results if not r.skipped),
            "derived_gold_facts": sum(r.derived_gold_facts for r in parse_results if not r.skipped),
        },
        "tests": [],
    }

    for test, result in zip(tests, parse_results):
        if result.skipped:
            continue

        # Re-run parse to get detailed sentence data
        lexicon = parse_lexicon(test.lexicon)
        doc_parse = parse_document(test.document, lexicon)
        gold_facts = [line.strip() for line in test.facts.split("\n")
                      if line.strip() and not line.strip().startswith("#")]

        sentences = []
        for sp in doc_parse.sentences:
            sent_data = {
                "text": sp.sentence,
                "tokens": sp.tokens,
                "num_parses": sp.num_parses,
                "failed": sp.failed,
                "ambiguous": sp.is_ambiguous,
                "matches": [],
            }
            for match in sp.matches:
                bindings = {}
                for var, (canon, typ) in match["bindings"].items():
                    bindings[var] = {"canonical": canon, "type": typ}
                sent_data["matches"].append({
                    "rule": match["rule"].name,
                    "output": match["output"],
                    "output_type": match["output_type"],
                    "bindings": bindings,
                })
            sentences.append(sent_data)

        # Lexicon info
        lexicon_data = {
            "predicates": {},
            "entities": {},
        }
        for name, pred in lexicon.predicates.items():
            lexicon_data["predicates"][name] = {
                "roles": pred.roles,
                "forms": pred.forms,
                "gloss": pred.gloss,
            }
        for name, ent in lexicon.entities.items():
            lexicon_data["entities"][name] = {
                "type": ent.typ,
                "forms": ent.forms,
                "gloss": ent.gloss,
            }

        derived = doc_parse.all_facts
        gold_status = []
        for gf in gold_facts:
            gold_status.append({"fact": gf, "derived": gf in derived})
        extra = [d for d in derived if d not in gold_facts]

        output["tests"].append({
            "group": test.group,
            "name": test.name,
            "label": f"{test.group}/{test.name}",
            "document": test.document,
            "lexicon_raw": test.lexicon,
            "lexicon": lexicon_data,
            "sentences": sentences,
            "gold_facts": gold_status,
            "extra_facts": extra,
            "derived_facts": derived,
            "result": {
                "passing": result.fully_passing,
                "facts": f"{result.derived_gold_facts}/{result.total_gold_facts}",
                "sentences": f"{result.parsed_sentences}/{result.total_sentences}",
                "ambiguous": result.ambiguous_sentences,
            },
        })

    return output


def export_inference_results(coverage_dir: str) -> dict:
    """Run all inference coverage tests and return structured JSON."""
    from message.core.inference import run_inference, strip_glosses
    from message.core.logical_lang import parse_logical, format_predicate
    from message.core.horn import KnowledgeBase
    from message.core.qbbn import QBBNGraph
    from message.core.qbbn_bp import belief_propagation

    root = Path(coverage_dir)
    output = {
        "type": "inference",
        "summary": {
            "total_tests": 0,
            "passing": 0,
            "failing": 0,
            "errors": 0,
        },
        "tests": [],
    }

    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue

        for facts_file in sorted(group_dir.glob("*.facts")):
            test_name = facts_file.stem
            test_path = group_dir / test_name

            lexicon_file = test_path.with_suffix(".lexicon")
            query_file = test_path.with_suffix(".query")
            expected_file = test_path.with_suffix(".expected")
            description_file = test_path.with_suffix(".description")
            document_file = test_path.with_suffix(".document")
            question_file = test_path.with_suffix(".question")

            if not all(f.exists() for f in [lexicon_file, query_file, expected_file]):
                continue

            lexicon_text = lexicon_file.read_text().strip()
            facts_text = facts_file.read_text().strip()
            query_text = query_file.read_text().strip()
            expected_answer = expected_file.read_text().strip()
            description = description_file.read_text().strip() if description_file.exists() else ""
            document = document_file.read_text().strip() if document_file.exists() else ""
            question = question_file.read_text().strip() if question_file.exists() else ""

            output["summary"]["total_tests"] += 1

            test_data = {
                "group": group_dir.name,
                "name": test_name,
                "label": f"{group_dir.name}/{test_name}",
                "description": description,
                "document": document,
                "question": question,
                "lexicon_raw": lexicon_text,
                "facts_raw": facts_text,
                "query_raw": query_text,
                "expected": expected_answer,
            }

            try:
                # Run inference with full detail
                clean_lexicon = strip_glosses(lexicon_text)
                combined = clean_lexicon + "\n\n" + facts_text + "\n\n" + query_text
                doc = parse_logical(combined)
                kb = KnowledgeBase.from_logical_document(doc)

                query_formula = format_predicate(doc.queries[0])
                graph = QBBNGraph.from_query(kb, query_formula)
                trace = belief_propagation(graph, iterations=20, damping=0.5)
                query_prob = graph.prob(query_formula)

                if query_prob > 0.9:
                    answer = "yes"
                elif query_prob < 0.1:
                    answer = "no"
                else:
                    answer = "unknown"

                passed = answer == expected_answer

                # Factor graph structure
                propositions = []
                for p in graph.propositions():
                    propositions.append({
                        "id": p.id,
                        "formula": p.formula,
                        "prob": round(p.prob, 4),
                        "is_evidence": p.is_evidence,
                        "evidence_value": p.evidence_value,
                        "is_query": p.id == graph.query_id,
                    })

                groups = []
                for g in graph.groups():
                    groups.append({
                        "id": g.id,
                        "premise_ids": list(g.conjunct_ids),
                        "conclusion_id": g.conclusion_id,
                        "rule_id": g.rule_id,
                        "prob": round(g.prob, 4),
                    })

                factors = []
                for f in graph.factors.values():
                    factors.append({
                        "id": f.id,
                        "type": f.factor_type.value,
                        "input_ids": f.input_ids,
                        "output_id": f.output_id,
                        "weights": {k: round(v, 4) for k, v in f.weights.items()} if f.weights else {},
                    })

                rules = []
                for r in graph.rules.values():
                    rules.append({
                        "id": r.id,
                        "premises": r.premise_patterns,
                        "conclusion": r.conclusion_pattern,
                        "variables": [{"name": n, "type": t} for n, t in r.variables],
                        "weight": r.weight,
                    })

                # BP trace: per-iteration beliefs
                bp_trace = []
                for iteration_beliefs in trace.iterations:
                    bp_trace.append({
                        var_id: round(prob, 4)
                        for var_id, prob in iteration_beliefs.items()
                    })

                test_data.update({
                    "status": "pass" if passed else "fail",
                    "query_formula": query_formula,
                    "query_prob": round(query_prob, 4),
                    "answer": answer,
                    "graph": {
                        "propositions": propositions,
                        "groups": groups,
                        "factors": factors,
                        "rules": rules,
                        "stats": graph.stats(),
                    },
                    "bp_trace": bp_trace,
                    "iterations": len(trace.iterations) - 1,
                })

                if passed:
                    output["summary"]["passing"] += 1
                else:
                    output["summary"]["failing"] += 1

            except Exception as e:
                test_data.update({
                    "status": "error",
                    "error": str(e),
                })
                output["summary"]["errors"] += 1

            output["tests"].append(test_data)

    return output
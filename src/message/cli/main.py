"""
Message CLI — semantic representation toolkit.
"""
import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="message",
        description="Semantic representation toolkit",
    )
    subparsers = parser.add_subparsers(dest="command")

    # check
    check_p = subparsers.add_parser("check", help="Validate a .logic file")
    check_p.add_argument("file", help="Path to .logic file")
    check_p.set_defaults(func=cmd_check)

    # coverage
    cov_p = subparsers.add_parser("coverage", help="Coverage test management")
    cov_sub = cov_p.add_subparsers(dest="cov_command")

    cov_list = cov_sub.add_parser("list", help="List coverage tests")
    cov_list.set_defaults(func=cmd_coverage_list)

    cov_status = cov_sub.add_parser("status", help="Show coverage status")
    cov_status.set_defaults(func=cmd_coverage_status)

    # parse
    parse_p = subparsers.add_parser("parse", help="Parse a document against a lexicon")
    parse_p.add_argument("document", help="Path to .document file")
    parse_p.add_argument("lexicon", help="Path to .lexicon file")
    parse_p.add_argument("--facts", "-f", help="Path to .facts file (to verify against)")
    parse_p.add_argument("--verbose", "-v", action="store_true", help="Show detailed parse info")
    parse_p.set_defaults(func=cmd_parse)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.parse_args([args.command, "--help"])


def _repo_root():
    return Path(__file__).parent.parent.parent.parent


def cmd_check(args):
    """Validate a .logic file."""
    from message.core.checker import check_file

    if not args.file.endswith(".logic"):
        print(f"✗ File must have .logic extension: {args.file}")
        sys.exit(1)

    errors = check_file(args.file)
    if not errors:
        print(f"✓ {args.file}")
    else:
        print(f"✗ {args.file} has {len(errors)} errors:")
        for e in errors:
            print(f"  line {e.line}: {e.message}")
        sys.exit(1)


def cmd_coverage_list(args):
    """List all coverage tests."""
    from message.core.coverage import scan_tests

    coverage_dir = _repo_root() / "coverage"
    if not coverage_dir.is_dir():
        print("✗ No coverage directory found.")
        sys.exit(1)

    tests = scan_tests(str(coverage_dir))

    current_group = None
    for t in tests:
        if t.group != current_group:
            current_group = t.group
            print(f"\n  {current_group}/")
        print(f"    {t.name:30} {t.expected:8} {t.description[:50]}")

    print(f"\n  {len(tests)} tests total")


def cmd_coverage_status(args):
    """Show which tests are in new vs legacy format."""
    from message.core.coverage import scan_tests, coverage_status, print_status_summary

    coverage_dir = _repo_root() / "coverage"
    if not coverage_dir.is_dir():
        print("✗ No coverage directory found.")
        sys.exit(1)

    tests = scan_tests(str(coverage_dir))
    statuses = coverage_status(tests)

    print_status_summary(statuses)


def cmd_parse(args):
    """Parse a document against a lexicon and show results."""
    from message.core.parser import parse_document_files

    doc_path = args.document
    lex_path = args.lexicon

    # Auto-resolve: if given a base name, find the files
    if not doc_path.endswith(".document"):
        doc_path = doc_path + ".document"
    if not lex_path.endswith(".lexicon"):
        lex_path = lex_path + ".lexicon"

    result = parse_document_files(doc_path, lex_path)

    # Load gold facts if provided
    gold_facts = None
    if args.facts:
        facts_path = args.facts
        if not facts_path.endswith(".facts"):
            facts_path = facts_path + ".facts"
        with open(facts_path) as f:
            gold_facts = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    # Display results
    print(f"Lexicon: {len(result.lexicon.predicates)} predicates, {len(result.lexicon.entities)} entities")
    print(f"Sentences: {len(result.sentences)}")
    print()

    for i, sp in enumerate(result.sentences):
        status = "✓" if sp.num_parses == 1 else "⚠" if sp.is_ambiguous else "✗"
        count = f"{sp.num_parses} parse(s)"
        print(f"  {status} [{i+1}] \"{sp.sentence}\"  — {count}")

        if sp.failed:
            # Show which tokens couldn't be resolved
            for tok in sp.tokens:
                clean = tok.lower().rstrip(".,!?")
                lookup = result.lexicon.lookup(clean)
                if lookup:
                    canonical, cat = lookup
                    typ = result.lexicon.get_type(canonical)
                    print(f"       {tok:15} → {canonical}:{typ}")
                else:
                    from message.core.grammar import KEYWORD_INDEX, IGNORED
                    if clean in KEYWORD_INDEX:
                        print(f"       {tok:15} → {KEYWORD_INDEX[clean]}")
                    elif clean in IGNORED:
                        print(f"       {tok:15} → _")
                    else:
                        print(f"       {tok:15} → ???")

        for j, match in enumerate(sp.matches):
            rule_name = match["rule"].name
            output = match["output"]
            prefix = "    →" if j == 0 else "     "
            print(f"    {prefix} {output}  ({rule_name})")

        if args.verbose and sp.matches:
            for match in sp.matches:
                print(f"       bindings: ", end="")
                parts = []
                for var, (canon, typ) in match["bindings"].items():
                    parts.append(f"{var}={canon}:{typ}")
                print(", ".join(parts))

        print()

    # Summary
    derived = result.all_facts
    print(f"Derived {len(derived)} logical forms:")
    for f in derived:
        print(f"  {f}")

    # Verify against gold facts
    if gold_facts:
        print()
        print(f"Gold facts ({len(gold_facts)}):")
        matched = 0
        for gf in gold_facts:
            if gf in derived:
                print(f"  ✓ {gf}")
                matched += 1
            else:
                print(f"  ✗ {gf}  (not derived)")

        extra = [d for d in derived if d not in gold_facts]
        for e in extra:
            print(f"  ⚠ {e}  (extra — not in gold)")

        print(f"\n  {matched}/{len(gold_facts)} gold facts derived")


if __name__ == "__main__":
    main()
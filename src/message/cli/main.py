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
    """Show which tests have .logic files."""
    from message.core.coverage import scan_tests, coverage_status

    coverage_dir = _repo_root() / "coverage"
    if not coverage_dir.is_dir():
        print("✗ No coverage directory found.")
        sys.exit(1)

    tests = scan_tests(str(coverage_dir))
    status = coverage_status(tests, str(coverage_dir))

    covered = sum(1 for s in status if s.has_logic)
    total = len(status)

    current_group = None
    for s in status:
        if s.group != current_group:
            current_group = s.group
            print(f"\n  {current_group}/")
        mark = "✓" if s.has_logic else "·"
        print(f"    {mark} {s.name}")

    print(f"\n  {covered}/{total} covered")


if __name__ == "__main__":
    main()
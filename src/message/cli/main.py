"""
Message CLI — semantic representation DSL toolkit.
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="message",
        description="Semantic representation DSL toolkit",
    )

    subparsers = parser.add_subparsers(dest="command")

    # dsl
    dsl_p = subparsers.add_parser("dsl", help="DSL version management")
    dsl_sub = dsl_p.add_subparsers(dest="dsl_command")

    dsl_list = dsl_sub.add_parser("list", help="List DSL versions")
    dsl_list.set_defaults(func=cmd_dsl_list)

    dsl_show = dsl_sub.add_parser("show", help="Show DSL spec")
    dsl_show.add_argument("version", help="DSL version (e.g. horn1)")
    dsl_show.set_defaults(func=cmd_dsl_show)

    dsl_check = dsl_sub.add_parser("check", help="Validate a .logic file")
    dsl_check.add_argument("version", help="DSL version (e.g. horn1)")
    dsl_check.add_argument("file", help="Path to .logic file")
    dsl_check.set_defaults(func=cmd_dsl_check)

    # coverage
    cov_p = subparsers.add_parser("coverage", help="Coverage test management")
    cov_sub = cov_p.add_subparsers(dest="cov_command")

    cov_list = cov_sub.add_parser("list", help="List coverage tests")
    cov_list.set_defaults(func=cmd_coverage_list)

    cov_status = cov_sub.add_parser("status", help="Show coverage status per DSL version")
    cov_status.add_argument("version", help="DSL version (e.g. horn1)")
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


def cmd_dsl_list(args):
    from message.core.dsl import list_versions
    versions = list_versions()
    if not versions:
        print("No DSL versions found.")
        return
    for v in versions:
        print(f"  {v['name']:8} {v['description']}")


def cmd_dsl_show(args):
    from message.core.dsl import load_version
    spec = load_version(args.version)
    if not spec:
        print(f"✗ Unknown version: {args.version}")
        sys.exit(1)
    print(spec.raw)


def cmd_dsl_check(args):
    from message.core.checker import check_file

    # Verify the version exists
    dsl_path = _repo_root() / "dsl" / f"{args.version}.dsl"
    if not dsl_path.exists():
        print(f"✗ Unknown DSL version: {args.version}")
        sys.exit(1)

    # Verify the file matches the version
    if f".{args.version}." not in args.file:
        print(f"✗ File {args.file} doesn't match version {args.version}")
        sys.exit(1)

    errors = check_file(args.file, version=args.version)
    if not errors:
        print(f"✓ {args.file} is valid {args.version}")
    else:
        print(f"✗ {args.file} has {len(errors)} errors:")
        for e in errors:
            print(f"  line {e.line}: {e.message}")
        sys.exit(1)


def cmd_coverage_list(args):
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
    from message.core.coverage import scan_tests, coverage_status

    coverage_dir = _repo_root() / "coverage"
    if not coverage_dir.is_dir():
        print("✗ No coverage directory found.")
        sys.exit(1)

    tests = scan_tests(str(coverage_dir))
    status = coverage_status(tests, args.version, str(coverage_dir))

    covered = sum(1 for s in status if s.has_logic)
    total = len(status)

    current_group = None
    for s in status:
        if s.group != current_group:
            current_group = s.group
            print(f"\n  {current_group}/")
        mark = "✓" if s.has_logic else "·"
        print(f"    {mark} {s.name}")

    print(f"\n  {covered}/{total} covered by {args.version}")


if __name__ == "__main__":
    main()
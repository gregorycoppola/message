"""
Coverage test scanning and status.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CoverageTest:
    group: str
    name: str
    document: str
    query: str
    expected: str
    description: str


@dataclass
class CoverageStatus:
    group: str
    name: str
    has_logic: bool


def scan_tests(coverage_dir: str) -> list[CoverageTest]:
    root = Path(coverage_dir)
    tests = []

    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue

        group = group_dir.name

        for doc_file in sorted(group_dir.glob("*.document")):
            name = doc_file.stem
            doc_text = doc_file.read_text().strip()

            query_file = group_dir / f"{name}.query"
            query_text = query_file.read_text().strip() if query_file.exists() else ""

            expected_file = group_dir / f"{name}.expected"
            expected_text = expected_file.read_text().strip() if expected_file.exists() else ""

            desc_file = group_dir / f"{name}.description"
            desc_text = desc_file.read_text().strip() if desc_file.exists() else ""

            tests.append(CoverageTest(
                group=group,
                name=name,
                document=doc_text,
                query=query_text,
                expected=expected_text,
                description=desc_text,
            ))

    return tests


def coverage_status(tests: list[CoverageTest], version: str, coverage_dir: str) -> list[CoverageStatus]:
    root = Path(coverage_dir)
    statuses = []

    for test in tests:
        logic_file = root / test.group / f"{test.name}.{version}.logic"
        statuses.append(CoverageStatus(
            group=test.group,
            name=test.name,
            has_logic=logic_file.exists(),
        ))

    return statuses
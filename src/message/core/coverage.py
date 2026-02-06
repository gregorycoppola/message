"""
Coverage test scanning and validation.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CoverageTest:
    """A coverage test case."""
    group: str
    name: str
    path: Path
    
    # Content
    document: str
    question: str  # NL question
    expected: str
    description: str
    
    # New format files
    lexicon: str | None
    facts: str | None
    query: str | None  # formal query
    
    # Legacy
    logic: str | None  # old combined format
    
    @property
    def has_new_format(self) -> bool:
        return self.lexicon is not None and self.facts is not None and self.query is not None
    
    @property
    def has_legacy_format(self) -> bool:
        return self.logic is not None
    
    @property
    def is_complete(self) -> bool:
        """Has all required files in new format."""
        return (
            self.document and
            self.question and
            self.expected and
            self.lexicon is not None and
            self.facts is not None and
            self.query is not None
        )


@dataclass 
class CoverageStatus:
    group: str
    name: str
    format: str  # 'new', 'legacy', 'incomplete'
    missing: list[str]


def scan_tests(coverage_dir: str) -> list[CoverageTest]:
    """Scan coverage directory for test cases."""
    root = Path(coverage_dir)
    tests = []
    
    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue
        
        group = group_dir.name
        
        # Find all unique test names by looking at .document files
        for doc_file in sorted(group_dir.glob("*.document")):
            name = doc_file.stem
            base = group_dir / name
            
            def read_if_exists(suffix: str) -> str | None:
                f = base.with_suffix(suffix)
                return f.read_text().strip() if f.exists() else None
            
            # Required files
            document = read_if_exists(".document") or ""
            expected = read_if_exists(".expected") or ""
            description = read_if_exists(".description") or ""
            
            # New format
            lexicon = read_if_exists(".lexicon")
            facts = read_if_exists(".facts")
            query = read_if_exists(".query")
            question = read_if_exists(".question")
            
            # Legacy format
            logic = read_if_exists(".logic")
            
            # Handle transition: if .question doesn't exist but .query does and looks like NL
            if question is None and query is not None and not query.startswith("?"):
                # Old format: .query was the NL question
                question = query
                query = None
            
            tests.append(CoverageTest(
                group=group,
                name=name,
                path=base,
                document=document,
                question=question or "",
                expected=expected,
                description=description,
                lexicon=lexicon,
                facts=facts,
                query=query,
                logic=logic,
            ))
    
    return tests


def coverage_status(tests: list[CoverageTest]) -> list[CoverageStatus]:
    """Check format status for each test."""
    statuses = []
    
    for test in tests:
        missing = []
        
        if test.has_new_format:
            fmt = "new"
            if not test.question:
                missing.append(".question")
        elif test.has_legacy_format:
            fmt = "legacy"
            missing = [".lexicon", ".facts", ".query"]
        else:
            fmt = "incomplete"
            if test.lexicon is None:
                missing.append(".lexicon")
            if test.facts is None:
                missing.append(".facts")
            if test.query is None:
                missing.append(".query")
            if not test.question:
                missing.append(".question")
        
        statuses.append(CoverageStatus(
            group=test.group,
            name=test.name,
            format=fmt,
            missing=missing,
        ))
    
    return statuses


def print_status_summary(statuses: list[CoverageStatus]):
    """Print a summary of test format status."""
    new_count = sum(1 for s in statuses if s.format == "new")
    legacy_count = sum(1 for s in statuses if s.format == "legacy")
    incomplete_count = sum(1 for s in statuses if s.format == "incomplete")
    
    print(f"Coverage Status: {len(statuses)} tests")
    print(f"  ✅ New format:  {new_count}")
    print(f"  📦 Legacy:      {legacy_count}")
    print(f"  ❌ Incomplete:  {incomplete_count}")
    
    if legacy_count > 0:
        print(f"\nLegacy tests (need conversion):")
        for s in statuses:
            if s.format == "legacy":
                print(f"  {s.group}/{s.name}")
    
    if incomplete_count > 0:
        print(f"\nIncomplete tests:")
        for s in statuses:
            if s.format == "incomplete":
                print(f"  {s.group}/{s.name} — missing: {', '.join(s.missing)}")
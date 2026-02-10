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


@dataclass
class ParseResult:
    """Result of running the parser on a single test case."""
    group: str
    name: str
    total_sentences: int
    parsed_sentences: int  # at least one parse
    ambiguous_sentences: int  # more than one parse
    failed_sentences: int  # zero parses
    total_gold_facts: int
    derived_gold_facts: int
    extra_facts: int  # derived but not in gold
    skipped: bool = False  # missing lexicon or facts
    
    @property
    def fully_passing(self) -> bool:
        return (not self.skipped and 
                self.derived_gold_facts == self.total_gold_facts and
                self.extra_facts == 0)
    
    @property 
    def label(self) -> str:
        return f"{self.group}/{self.name}"


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


def run_parse_coverage(tests: list[CoverageTest]) -> list[ParseResult]:
    """Run the parser on all tests and collect results."""
    from message.core.lexicon import parse_lexicon
    from message.core.parser import parse_document
    
    results = []
    
    for test in tests:
        if not test.lexicon or not test.facts or not test.document:
            results.append(ParseResult(
                group=test.group,
                name=test.name,
                total_sentences=0,
                parsed_sentences=0,
                ambiguous_sentences=0,
                failed_sentences=0,
                total_gold_facts=0,
                derived_gold_facts=0,
                extra_facts=0,
                skipped=True,
            ))
            continue
        
        lexicon = parse_lexicon(test.lexicon)
        doc_parse = parse_document(test.document, lexicon)
        
        gold_facts = [line.strip() for line in test.facts.split("\n") 
                      if line.strip() and not line.strip().startswith("#")]
        
        derived = doc_parse.all_facts
        
        derived_gold = sum(1 for gf in gold_facts if gf in derived)
        extra = sum(1 for d in derived if d not in gold_facts)
        
        results.append(ParseResult(
            group=test.group,
            name=test.name,
            total_sentences=len(doc_parse.sentences),
            parsed_sentences=sum(1 for s in doc_parse.sentences if s.num_parses >= 1),
            ambiguous_sentences=sum(1 for s in doc_parse.sentences if s.is_ambiguous),
            failed_sentences=sum(1 for s in doc_parse.sentences if s.failed),
            total_gold_facts=len(gold_facts),
            derived_gold_facts=derived_gold,
            extra_facts=extra,
        ))
    
    return results


def print_parse_coverage(results: list[ParseResult]):
    """Print parse coverage summary."""
    for r in results:
        if r.skipped:
            print(f"  ⏭  {r.label:40} skipped (missing lexicon/facts)")
            continue
        
        if r.fully_passing:
            icon = "✅"
        elif r.derived_gold_facts > 0:
            icon = "🔶"
        else:
            icon = "❌"
        
        facts_str = f"{r.derived_gold_facts}/{r.total_gold_facts} facts"
        sents_str = f"{r.parsed_sentences}/{r.total_sentences} sents"
        
        extra = ""
        if r.ambiguous_sentences > 0:
            extra += f"  ⚠ {r.ambiguous_sentences} ambiguous"
        if r.extra_facts > 0:
            extra += f"  +{r.extra_facts} extra"
        
        print(f"  {icon} {r.label:40} {facts_str:14} {sents_str}{extra}")
    
    # Totals
    active = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]
    passing = [r for r in active if r.fully_passing]
    
    total_facts = sum(r.total_gold_facts for r in active)
    derived_facts = sum(r.derived_gold_facts for r in active)
    total_sents = sum(r.total_sentences for r in active)
    parsed_sents = sum(r.parsed_sentences for r in active)
    ambiguous_sents = sum(r.ambiguous_sentences for r in active)
    
    print()
    print("=" * 60)
    print(f"  Tests:     {len(passing)}/{len(active)} fully passing" + 
          (f"  ({len(skipped)} skipped)" if skipped else ""))
    print(f"  Facts:     {derived_facts}/{total_facts} derived")
    print(f"  Sentences: {parsed_sents}/{total_sents} parsed" +
          (f"  ({ambiguous_sents} ambiguous)" if ambiguous_sents else ""))


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
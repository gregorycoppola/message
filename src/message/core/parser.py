"""
Sentence parser — tokenizes documents and matches against grammar.

Takes a .document text and a Lexicon, produces parses for each sentence.
"""

import re
from dataclasses import dataclass, field
from message.core.lexicon import Lexicon, parse_lexicon, parse_lexicon_file
from message.core.grammar import match_sentence


@dataclass
class SentenceParse:
    """Result of parsing a single sentence."""
    sentence: str
    tokens: list[str]
    matches: list[dict]  # from grammar.match_sentence

    @property
    def num_parses(self) -> int:
        return len(self.matches)

    @property
    def is_ambiguous(self) -> bool:
        return len(self.matches) > 1

    @property
    def failed(self) -> bool:
        return len(self.matches) == 0

    @property
    def best(self) -> dict | None:
        return self.matches[0] if self.matches else None


@dataclass
class DocumentParse:
    """Result of parsing a full document."""
    text: str
    lexicon: Lexicon
    sentences: list[SentenceParse]

    @property
    def all_facts(self) -> list[str]:
        """Collect all derived facts/rules from best parses."""
        results = []
        for sp in self.sentences:
            if sp.best:
                results.append(sp.best["output"])
        return results

    @property
    def num_failed(self) -> int:
        return sum(1 for s in self.sentences if s.failed)

    @property
    def num_ambiguous(self) -> int:
        return sum(1 for s in self.sentences if s.is_ambiguous)


def tokenize(text: str) -> list[str]:
    """Simple tokenizer — split on whitespace, keep punctuation attached."""
    return text.split()


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on period/question mark/exclamation."""
    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def parse_document(text: str, lexicon: Lexicon) -> DocumentParse:
    """Parse a document against a lexicon using the grammar."""
    sentences = split_sentences(text)
    parsed = []

    for sent in sentences:
        tokens = tokenize(sent)
        matches = match_sentence(tokens, lexicon)
        parsed.append(SentenceParse(
            sentence=sent,
            tokens=tokens,
            matches=matches,
        ))

    return DocumentParse(text=text, lexicon=lexicon, sentences=parsed)


def parse_document_files(doc_path: str, lexicon_path: str) -> DocumentParse:
    """Parse a .document file against a .lexicon file."""
    with open(doc_path) as f:
        doc_text = f.read().strip()
    lexicon = parse_lexicon_file(lexicon_path)
    return parse_document(doc_text, lexicon)
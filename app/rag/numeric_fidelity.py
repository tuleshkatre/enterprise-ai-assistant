import re
from collections.abc import Iterable, Iterator
from typing import Any

NEGATIVE_QUANTITY_PATTERN = re.compile(
    r"(?<![\w.])-(?P<quantity>\d+(?:\.\d+)?)"
    r"(?P<suffix>(?:\s+[A-Za-z]+){1,2})"
)


def correct_unsupported_negative_quantities(
    answer: str, documents: Iterable[dict[str, Any]]
) -> str:
    """Remove a generated minus only when the source supports the positive phrase."""
    source = "\n".join(
        str(document.get("content", "")) for document in documents
    ).casefold()

    def replace(match: re.Match[str]) -> str:
        quantity = match.group("quantity")
        suffix_words = match.group("suffix").split()
        for word_count in range(len(suffix_words), 0, -1):
            grounded_suffix = " ".join(suffix_words[:word_count])
            positive_phrase = f"{quantity} {grounded_suffix}"
            negative_phrase = f"-{positive_phrase}"
            if (
                positive_phrase.casefold() in source
                and negative_phrase.casefold() not in source
            ):
                remainder = suffix_words[word_count:]
                return " ".join([positive_phrase, *remainder])
        return match.group(0)

    return NEGATIVE_QUANTITY_PATTERN.sub(replace, answer)


def stream_corrected_numeric_chunks(
    chunks: Iterable[str],
    documents: Iterable[dict[str, Any]],
    holdback: int = 64,
) -> Iterator[str]:
    """Correct split numeric phrases while retaining progressive streaming."""
    source_documents = list(documents)
    pending = ""

    for chunk in chunks:
        pending += chunk
        pending = correct_unsupported_negative_quantities(pending, source_documents)
        if len(pending) > holdback:
            emit_until = len(pending) - holdback
            yield pending[:emit_until]
            pending = pending[emit_until:]

    if pending:
        yield correct_unsupported_negative_quantities(pending, source_documents)

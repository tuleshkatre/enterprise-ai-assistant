from app.rag.numeric_fidelity import (
    correct_unsupported_negative_quantities,
    stream_corrected_numeric_chunks,
)


def test_removes_generated_minus_when_positive_quantity_is_in_source():
    documents = [
        {
            "content": (
                "Incident reports must be escalated within 1 hour. "
                "Returns are processed within 5 business days."
            )
        }
    ]

    assert (
        correct_unsupported_negative_quantities(
            "Escalate within -1 hour and process returns within -5 business days.",
            documents,
        )
        == "Escalate within 1 hour and process returns within 5 business days."
    )


def test_preserves_negative_quantity_when_source_contains_it():
    documents = [{"content": "Storage must remain at -5 degrees Celsius."}]

    assert (
        correct_unsupported_negative_quantities(
            "Storage must remain at -5 degrees Celsius.", documents
        )
        == "Storage must remain at -5 degrees Celsius."
    )


def test_does_not_change_unsupported_number_without_matching_source_phrase():
    documents = [{"content": "Returns are processed promptly."}]

    assert (
        correct_unsupported_negative_quantities(
            "Returns take -5 business days.", documents
        )
        == "Returns take -5 business days."
    )


def test_stream_correction_handles_numeric_phrase_split_across_chunks():
    documents = [{"content": "Returns are processed within 5 business days."}]

    chunks = list(
        stream_corrected_numeric_chunks(
            ["Returns are processed within -", "5", " business", " days."],
            documents,
            holdback=16,
        )
    )

    assert "".join(chunks) == "Returns are processed within 5 business days."


def test_stream_correction_preserves_grounded_negative_across_chunks():
    documents = [{"content": "Storage must remain at -5 degrees Celsius."}]

    chunks = list(
        stream_corrected_numeric_chunks(
            ["Storage must remain at -", "5 degrees", " Celsius."], documents
        )
    )

    assert "".join(chunks) == "Storage must remain at -5 degrees Celsius."

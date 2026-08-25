from app.rag.retrieval import (
    _explicit_source_match,
    _lexical_tsquery,
    _policy_statement_pattern,
)


def test_policy_statement_page_query_builds_exact_label_pattern():
    assert (
        _policy_statement_pattern("What is the policy statement on page 36?")
        == "%Policy Statement 36:%"
    )


def test_unrelated_queries_do_not_enable_exact_page_matching():
    assert _policy_statement_pattern("Who approves leave requests?") is None


def test_lexical_query_keeps_domain_and_content_terms_only():
    value = _lexical_tsquery(
        "According to the SaaS policy, what must deployments pass?"
    )

    assert set(value.split(" | ")) == {
        "according",
        "deployments",
        "pass",
        "policy",
        "saas",
    }


def test_explicit_domain_matches_source_filename_only_when_requested():
    filename = "uploads/1_uuid_saas_policy.pdf"

    assert _explicit_source_match("According to SaaS policy", filename) is True
    assert _explicit_source_match("What is the deployment policy?", filename) is False

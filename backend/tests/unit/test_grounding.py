"""Step 8 (ADR-0009 D2): number words and operator-controlled recipient aliases in the grounding checks.
Pure functions: no database, no network."""
import json

import pytest

from budget_kernel.proposals import validate
from budget_kernel.proposals.schema import Proposal
from budget_kernel.proposals.validate import amounts_in, grounded_amounts, name_in_text, semantic_issues


# ---------------------------------------------------------------- number words

@pytest.mark.parametrize("text,expected", [
    ("pay forty dollars", [4000]),
    ("Pay Forty Dollars to aws", [4000]),
    ("one hundred and twenty dollars", [12000]),
    ("one hundred twenty dollars", [12000]),
    ("twenty-five dollars", [2500]),
    ("a hundred dollars", [10000]),
    ("a thousand dollars", [100000]),
    ("two thousand five hundred dollars", [250000]),
    ("nine hundred ninety-nine thousand nine hundred ninety-nine dollars", [99_999_900]),
    ("fifty cents", [50]),
    ("seventeen usd", [1700]),
    ("five bucks", [500]),
])
def test_number_words_with_a_currency_word_are_amounts(text, expected):
    assert amounts_in(text) == expected


@pytest.mark.parametrize("text", [
    "pay forty for aws",                      # no currency word: not an amount (a safe miss, stays unresolved)
    "pay one of the invoices",
    "the one and only cloud",
    "hundred hundred dollars",                # malformed
    "forty fifty dollars",
    "twenty twenty dollars",
    "one thousand thousand dollars",
    "a dollars",
    "and dollars",
])
def test_number_words_without_a_currency_word_or_malformed_are_not_amounts(text):
    assert amounts_in(text) == []


def test_digits_still_work_and_mix_with_words():
    assert amounts_in("Pay $1,200.50 and forty dollars") == [120050, 4000]
    assert amounts_in("version 2.0.1 costs 3.5") == [350]


def test_dollars_and_cents_in_words_ground_their_sum():
    g = grounded_amounts("forty dollars and fifty cents")
    assert {4000, 50, 4050} <= g


def test_a_percentage_in_words_context_still_applies_to_a_word_amount():
    assert 4400 in grounded_amounts("forty dollars plus a 10% fee")


def test_an_unrelated_amount_is_still_ungrounded():
    assert 4100 not in grounded_amounts("pay forty dollars")


# ---------------------------------------------------------------- aliases

@pytest.fixture()
def alias_file(tmp_path, monkeypatch):
    def make(content):
        p = tmp_path / "aliases.json"
        p.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        monkeypatch.setenv("BK_RECIPIENT_ALIASES", str(p))
        return p
    return make


def test_an_alias_counts_as_the_recipient_appearing_in_the_text(alias_file):
    alias_file({"aws": ["amazon web services"], "acme": ["acme corp", "c++ cloud"]})
    assert name_in_text("aws", "Pay Amazon Web Services $5")
    assert name_in_text("aws", "pay AWS $5")                          # the canonical name still works
    assert name_in_text("acme", "pay the C++ Cloud bill")             # regex characters in an alias are literal
    assert not name_in_text("aws", "Pay Amazon $5")                   # a fragment of the alias is not the alias
    assert not name_in_text("aws", "pay amazon web servicesX")        # whole words only
    assert not name_in_text("acme", "pay amazon web services")        # an alias belongs to its own recipient only


def test_aliases_never_widen_the_existing_word_boundary_rules(alias_file):
    alias_file({"aws": ["amazon web services"], "ads": ["advertising"]})
    assert not name_in_text("aws", "Pay lawsuits $5")
    assert not name_in_text("ads", "Pay roads $5")
    assert not name_in_text(None, "x")


@pytest.mark.parametrize("content", ["{not json", "[]", '{"aws": "amazon web services"}', '{"aws": [1, 2]}', ""])
def test_a_broken_alias_file_means_no_aliases_and_never_an_error(alias_file, content):
    alias_file(content)
    assert name_in_text("aws", "pay aws $5")
    assert not name_in_text("aws", "pay amazon web services $5")


def test_a_missing_alias_file_means_no_aliases(monkeypatch, tmp_path):
    monkeypatch.setenv("BK_RECIPIENT_ALIASES", str(tmp_path / "nope.json"))
    assert name_in_text("aws", "pay aws $5") and not name_in_text("aws", "pay amazon web services $5")


def test_the_shipped_alias_file_is_valid_and_lowercase_whole_phrases():
    data = json.loads(validate.DEFAULT_ALIASES_PATH.read_text(encoding="utf-8"))
    assert data["aws"] and all(isinstance(a, str) and a == a.lower() and a.strip() == a for v in data.values() for a in v)


def test_an_edited_alias_file_is_picked_up_without_a_restart(alias_file):
    p = alias_file({"aws": ["amazon web services"]})
    assert name_in_text("aws", "pay amazon web services")
    p.write_text(json.dumps({"aws": ["some other name"]}), encoding="utf-8")
    import os
    os.utime(p, ns=(10**18, 10**18 + 5))              # make the mtime differ even on coarse clocks
    assert not name_in_text("aws", "pay amazon web services") and name_in_text("aws", "pay some other name")


# ---------------------------------------------------------------- end to end through semantic_issues

def _p(amount, **over):
    base = {"schema_version": "1", "request_type": "payment", "amount_minor": amount, "currency": "USD",
            "recipient": "aws", "category": "cloud", "purpose": None, "evidence": [], "missing_fields": [],
            "ambiguities": [], "conflicts": [], "needs_human_review": False, "explanation": "ok"}
    base.update(over)
    return Proposal.model_validate(base)


def test_a_word_amount_and_an_alias_ground_a_complete_proposal(alias_file):
    alias_file({"aws": ["amazon web services"]})
    assert semantic_issues(_p(4000), "Pay Amazon Web Services forty dollars for cloud") == []


def test_a_wrong_amount_for_a_word_amount_is_still_flagged(alias_file):
    alias_file({"aws": ["amazon web services"]})
    assert "AMOUNT_UNGROUNDED" in semantic_issues(_p(5000), "Pay Amazon Web Services forty dollars for cloud")


def test_an_unlisted_alias_is_still_ungrounded(alias_file):
    alias_file({"aws": ["amazon web services"]})
    assert "RECIPIENT_UNGROUNDED" in semantic_issues(_p(4000), "Pay Amazon forty dollars for cloud")

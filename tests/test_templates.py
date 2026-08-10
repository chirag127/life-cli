import json

import pytest

from mail_agent.templates_loader import FIELDS, load_index, render

KEYS = [
    "statement-of-account",
    "consolidated-account-statement",
    "transaction-holding-statement",
    "capital-gains-statement",
]

VALUES = {
    "name": "Asha Rao",
    "PAN": "ABCDE1234F",
    "folio": "1234567/89",
    "registered_email": "asha@example.com",
    "address": "12 Main St\nBengaluru 560001",
}


def test_index_has_four_rta_keys():
    idx = load_index()
    assert set(idx) == set(KEYS)
    for entry in idx.values():
        assert entry["recipient_type"] == "RTA"
        assert set(entry) == {"file", "recipient_type", "subject"}


@pytest.mark.parametrize("key", KEYS)
def test_index_file_matches_key(key):
    assert load_index()[key]["file"] == f"{key}.txt"


@pytest.mark.parametrize("key", KEYS)
def test_render_fills_placeholders(key):
    out = render(key, **VALUES)
    assert out["recipient_type"] == "RTA"
    assert "{" not in out["body"] and "}" not in out["body"]
    assert "{" not in out["subject"] and "}" not in out["subject"]
    for v in VALUES.values():
        for line in v.splitlines():
            assert line in out["body"]


@pytest.mark.parametrize("key", KEYS)
def test_body_requests_both_copies(key):
    body = render(key, **VALUES)["body"].lower()
    assert "physical copy" in body
    assert "registered email" in body
    assert "address" in body


@pytest.mark.parametrize("key", KEYS)
def test_missing_field_becomes_blank(key):
    out = render(key)
    assert "{" not in out["body"] and "{" not in out["subject"]


def test_index_is_valid_json():
    from importlib.resources import files

    raw = files("mail_agent.templates").joinpath("index.json").read_text(encoding="utf-8")
    assert json.loads(raw)

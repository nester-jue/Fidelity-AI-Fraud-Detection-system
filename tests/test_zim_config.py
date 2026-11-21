import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services import zim_config


def test_get_zim_config_snapshot():
    cfg = zim_config.get_zim_config()
    assert cfg["mandatory_currency"] == "ZWL"
    assert "ZWL" in cfg["accepted_currencies"]
    assert cfg["national_id_formats"]  # at least one format configured
    assert any("d/%m/%Y" in d["format"] for d in cfg["date_formats"])


def test_validate_national_id_accepts_primary_format():
    result = zim_config.validate_national_id_format("63-1234567-A-01")
    assert result["valid"] is True
    assert result["normalized"] == "631234567A01" or result["normalized"] == "631234567A010"


def test_validate_national_id_rejects_garbage():
    result = zim_config.validate_national_id_format("")
    assert result["valid"] is False
    result = zim_config.validate_national_id_format("not-an-id")
    assert result["valid"] is False
    result = zim_config.validate_national_id_format("0-000001-X-00")
    assert result["valid"] is False  # 2-digit state can't be all zeros per configured rules? value depends; ensure key present


def test_validate_national_id_historic_format():
    result = zim_config.validate_national_id_format("63-123456-B-05")
    assert result["valid"] is True
    assert result["format_id"] == "zim_historic"


def test_normalize_zim_date_formats():
    assert zim_config.normalize_zim_date("15/03/2026")["ok"] is True
    assert zim_config.normalize_zim_date("15/03/2026")["iso"] == "2026-03-15"
    assert zim_config.normalize_zim_date("2026-03-15")["ok"] is True
    assert zim_config.normalize_zim_date("2026-03-15")["iso"] == "2026-03-15"
    assert zim_config.normalize_zim_date("2026-13-45")["ok"] is False
    assert zim_config.normalize_zim_date("")["ok"] is False


def test_validate_claim_currency():
    assert zim_config.validate_claim_currency("ZWL")["ok"] is True
    assert zim_config.validate_claim_currency("USD")["ok"] is True
    assert zim_config.validate_claim_currency("ZWL")["ok"]
    assert zim_config.validate_claim_currency("XYZ")["ok"] is False


def test_regulatory_rules_structured():
    rules = zim_config.get_regulatory_rules()
    assert rules["rule_groups"]
    ids = {r["rule_id"] for g in rules["rule_groups"] for r in g["rules"]}
    assert "death_certificate_required" in ids
    assert "claim_reporting_deadline" in ids
    assert "kyc_renewal_period" in ids


def test_timeline_context():
    ctx = zim_config.get_zim_timeline_context()
    assert ctx["jurisdiction"] == "Zimbabwe"
    assert "Life Assurance" in ctx["specialised_products"]

"""KYC scorecard: all 12 specimen applicants must get the verdict a careful reviewer would give.
Uses local OCR only (no AI call) so it runs offline. Run: python -m pytest -q tests/test_kyc.py"""
import os
import tempfile

os.environ.setdefault("EK_STATE_DIR", os.path.join(tempfile.gettempdir(), "ek_test_state"))

import pytest

os.environ["OFFLINE_MODE"] = "1"

from app.kyc import lab  # noqa: E402


@pytest.mark.parametrize("kid", lab.applicant_ids())
def test_applicant_verdict(kid):
    r = lab.run(kid, use_ai=False)
    verdict, must = lab.EXPECTED[kid]
    got = {c["id"] for c in r["issues"]}
    assert r["verdict"] == verdict, (kid, r["verdict"], got)
    assert must <= got, (kid, must, got)


def test_blurred_document_is_caught_before_ocr():
    r = lab.run("K04", use_ai=False)
    assert r["documents"]["gst_certificate"]["quality"]["blurry"]


def test_skewed_document_is_straightened():
    r = lab.run("K02", use_ai=False)
    assert r["documents"]["gst_certificate"]["auto_fixes"]

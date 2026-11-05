"""GSTIN and Udyam number format checks.

GSTIN = 2-digit state code + 10-char PAN + entity number + 'Z' + check character.
The check character uses the Luhn mod-36 scheme. In this synthetic data the 4th PAN
character is always 'X', which we accept (see data README).
"""
from __future__ import annotations

import itertools
import re

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}
UDYAM_STATE = {
    "AP": "Andhra Pradesh", "BR": "Bihar", "DL": "Delhi", "GJ": "Gujarat", "KA": "Karnataka", "KR": "Karnataka",
    "KL": "Kerala", "MH": "Maharashtra", "MP": "Madhya Pradesh", "PB": "Punjab", "RJ": "Rajasthan",
    "TN": "Tamil Nadu", "TS": "Telangana", "UP": "Uttar Pradesh", "WB": "West Bengal", "HR": "Haryana",
}

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")

# Characters OCR confuses. Used only to propose candidates, never to auto-accept.
_DIGIT_LOOKALIKE = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6", "T": "7"}
_LETTER_LOOKALIKE = {v: k for k, v in [("O", "0"), ("I", "1"), ("Z", "2"), ("S", "5"), ("B", "8"), ("G", "6")]}


def check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = CHARS.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return CHARS[(36 - total % 36) % 36]


def checksum_ok(gstin: str) -> bool:
    g = (gstin or "").upper()
    return len(g) == 15 and all(c in CHARS for c in g) and check_char(g[:14]) == g[14]


def normalise_ocr(raw: str) -> str:
    """Fix OCR confusions that the GSTIN layout makes unambiguous (digits vs letters by position)."""
    s = re.sub(r"[^0-9A-Za-z]", "", raw or "").upper()
    if len(s) != 15:
        return s
    out = list(s)
    digit_pos = [0, 1, 7, 8, 9, 10]
    letter_pos = [2, 3, 4, 5, 6, 11]
    for i in digit_pos:
        out[i] = _DIGIT_LOOKALIKE.get(out[i], out[i])
    for i in letter_pos:
        out[i] = _LETTER_LOOKALIKE.get(out[i], out[i])
    out[13] = "Z" if out[13] in "Z2" else out[13]
    return "".join(out)


def ocr_candidates(raw: str) -> list[str]:
    """All O/0 and I/1 variants of the free positions (13th and 15th) that pass the checksum."""
    s = normalise_ocr(raw)
    if len(s) != 15:
        return []
    swaps = {"0": "0O", "O": "0O", "1": "1I", "I": "1I"}
    options = [swaps.get(c, c) if i in (12, 14) else c for i, c in enumerate(s)]
    return [c for c in ("".join(p) for p in itertools.product(*options)) if checksum_ok(c)]


def validate(gstin: str) -> dict:
    g = (gstin or "").strip().upper()
    problems = []
    if len(g) != 15:
        problems.append(f"GSTIN must have 15 characters, this has {len(g)}")
    elif not GSTIN_RE.match(g):
        problems.append("GSTIN does not follow the standard pattern")
    elif not checksum_ok(g):
        problems.append("Check character is wrong: the number has a typo or was altered")
    state = STATE_CODES.get(g[:2]) if len(g) >= 2 else None
    if len(g) >= 2 and not state:
        problems.append("Unknown state code")
    return {"gstin": g, "valid": not problems, "state": state, "pan": g[2:12] if len(g) >= 12 else None, "problems": problems}


def validate_udyam(number: str) -> dict:
    n = (number or "").strip().upper()
    m = UDYAM_RE.match(n)
    if not m:
        return {"udyam": n, "valid": False, "state": None, "problems": ["Udyam number should look like UDYAM-XX-00-1234567"]}
    return {"udyam": n, "valid": True, "state": UDYAM_STATE.get(m.group(1)), "problems": []}


def mask(value: str | None, keep_start: int = 2, keep_end: int = 3) -> str:
    """Mask identifiers for UI and logs: 27PZ********1ZH style."""
    if not value:
        return ""
    v = str(value)
    if len(v) <= keep_start + keep_end:
        return "•" * len(v)
    return v[:keep_start] + "•" * (len(v) - keep_start - keep_end) + v[-keep_end:]

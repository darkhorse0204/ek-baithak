"""UI and advisor strings in 10 languages. English is the master; the others are generated once
by scripts/gen_i18n.py (Gemini), reviewed, and stored in web/i18n.json so runtime needs no model."""
from __future__ import annotations

import json
from functools import lru_cache

from .config import ROOT

LANGS = {
    "en": {"name": "English", "native": "English", "speech": "en-IN"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "speech": "hi-IN"},
    "mr": {"name": "Marathi", "native": "मराठी", "speech": "mr-IN"},
    "ta": {"name": "Tamil", "native": "தமிழ்", "speech": "ta-IN"},
    "te": {"name": "Telugu", "native": "తెలుగు", "speech": "te-IN"},
    "bn": {"name": "Bengali", "native": "বাংলা", "speech": "bn-IN"},
    "gu": {"name": "Gujarati", "native": "ગુજરાતી", "speech": "gu-IN"},
    "kn": {"name": "Kannada", "native": "ಕನ್ನಡ", "speech": "kn-IN"},
    "ml": {"name": "Malayalam", "native": "മലയാളം", "speech": "ml-IN"},
    "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ", "speech": "pa-IN"},
}

EN = {
    # Advisor
    "greeting": "Namaste! I'm your Accel Business advisor. In a few minutes I'll suggest the right internet, mobile and digital tools for your business, with one clear monthly price. What kind of business do you run? You can type, tap, or send a voice note.",
    "ask_business_type": "What kind of business do you run?",
    "ask_city": "Which city is your business in?",
    "ask_employees": "How many people work in your business, including you?",
    "ask_sites": "How many shops, branches or locations do you have?",
    "ask_gstin": "Do you have a GSTIN? Type it and I'll fill in your details from the GST registry, so you don't have to.",
    "ask_needs": "Businesses like your {business} usually need these. Tick what matters to you and tap Confirm.",
    "your_business": "business",
    "qr_type_gstin": "I'll type my GSTIN",
    "qr_no_gstin": "I don't have GST",
    "registry_found": "Found you in the GST registry: {name}, {city} (registered since {since}, status: {status}). Business type: {btype}. No documents needed for this part.",
    "gst_inactive": "Your GST registration shows as {status}. You can still go live today with products that don't need GST.",
    "gstin_bad": "That GSTIN doesn't look right ({problem}). Please check and type it again, or tap 'I don't have GST'.",
    "city_unlisted": "We're expanding to your city soon; I'll use tier-2 availability for now.",
    "handoff": "Sure. A local Accel partner will call you within 30 minutes, with everything you told me, so you won't have to repeat yourself.",
    "reco_head": "Your plan: ₹{monthly} a month (about ₹{per_day} a day).",
    "go_checkout": "Great choice! Tap Continue to verify your business. It takes about 2 minutes.",
    "bt_kirana": "Kirana / shop", "bt_clinic": "Clinic", "bt_ca": "CA / office", "bt_salon": "Salon",
    "bt_restaurant": "Restaurant chain", "bt_factory": "Factory", "bt_coaching": "Coaching centre", "bt_pharmacy": "Pharmacy",
    # App UI
    "ui_tagline": "Your business, live in one sitting",
    "ui_choose_lang": "Choose your language",
    "ui_start": "Start",
    "ui_type_message": "Type, or hold the mic to speak",
    "ui_listening": "Listening… release to send",
    "ui_confirm": "Confirm",
    "ui_see_plan": "See my plan",
    "ui_your_plan": "Your plan",
    "ui_per_month": "/month",
    "ui_per_day": "That's about ₹{n} a day",
    "ui_setup": "One-time setup",
    "ui_contract": "Contract",
    "ui_months": "months",
    "ui_term_12": "12 months",
    "ui_term_24": "24 months · lower price",
    "ui_addons": "Add-ons you can switch on",
    "ui_not_offered": "Not offered right now, and why",
    "ui_live_today": "Live today",
    "ui_installed_in": "Installed in about {n} days",
    "ui_continue": "Continue",
    "ui_back": "Back",
    "ui_vs_today": "You pay about ₹{n} today across vendors",
    "ui_consent_title": "Before we verify your business",
    "ui_consent_intro": "We only collect what this step needs. You can see, download or delete your data anytime from 'My data'.",
    "ui_c_kyc": "Verify my business and signatory identity (required by telecom rules)",
    "ui_c_registry": "Fetch my GST and Udyam details from government registries and Entity Locker, instead of uploading",
    "ui_c_updates": "Send order updates on WhatsApp",
    "ui_c_partner": "Share my address and phone with the installation partner",
    "ui_c_marketing": "Tell me about new offers (optional)",
    "ui_required": "Required",
    "ui_optional": "Optional",
    "ui_retention": "Document images are deleted within 24 hours of verification. We keep only the verified details, as the law requires for telecom connections.",
    "ui_agree": "I agree, continue",
    "ui_kyc_title": "Verify your business",
    "ui_fetch_locker": "Fetch from Entity Locker",
    "ui_upload": "Upload photos",
    "ui_use_sample": "Try a sample applicant",
    "ui_checking": "Checking your documents…",
    "ui_all_good": "All verified",
    "ui_fix_needed": "Almost there: one thing to fix",
    "ui_restricted": "Approved for products that don't need GST",
    "ui_review": "A specialist will check this within 2 hours",
    "ui_sign_title": "Sign and pay",
    "ui_esign": "e-Sign with Aadhaar OTP",
    "ui_send_link": "Send e-sign link on WhatsApp",
    "ui_sim_users": "Each SIM user gets a 1-minute self-KYC link (telecom rules)",
    "ui_pay": "Pay ₹{n} by UPI",
    "ui_autopay": "AutoPay starts from month 2. You get a reminder before every debit.",
    "ui_track_title": "Your order",
    "ui_whatsapp_updates": "Updates come to WhatsApp automatically. No need to call.",
    "ui_next_step": "Next step",
    "ui_my_data": "My data",
    "ui_download": "Download my data",
    "ui_erase": "Delete my data",
    "ui_withdraw": "Withdraw",
    "ui_talk_human": "Talk to a person",
}


@lru_cache
def table() -> dict[str, dict[str, str]]:
    f = ROOT / "web" / "i18n.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    data["en"] = EN
    return data


def t(key: str, lang: str = "en", **fmt) -> str:
    s = table().get(lang, {}).get(key) or EN.get(key, key)
    try:
        return s.format(**fmt)
    except (KeyError, IndexError):
        return EN.get(key, key).format(**fmt)

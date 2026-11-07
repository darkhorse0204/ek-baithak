# Ek Baithak · business live in one sitting

**YTL Hackathon 2026 · Track A · Project Udyam Digital** (fictional operator: Accel Business)

**Demo video (2 min 41 s):** https://drive.google.com/file/d/1Ho5gl_mTiw0q22HQnWRdzY6kNB6TKGQd/view?usp=sharing  
**Team:** Ansh Jerath and Shivani Jogiya

An AI advisor that lets a small-business owner discover the right bundle, buy it and get activated **in one sitting**, on a phone, in **10 Indian languages**, by typing, tapping or sending a voice note. The AI listens and explains. Plain, tested code decides what can be sold, what it costs, and whether KYC passes.

| Result | Number |
|---|---|
| Advisor test scenarios (rules traps, budget, Hindi, Tamil) | **15/15**, with AI on *and* off |
| KYC specimen applicants with the right verdict | **12/12** |
| Unit tests | 29 passing |
| Bundles sold last quarter that broke a catalogue rule (our audit) | 56 of 368 (15%): the advisor cannot do this |
| Projected lead → activation (simulator, same 5,000 leads) | 7.4% → 15.9% (conservative 11.0%) |
| Projected cost per activation | ₹15,053 → ₹4,245 (conservative ₹5,729) |

## Run it

```bash
pip install -r requirements.txt
# put your key in .env (see .env.example); without it the app runs fully offline
python -m uvicorn app.main:app --port 8000      # or double-click run.bat
```
Open **http://localhost:8000**. On a laptop you get the owner's phone (left) next to the **control room** (right). On a phone, or at `http://localhost:8000/#owner`, you get the owner app only.

Start-up takes a few seconds (the specimen documents ship pre-read in `data/ocr_cache_seed.json`). Use `reset_demo.bat` to clear old chats before a demo.


## What's inside

| Requirement in the brief | Where |
|---|---|
| **Advisor**: asks about the business, recommends from the catalogue, explains in plain language | `app/advisor.py` (dialogue), `app/recommender.py` + `app/catalogue.py` (rules, pricing) |
| **Quote & checkout**: one monthly price, add-ons the owner can toggle | Quote screen: ₹/month, ₹/day, 12 vs 24 months, toggles, quantities, "not offered and why" |
| **Smart KYC**: upload, extraction, validation, mocked GSTIN/Udyam lookups, consent screen | `app/kyc/` (quality gate, local OCR, parser, verifier), `app/registry.py`, consent screen |
| **Tracker**: order status the owner checks instead of calling | `app/orders.py`: milestones from install times, proactive WhatsApp-style updates |
| Stretch: voice / WhatsApp front end | Voice notes (Gemini speech-to-text), `POST /webhook/whatsapp` (Cloud API format) |
| Stretch: back office for leads the advisor couldn't close | Control room → *Live journeys* (scored, with reasons) |
| Stretch: propensity score | `app/analytics.py`: logistic model on 5,000 leads, AUC 0.69, reasons per lead |
| Extra | Rescue queue for dropped leads, funnel simulator, bundle audit, DPDP privacy log, "My data" page |

### Design choices worth knowing
- **The AI talks, code decides.** The LLM extracts facts from the owner's words and writes explanations from structured reasons. Eligibility (city tier, size, active GSTIN, product dependencies), price and KYC verdicts are deterministic and unit-tested, so a judge can't talk the advisor into selling 1 Gbps fibre in a tier-2 city.
- **Registry first, documents last.** A GSTIN pre-fills name, address, constitution, Udyam number and (from the CRM) size. Entity Locker replaces GST and Udyam uploads.
- **Two readers before an accusation.** OCR runs locally (RapidOCR). Gemini is a second reader only when a hard check fails. In testing, Gemini misread a blurred GSTIN and called it "legible", so the code never trusts a single reader.
- **Built for flaky free tiers.** Gemini model chain → optional Groq → offline keyword rules plus 10-language templates. Set `OFFLINE_MODE=1` to demo with no internet.
- **Who may sign.** Proprietor in person, an LLP partner, or a company director; anyone else gets a one-tap e-sign authorisation link (DoT business-connection KYC). Each SIM user gets a self-KYC link.

### KYC verdicts on the specimen pack
| | Caught | Outcome |
|---|---|---|
| K01 | GSTIN **cancelled** in registry; Udyam number blank | Go live with non-GST products |
| K02 | Scan tilted 7°: straightened automatically | Approved |
| K04 | GST certificate too blurry (sharpness 1 vs ~1,000) | Fix in app / Entity Locker |
| K05 | No Udyam upload (fetched from registry); LLP signatory needs partner authorisation | Fix in app |
| K06 | GSTIN altered: check digit fails, registry has `…5189…` not `…8189…`; AI second reader agrees | Compliance review |
| K07 | Legal name "Shri Physio Clinic" ≠ registry "Neelgiri Physio Clinic" | Compliance review |
| K10 | Signatory isn't the person who applied (and LLP authority) | Fix in app |
| K11 | Electricity bill 257 days old (limit 90); company needs board resolution | Fix in app |
| K03, K08, K09, K12 | All checks pass | Approved |

## Tests
```bash
python -m pytest -q                       # 29 tests: rules, GSTIN, pricing, privacy, 12 KYC verdicts
python scripts/scenarios.py --offline     # 15 advisor scenarios, rules-only
python scripts/scenarios.py               # same with Gemini (slower on the free tier)
python scripts/ui_tour.py en              # drives the real UI in Chrome, saves screenshots
```

## Repository map
```
app/            FastAPI app: advisor, recommender, catalogue rules, registry mocks, KYC, orders, privacy, analytics
web/            Phone app + control room (vanilla JS, no build step) and translations (web/i18n.json)
data/           The synthetic dataset from the case pack
tests/          pytest suite
scripts/        scenario suite, UI tour, translation generator, deck builders
docs/           Architecture diagram, privacy note (PDF), demo script
deck/           Business case (PPTX + PDF), charts, screenshots
```

## Mocked vs real
Mocked: GST/Udyam/Entity Locker APIs (backed by the case CSVs), fibre feasibility (by pincode hash), Aadhaar e-Sign OTP, UPI payment, WhatsApp sending (the webhook returns the payload it would send). Real: the advisor, rules, pricing, OCR, KYC checks, AI calls, model, simulator, consent ledger and audit log.

All data is synthetic. Production would use a paid, no-training AI tier hosted in India (see `docs/Privacy_Security_Note.pdf`).

# Ek Baithak: how to run it, record the demo, and submit

This guide is in 5 parts. Follow them in order.

1. [Run the project](#1-run-the-project)
2. [Get ready to record](#2-get-ready-to-record)
3. [The demo script (3 minutes)](#3-the-demo-script-3-minutes)
4. [Edit and upload the video to Google Drive](#4-edit-and-upload-the-video-to-google-drive)
5. [Put the code online and submit](#5-put-the-code-online-and-submit)

---

## 1. Run the project

### First time only (about 10 minutes)
1. **Check Python.** Open *Command Prompt* and type `python --version`. You need 3.10 or newer.
   If you get an error, install Python from python.org and tick **"Add Python to PATH"** during install.
2. **Install the libraries.** In Command Prompt:
   ```
   cd C:\Users\91738\Downloads\AIRTEL_SYNC_HACKATHON\ek-baithak
   pip install -r requirements.txt
   ```
   This downloads about 500 MB, so use good internet.
3. **Check your AI key.** The file `ek-baithak\.env` already has your Gemini key. Nothing to do.
   (On another computer: copy `.env.example` to `.env` and paste the key after `GEMINI_API_KEY=`.)

### Every time
1. Double-click **`run.bat`** inside the `ek-baithak` folder.
   A black window opens (this is the server; keep it open) and Chrome opens **http://localhost:8000**.
2. Wait about 10 seconds, then refresh the page if it's blank.
3. To stop: click the black window and press **Ctrl + C**, then close it.

### What you will see
- **Left:** the owner's phone. This is the app a shop owner uses.
- **Right:** the *Control room*. This is what Accel's sales, partner and compliance teams see.
- To see only the phone app (for example on a real phone on the same Wi-Fi): http://localhost:8000/#owner

### If something goes wrong
| Problem | Fix |
|---|---|
| `python` is not recognised | Reinstall Python and tick "Add Python to PATH". |
| "Address already in use" / port 8000 busy | Another copy is running. Close the other black window, or restart the computer. |
| The AI replies slowly (more than 10 s) | Free Gemini models get busy. Open `.env`, change `OFFLINE_MODE=0` to `OFFLINE_MODE=1`, save, and restart `run.bat`. Everything still works with simpler, rule-based replies. |
| The 🎤 mic button does nothing | Click the lock icon left of the address bar → allow **Microphone**. You can always type instead. |
| Old chats show up in the Control room | Stop the server, double-click **`reset_demo.bat`**, start again. |

---

## 2. Get ready to record

### 10 minutes before recording
- [ ] Double-click **`reset_demo.bat`** (clears old test chats), then **`run.bat`**.
- [ ] Do one practice run of the script below without recording. It warms up the AI and you'll know where to click.
- [ ] Then stop, run **`reset_demo.bat`** and **`run.bat`** again, so the Control room starts empty.
- [ ] In Chrome: close other tabs, press **F11** for full screen, zoom at **100%** (Ctrl + 0).
- [ ] Turn on Windows **Do not disturb** so no pop-ups appear.
- [ ] Keep this guide open on your phone or a second screen to read the lines.
- [ ] Copy the two typed lines below into Notepad so you can paste them quickly.

**Lines to paste during the demo:**
```
मेरी जयपुर में मिठाई की दुकान है, 4 लोग काम करते हैं। UPI के लिए अच्छा इंटरनेट और CCTV चाहिए।
Dental clinic in Kochi, 12 staff. We want 1 Gbps internet and SMS reminders for patients.
32TTNXB7384T1ZW
```

### Recording tool (pick one, both are free)
- **Easiest: Xbox Game Bar** (built into Windows). Press **Win + Alt + R** to start and stop recording the Chrome window. Videos are saved in *Videos → Captures*.
  To record your voice: press **Win + G**, then click the mic icon so it's on.
- **More control: OBS Studio** (obsproject.com). Add *Display Capture* and your microphone, set output to 1920×1080, 30 fps, MP4.

**Tip:** recording the screen and your voice separately is fine. You can add the voice later in Clipchamp (part 4).

---

## 3. The demo script (3 minutes)

We tested this exact path. The AI waits add up to about 30 seconds in total; cut them out when editing.
**Bold** = what you click or type. *Italic* = what you say.

### Scene 1 · The problem (0:00–0:15)
**Do:** Show the full screen. In the Control room, click the **Funnel & simulator** tab.
*Say:* "Accel Business loses 93 out of every 100 small businesses that show interest. Getting connected takes 17 days and three 'where is my order?' calls. Ek Baithak fixes this. A shop owner can choose, buy and switch on their services in one sitting, on their phone, in their own language."

### Scene 2 · A shop owner who speaks Hindi (0:15–0:45)
**Do:**
1. On the phone, click **हिन्दी**, then **शुरू करें →**.
2. Paste the Hindi line and press **Enter**.
3. When it asks about GST, tap **मेरे पास GST नहीं है** ("I don't have GST").
4. A list of needs appears with some already ticked. Tap the red **कन्फर्म करें ✓** (Confirm) button.
5. The plan appears (about ₹2,295 a month).

*Say:* "A sweet-shop owner in Jaipur types in Hindi. The AI understands, asks only what it needs, and gives a plan in Hindi, with the price per month and per day. No sales visit, no product codes. It works in 10 Indian languages, and the owner can also send a voice note."

### Scene 3 · The AI can't be talked into a wrong sale (0:45–1:15)
**Do:**
1. Press **F5** to start fresh. Click **English**, then **Start →**.
2. Paste the dental clinic line and press **Enter**.
3. When it asks how many locations, tap **1**.
4. When it asks about GSTIN, tap **I'll type my GSTIN**, paste **32TTNXB7384T1ZW**, press **Enter**.
5. It finds the clinic in the GST records. Tap **Confirm ✓** on the needs list.
6. Point at the line saying 1 Gbps isn't available in Kochi, so it chose 300 Mbps.

*Say:* "Now a dental clinic in Kochi asks for 1 Gbps internet. That product is only sold in big cities. The AI can't be talked into selling it, because simple rules decide what can be sold, not the AI. It explains why and offers the right option. The GST number fills in the business details from government records, so there are no forms to fill."

### Scene 4 · One clear price (1:15–1:30)
**Do:**
1. Tap **See my plan →**.
2. Tap **24 months · lower price** (₹8,276 drops to about ₹7,189).
3. Scroll down a little and switch one add-on on or off.

*Say:* "One clear monthly price, with the price per day. A longer contract costs less. The owner can switch extras on or off. Items marked 'today' start working right away."

### Scene 5 · Consent (1:30–1:38)
**Do:** Tap **Continue**. On the consent screen, tap **I agree, continue**.
*Say:* "Before checking any documents, we ask for consent in simple words, one purpose at a time. Marketing is off unless they turn it on."

### Scene 6 · Smart KYC (1:38–2:05)
**Do:**
1. Under *Try a sample applicant*, tap **K06**. A red result appears: a specialist will check it.
2. Tap **↺ Try other documents**, then tap **K02**. A green **All verified** appears.

*Say:* "Owners can fetch documents from Entity Locker, the government's document wallet, or take four photos. Here we use the sample files from the case. This first one has an edited GST number. The check digit fails, and a second AI reading confirms the document is wrong, so a person checks it. This one was a tilted scan: we straighten it, read it on our own server, and approve it automatically."

### Scene 7 · Sign, pay and go live (2:05–2:25)
**Do:**
1. Tap **Continue**, then **🔐 e-Sign with Aadhaar OTP**. The OTP fills in by itself.
2. Tap the green **UPI · Pay** button. The tracker opens.
3. Tap **⏩ Next day (demo)** 6 times, until it shows **100% · Everything live**.

*Say:* "The form is already filled in. They sign with an Aadhaar OTP and pay once by UPI. Mobile lines, email and backup work today; fibre comes in about five days. Every update goes to WhatsApp, so nobody needs to call. In Accel's own data, customers who had to call five times were almost five times more likely to leave."

### Scene 8 · What Accel's team sees (2:25–2:50)
**Do:** In the Control room, click these tabs, about 5 seconds each:
1. **Live journeys**: the chats you just had, each with a score.
2. **KYC lab**: shows **12/12**.
3. **Bundle audit**: shows 56 of 368.
4. **Funnel & simulator**: drag one slider a little.

*Say:* "This is Accel's control room. Every chat gets a score for how likely it is to buy, so partners call the right people. All 12 sample KYC files get the right result. Last quarter, 15% of bundles sold by people broke the product rules; our app can't. With the same 5,000 leads, we expect about twice the customers at about a third of the cost."

### Scene 9 · Close (2:50–3:00)
**Do:** Click back on the phone tracker showing **Everything live**.
*Say:* "Ek Baithak: your business, live in one sitting. Thank you."

### If a judge asks you live
- **"What if the AI is down?"** "It tries three backup models, then simple built-in rules. Set `OFFLINE_MODE=1` and the whole journey still works."
- **"What if the owner has no GST?"** "They can still buy everything that doesn't need GST, today. K01's GST is cancelled, and it gets exactly that."
- **"Won't partners lose business?"** "No. They earn a fee on every app sale in their area, get ready-made leads with the full chat, and do the installs."
- **"Is the data safe?"** "Document photos are read on our server and never stored. ID numbers are hidden on staff screens, and every access is logged. Owners can see, download or delete their data."

---

## 4. Edit and upload the video to Google Drive

### Edit (Clipchamp, free, built into Windows 11; search "Clipchamp" in Start)
1. **Create a new video** → drag in your recording.
2. **Cut the waits:** move the playhead to the start of a wait, press **S** to split, split again at the end, select the piece, press **Delete**.
3. Optional: add a 2-second title card ("Ek Baithak · Team name") and captions (*Captions → Auto captions*).
4. Check the total length is **under 3:00**.
5. **Export → 1080p**. You get an MP4 file.

### Upload to Google Drive
1. Go to drive.google.com → **New → File upload** → choose the MP4. Name it `EkBaithak_Demo_<TeamName>.mp4`.
2. **Wait until Drive finishes processing** (10–30 minutes). Until then it says "video is still being processed".
3. Right-click the file → **Share** → under *General access* choose **Anyone with the link** → role **Viewer** → **Copy link**.
4. **Test it:** open the link in an Incognito window (Ctrl + Shift + N). If it plays there, judges can see it.

Yes, a Google Drive link is a good way to submit the demo video, as long as it's set to "Anyone with the link".

---

## 5. Put the code online and submit

### Option A (recommended): GitHub
1. Create an account at github.com if you don't have one.
2. Click **New repository** → name it `ek-baithak` → **Public** → don't tick "Add a README" → **Create**.
3. In Command Prompt:
   ```
   cd C:\Users\91738\Downloads\AIRTEL_SYNC_HACKATHON\ek-baithak
   git add .
   git commit -m "Ek Baithak: digital onboarding prototype for Accel Business"
   git branch -M main
   git remote add origin https://github.com/<your-username>/ek-baithak.git
   git push -u origin main
   ```
   (If asked, sign in to GitHub in the window that pops up.)
4. **Check your key is NOT online:** on the GitHub page, there should be **no `.env` file**. It is blocked by `.gitignore`. Only `.env.example` (empty) should be there.

### Option B: a zip on Google Drive
After step 3's `git commit`, run this in the same folder. It makes a zip **without** your secret key:
```
git archive -o ..\SUBMISSION\ek-baithak-code.zip HEAD
```
Upload `ek-baithak-code.zip` to Drive and share it the same way as the video.
⚠️ Don't right-click the folder and choose "Compress". That would include your `.env` file with the AI key.

### What to submit
| Required | What to give |
|---|---|
| Working prototype: demo video (≤ 3 min) | Google Drive link to the MP4 |
| Working prototype: code repository | GitHub link (or Drive link to the zip) |
| Solution architecture diagram | `SUBMISSION\Solution_Architecture.png` |
| Business case (≤ 10 slides) | `SUBMISSION\Ek_Baithak_Business_Case.pptx` (or the PDF). **First put your team name on slide 1.** |
| 1-page privacy & security note | `SUBMISSION\Privacy_Security_Note.pdf` |

### Last checks before you press submit
- [ ] Slide 1 shows your team name, not "<your name>".
- [ ] The video link and code link open in an Incognito window.
- [ ] The video is under 3 minutes.
- [ ] No `.env` file in the GitHub repo or zip.
- [ ] After the hackathon: create a new Gemini key and delete the old one (it was shared in chat).

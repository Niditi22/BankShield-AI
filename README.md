# BankShield React · Version 3 (October 2026)

**Updated from the uploaded BankShield React V2 project.** Existing user, review, and verification records remain compatible: `create_app()` applies additive SQLite migrations (`users.password_version`, `applications.decided_at`, and `password_resets`). Do not delete your old `instance/` directory.

## V3 additions (all six requested changes)

1. **Video timing:** `video_validation.py` counts decodable frames and measures **actual frame presentation timestamps** with PyAV rather than trusting WebM FPS alone. Accepts 10–45 s server-side, with 12–25 s guided in the recorder. The React recorder now cleans up timers/tracks, uses a monotonic stopwatch, records its duration for a cautious fallback, and shows validation errors clearly. `legacy_analysis.py` also derives rPPG sampling rate from verified media duration.
2. **Inline capture guidance:** Side instructions in the signature, live camera, and voice steps (also reference face photos). The `frontend/src` UI contains full React components; the included no-Node prebuilt frontend has an additional compatibility layer (`static/react/v3-enhancements.js`) for the same key flows.
3. **Model reliability:** Visual ViT now runs **aligned face crop and full camera frame** on four distributed frames, reports both raw median scores, flags inconsistent views/poor image sharpness, and avoids silently equating extreme classification scores with fraud probability. Video frame sampling does not depend on unreliable WebM FPS. These changes improve diagnostic transparency and robustness; **accuracy improvement is NOT established without a labeled benchmark**. Existing pinned model weights are unchanged, so existing `weights/` can be reused. No invented percentages or fabricated benchmarks.
4. **Clear output:** Improved React score cards distinguish similarity indices from fake-class scores, with conspicuous uncertainty flags, underlying view scores, and notes; the no-Node prebuilt UI adds compact score explanations.
5. **Forgot password:** Customer enters email, proposed password, and confirmation. The submitted password is salted-hashed; it is only activated after an administrator records an identity-checked decision. Requests are rate-limited, email enumeration is avoided, old sessions are invalidated, and the reset history is audited. No email/OTP is falsely claimed; officer must confirm identity *out-of-band* before approving. Admin users must use an administrator-controlled recovery process, not this customer form.
6. **Validation PDF:** Customer gets **Download PDF** only after an approve/disapprove decision. The generated PDF has reference number, customer, request type, submission/decision timestamps, officer reason and prototype-only disclaimer. It contains no raw biometric evidence or six model scores. Only that application's owner can download it; no digital seal is claimed.

## Quick Windows VS Code setup (PowerShell)

Open the extracted **`BankShield_React`** folder (the one containing `app.py`). If running for the first time, use Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_models.py
.\.venv\Scripts\python.exe -m flask --app app create-admin
.\.venv\Scripts\python.exe app.py
```

Open **http://localhost:5000**. The bundled static website works without installing Node. First-time model downloads are **not** included in this ZIP and require internet (~1.3 GB of model weights).

**Reusing your V2 data:** Before the FIRST launch in a new folder, copy the existing `instance/` folder to this new project directory, or use `migrate_data.py` as explained below. Do **not** create a second admin if you copy your existing database. If you copy your existing `weights/`, you normally do not need to download them again; run setup only if Model health says missing/failed. If you migrate, preserve `secret.key`, database, and `media` together. Always back up the original folder first.

**Every restart thereafter:**

```powershell
.\.venv\Scripts\python.exe app.py
```

**Optional — rebuild the full V3 React interface from source:** Requires Node.js LTS and internet for the first dependency install.

```powershell
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe app.py
```

The shipped static frontend uses the original prebuilt V2 asset plus a plain-JavaScript V3 compatibility layer because rebuild tooling is not embedded in the ZIP. **For all new V3 UI layouts including the side-by-side help cards and fully styled admin reset queue, run the optional React build.** In both paths, the server-side security, new model logic, camera validation, and PDF endpoint are V3.

### Tests and verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
cd frontend
npm test
```

Frontend tests require running `npm ci`. The model forward-pass/setup script verifies software functionality only, not real-world detection accuracy. See `CHANGELOG_V3.md`, `MODEL_GUIDE.md`, and `VALIDATION.md` for details.

---

## V2 baseline documentation (retained for reference)

### BankShield React · Version 2

A responsive React customer/admin app with Flask, SQLite, local pretrained model inference and background application processing.

## What changed
1. Enrollment face images now use **Open camera → Click photo → Retake** for front/left/right. There are no file-upload controls for faces. The signature remains an image upload.
2. Each admin enrollment section has green **Approve**, red **Deny** and amber **Request retake** buttons. Denials/retakes require notes. A denied revision can be corrected and resubmitted; an existing approved profile stays active.
3. Real local pretrained models are integrated, with one-time downloads, checksum verification, forward-pass diagnostics, processing status and reanalysis. No API keys or paid services are required. All six admin score fields are calculated on usable input after model setup.
4. React state, live dashboard polling, loading/error states, responsive layouts, camera cleanup, previews and a new dark-green/ivory design replace the old DOM-driven frontend. The prebuilt React app is included, so Node is **not required just to run it**.

## Read before interpreting the scores
The models work in the software sense: their weights load and real inference produces outputs. This is not a guarantee of correct classification. Classifier percentages are uncalibrated softmax scores; matching percentages are scaled cosine similarities, not identity probabilities. The signature classifier detects learned CEDAR forgery patterns, not AI generation; signature matching uses that classifier's features and is exploratory, not a trained signer-verification model. Visual deepfake detection analyzes sampled face frames, not temporal consistency or screen replay. rPPG remains a separate experimental pulse estimate. See MODEL_GUIDE.md for exact definitions and limitations.

The ZIP contains complete source, the built React frontend, pinned model download references and setup scripts. The approximately 1.3 GB of pretrained weights download from their original hosts during model setup; they are not duplicated inside the ZIP. After setup, inference uses local files only, with no upload of customer samples.

## Windows / VS Code setup — run in order
**Use 64-bit Python 3.12 (or 3.11).** Python 3.12 was tested. If the earlier `No suitable Python runtime found` error appears, install Python 3.12 from https://www.python.org/downloads/windows/ with “Add Python to PATH,” then restart VS Code. `py --list` shows installed versions.

1. Extract this ZIP to a new folder, such as `D:\BankShield_React`. Do not overwrite the old project.
2. VS Code → File → Open Folder → choose the folder containing `app.py`, `requirements.txt` and `setup_models.py`.
3. Terminal → New Terminal (PowerShell). Run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_models.py
```

If using Python 3.11, replace only the first command with `py -3.11 -m venv .venv`. Virtual-environment activation is not needed.

**Do not skip `setup_models.py`.** It prints download progress and a JSON diagnostic report. Wait until it reports `"ready": true` and `Model setup complete`. Initial installation needs internet and can take several minutes. Allow several GB of disk space for the Python environment, downloads and uploads. A CPU can run the models; a machine with 8 GB RAM may work, but 16 GB is preferable. Inference time depends on your CPU and clip length; processing runs in a background thread and the dashboard updates automatically.

4. Choose ONE account setup path:

**Fresh account/database:**
```powershell
.\.venv\Scripts\python.exe -m flask --app app create-admin
```
Enter your admin email and a password of at least 12 characters. Password input is hidden. There is no default admin password.

**Keep your existing accounts instead:** stop the old server with Ctrl+C. Before running any app/create-admin command in the new folder, use:
```powershell
.\.venv\Scripts\python.exe migrate_data.py "D:\BankShield\instance"
```
Change the source path if your old folder is elsewhere. Migration refuses to overwrite a nonempty destination. Your old data are left unchanged. Reuse your existing admin login. Old pending applications can be reanalyzed from the new admin dashboard.

5. Start the website:
```powershell
.\.venv\Scripts\python.exe app.py
```

Open **http://localhost:5000** in Chrome or Edge. Allow camera and microphone access. Keep the terminal open. Use the normal browser window for the customer and an incognito window for the admin, because tabs in one browser profile share a session.

## Every later restart
Run only:
```powershell
.\.venv\Scripts\python.exe app.py
```
Or double-click `start.bat`. Do not repeat setup, migration or create-admin each time.

## Customer and admin workflow
- Register: mandatory personal details, signature upload, three manually captured photos and a language-specific voice challenge.
- Customer can enter a restricted status/correction portal before enrollment approval; banking applications remain backend-blocked until approval.
- Admin reviews each section. All sections must be approved to activate the enrollment. A Deny rejects the revision; Request retake asks for corrections. Both require replacing the flagged section before resubmission.
- Approved customers can propose profile changes. The old approved profile stays active until the admin accepts a revision.
- Verification: signature upload → record camera video → record voice → send Loan/Pension/KYC verification request.
- Video: remain still and front-facing for about 15 seconds, then turn gently left/right. Record at least 12 seconds; capture stops automatically at 25 seconds.
- Voice: choose English/Hindi/Marathi, read the displayed phrase and six-digit code, record 3–40 seconds, press Stop and review playback.
- The server validates media and queues analysis. The admin sees processing stages and then all six score fields beside the evidence. Customer responses never contain analysis scores.
- Missing/failed models and poor-quality samples remain explicit failures, not zero-risk scores. Admin can inspect Model health, fix setup or request better evidence, then Reanalyze a pending application.
- Final approval is blocked until all six score fields have computed successfully. Disapproval is permitted if evidence is incomplete. Finishing all six checks is only a completeness condition, not an automatic authenticity verdict.
- Admin records a final decision and reason; the customer's screen refreshes automatically within about five seconds. Approval is for the verification request, not a loan sanction or pension entitlement.

## Why no “perfect percentages”?
A model output of 95% is not a measurement that the sample is “95% real.” Signature and speaker identity can be imitated; a replay can contain a pulse; a copied signature can match perfectly. This build does not turn a similarity score into a fake score by subtracting it from 100. Each classifier and matcher is independent, with its meaning shown. Calibration and evaluation on representative data are necessary before operational claims.

## Model health / downloads
`setup_models.py` downloads fixed revisions, validates SHA256 hashes and runs actual forward passes. The Model health page shows the latest diagnostics. If a download fails, rerun the same command; verified files are reused. No need to edit Python to connect the models. Model files live in `weights/`. Keep them for offline use.

Downloads use Hugging Face and GitHub. A firewall/network block can prevent setup; use a network that permits those hosts. If a model is later removed or inaccessible, the setup script reports the failure. No generic placeholder result is substituted.

## Optional: editing the React interface
The app is already built. Only if changing frontend source, install a supported Node.js LTS version, then run:
```powershell
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe app.py
```
For development, run Python as above in one terminal and `cd frontend` then `npm run dev` in another. Open the URL printed by Vite. Vite proxies `/api` and `/media` to Flask. Never use `flask run` for normal operation: `app.py` starts the background inference worker as well as the server.

## Troubleshooting
- Camera denied/busy: allow permissions at the browser address bar, close Teams/Zoom/other camera apps and retry. Insecure remote HTTP will not provide camera access; use localhost.
- Picture unclear: Retake; keep face visible and avoid a full 90-degree side profile. Slight left/right turns help the face detector retain both eyes.
- Face score failed: at least one approved reference and three video frames need a single clear detectable face. Replace references or submit a clearer new application.
- rPPG unavailable: this can occur despite successful deepfake/face scores. Remain steady, use stable light and keep the forehead visible. Lack of signal is inconclusive, not evidence of fraud.
- “Queued” indefinitely: make sure you started `python app.py`, not `flask run`. Check terminal output. Restarting requeues jobs interrupted during processing.
- “Partial”/“Failed”: open the application for the exact error. Check Model health and rerun setup if necessary; reanalyze after fixing the cause. Poor inputs may require a new recording/application.
- Earlier completed applications: scores are saved with the reference snapshot, not recalculated when the profile changes. Already decided applications cannot be reanalyzed or decided again.
- Audio silence/short: select the correct Windows microphone and read the phrase fully. The score works on original audio. The filtered copy is for listening only.
- Prompt expired: change the language to obtain a new prompt and record again. Prompts expire after 20 minutes; spoken phrase correctness is checked manually, not by ASR.
- Session expired: sign in again. Forms are not persisted across sign-out/page reload, for privacy.
- Model warning about attention masks: the tested WavLM package can log a PyTorch deprecation warning; successful finite output is still verified by setup diagnostics.

## Testing
```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```
Optional frontend tests:
```powershell
cd frontend
npm ci
npm test
```
See VALIDATION.md for what was actually checked. Automated inference smoke tests do not measure real/fake accuracy. Physical webcam/microphone testing on Windows remains a local acceptance step.

## Files and data
`app.py` handles authentication, review and SQLite persistence. `worker.py` processes the durable queue. `inference.py` loads actual pretrained models. `model_catalog.py` pins references and hashes; `setup_models.py` installs and diagnoses them. `frontend/src/` contains React. `static/react/` contains the prebuilt app. `instance/` contains runtime data and is excluded from this ZIP.

This remains a local research application. It has hashed passwords, CSRF checks, role-based media access, immutable reference snapshots and approval gating. It does not include encrypted biometric storage, MFA, account recovery, verified identity proofing, production rate limits/resource quotas, tamper-proof logs, retention/deletion administration, ASR, replay/injection-resistant camera hardware, regulatory certification or deployment hardening. Use test data. Do not expose the local server or use it for real lending/pension decisions. Customer photos and audio cannot establish that the enrollment identity itself is genuine.

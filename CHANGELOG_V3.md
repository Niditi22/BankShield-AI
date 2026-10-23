# BankShield React V3 - implementation and limitations

## Changed files

- `app.py`: password reset requests/admin approvals, session invalidation on reset, customer-only reportlab PDF, timestamp-aware video validation, schema migration, static V3 compatibility file routes.
- `video_validation.py` (new): count/inspect decoded video frame timestamps; do not infer duration from bad WebM FPS metadata.
- `legacy_analysis.py`: experimental rPPG derives effective FPS from the validated duration.
- `inference.py`: ViT two-view multi-frame check with raw scores and discrepancy warning; frame sampling independent of FPS; score interpretation metadata.
- `frontend/src/main.jsx`: forgot password route, staff reset requests, guidance, customer PDF links, clarified scores.
- `frontend/src/Capture.jsx`: more reliable recording lifecycle; returns blob and local monotonic duration.
- `frontend/src/style.css`: new capture/manual, reset, report, score layouts.
- `static/react/v3-enhancements.js`, `v3-overrides.css`: no-Node compatibility additions to shipped V2 bundle.
- `requirements.txt`: adds `av` and `reportlab`.
- `tests/test_v3.py`: regression tests for reset, PDF authorization, and duration logic.

## Integrity and privacy

PDFs are generated only from a server-side recorded decision; a customer cannot insert one with a pending decision. The PDF is an informational electronic copy; it is not digitally signed, independently verifiable, or proof of approval of a loan/pension. The password reset does not independently authenticate the claimant: administrator approval **requires independent identity checks**. Deploy behind TLS, add institutional authentication and an approved secure recovery protocol before production.

## Accuracy note

No training data, labeled videos, adversarial examples, or external calibration set were attached. Real-world false-positive and false-negative rates cannot be established from the code. A score of 99% after inference can still be wrong. V3 shows which representation generated it and flags disagreements; it does NOT hide or force down high scores. For statistically demonstrable accuracy gains, record ground-truth test cases under varied lighting/language/attacks, evaluate per-model ROC/EER/FAR/FRR, hold out unseen identities, and calibrate with held-out representative data. Do not automatically approve customers based on any one score.

## Runtime validation available for this build

Python source syntax and `video_validation.py` synthetic timestamp checks were verified. PyAV, Flask and complete Node dependencies were unavailable in the build environment, so full integration tests and the `npm run build` step could **not** be executed here. Run tests in the target Windows VS Code environment after installation. The included static browser code was syntax-checked using Node. No real-model accuracy benchmark is claimed.

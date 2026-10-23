# Validation performed for Version 2

## Passed
- React production build with Vite: successful; compiled assets included.
- Seven backend tests: CSRF/role restrictions; private media ownership; pending enrollment gate; section correction/approval; Deny and resubmit; application queuing and approval completeness gate; immutable reference snapshots; final decision protection; invalid media/challenge handling; admin model health privacy; React shell served.
- Three React component tests: camera opens only after user action; no face-file-upload control; capture occurs only on Click photo; camera stops after capture/unmount; permission denial produces a useful message. Browser APIs are mocked in these tests.
- Real pretrained forward-pass smoke tests: ResNet-34 signature, ViT visual classifier, Wav2Vec2 audio classifier, WavLM XVector and OpenCV YuNet/SFace all loaded and returned finite outputs.
- Full inference function smoke test: all six output fields computed using a drawn signature, a repeated official OpenCV sample face image in a generated video, and a synthetic audio tone. This tests program integration and label/shape handling only. It is **not** a biometric or real/fake accuracy evaluation.
- Checkpoint integrity: downloaded assets verified against model-host LFS digests when provided; all shipped model references now have pinned local SHA256 digests.

- Full API → real background worker → admin approval → customer status integration check passed using synthetic/fixture media; customer response contained no analysis scores.

## Not verified
- Browser visual screenshots and physical webcam/microphone behavior: unavailable in the build environment. Perform the manual checklist below on your Windows laptop.
- Detection accuracy, probability calibration, adversarial robustness, biometric fairness, unseen attack generators and banking deployment suitability.
- A trained signer-identity model: signature similarity uses classifier features, with an explicit exploratory label.
- Real-world liveness/replay resistance, ASR challenge validation and verified identity enrollment.
- Windows installation was documented, not executed on a Windows host. Tests ran on Linux with Python 3.12 and CPU PyTorch 2.6.0.

## Local acceptance checklist
1. Start the app and open Chrome/Edge at localhost:5000; permit camera/microphone.
2. Register with three camera photos, signature and voice. Retake a photo and verify the preview changes.
3. Sign in as admin in incognito. Check each colored decision button and deny/retake with a note. Correct just that section as the customer, then approve.
4. Open Model health; confirm all setup checks passed.
5. Submit a clear 12–25 second camera clip and 3–40 second spoken phrase. Watch stages move from queued to running to complete, or inspect a concrete failure.
6. Review original and filtered audio, reference and current face evidence, and six separate model outputs. An inconclusive rPPG estimate is allowed and explicitly labeled.
7. Approve/disapprove with a reason. Confirm the customer's page updates automatically without receiving model scores.
8. Test narrow window/mobile layouts, camera denial, too-short capture, bad lighting and a model-download failure. Neither missing nor failed checks should appear as 0% fake.

The goal of these tests is to prove that code paths execute and access restrictions hold. They cannot establish that the classifiers' outputs are factually correct for a given customer.

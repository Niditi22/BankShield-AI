# Model guide and score definitions

## Six separate outputs

| Admin field | Actual implementation | Percentage meaning |
|---|---|---|
| Signature forgery score | NethranjaliSE/resnet34-signature-verification; ResNet-34, CEDAR training | Softmax for published class 0 (`Forged`) ×100. Experimental forgery classifier, **not AI-generated-signature detection**. |
| Signature feature similarity | Pooled features from the same trained signature classifier | Cosine similarity ×100, negatives clipped to 0. **Exploratory comparison**, not a signer-specific verification model and not a calibrated identity probability. |
| Visual deepfake score | dima806/deepfake_vs_real_image_detection; pretrained ViT | V3 uses 4 sampled video frames with both an aligned face crop and full camera frame. Score = median of paired-view fake-class softmax means ×100; preserves each view’s raw median and flags disagreement. **Not a calibrated probability or confirmed improvement in accuracy.** |
| Face similarity | OpenCV YuNet detection/alignment and SFace recognition | Median across sampled video frames of the highest similarity to usable approved reference views. Cosine ×100, negatives clipped to 0; raw cosine saved. |
| Synthetic-speech score | MelodyMachine/Deepfake-audio-detection; Wav2Vec2 classifier | Mean `fake` softmax ×100 across up to six audible original-audio windows at 16 kHz. No probability calibration for this banking context. |
| Speaker similarity | microsoft/wavlm-base-plus-sv; WavLM XVector | Cosine of averaged normalized speaker embeddings ×100, negatives clipped to 0; raw cosine saved. Uses up to three audio windows per recording. |

V3 does not replace pretrained weights. Camera reliability has stronger diagnostics, but classification accuracy must be measured on labeled data. These are actual forward-pass results. Values are never generated randomly, fixed to a success value, or derived as `100 - match` to simulate a forgery model. A failed model/input produces a failed state and an explanatory message rather than a fabricated percentage. Scores remain admin-only.

## Interpretation constraints
- Signature classifier: the publisher describes a small CEDAR-based model. The advertised loss is not evidence of generalizable bank-level accuracy. We have not independently reproduced their accuracy. Photographed and Indic-script signatures can differ substantially from the training data. The matching features were learned for binary forgery classification, not signer identity, so treat their similarity only as an exploratory aid.
- Visual classifier: the author explicitly warns about concept drift as generators improve. Cropped video-frame inputs can also differ from its training distribution. A replay of genuine footage may score real. No temporal synchronization, injected-camera detection, presentation-attack model or motion challenge verification is included.
- Audio classifier: published training/evaluation context is incomplete. The UI supports English/Hindi/Marathi prompts, but model accuracy for those languages, codecs, microphones and present-day cloning methods has not been established here.
- Speaker model: a cloned voice can retain the original speaker's identity. A strong speaker match does not mean the audio is genuine. WavLM's example threshold is dataset-dependent; this app does not convert it into a universal accept/reject rule.
- Face model: a face swap can resemble an enrolled person and match strongly. Identity similarity and fake-image classification remain separate. Unusable side-profile references are omitted with a note, never silently replaced with a perfect score.
- Enrollment is not independently identity-proofed. A fraudster could enroll their own photo or an already manipulated reference. The bank must establish a trustworthy reference through a separate verified process.
- Reading the spoken challenge is manually reviewed. There is no transcription/ASR correctness check. A nonce in the displayed prompt is not proof that the recorded audio contains that nonce.

## rPPG: separate signal, separate claim
The app retains the experimental rPPG implementation: frontal-face detection, forehead-region green-channel sampling, interpolation, detrending and spectral analysis in the 0.7–3 Hz band. It requires at least 10 seconds and adequate face visibility. An estimate is in BPM, not “realness percent.” Lighting/motion artifacts can produce apparent pulse peaks. Genuine recordings may fail; replayed or generated recordings may carry pulse-like signals. No rPPG result is fused into a guaranteed deepfake score.

Reference for the broader research field: https://github.com/phuselab/pyVHR . No pyVHR code is bundled or represented as this implementation.

## Preprocessing
- Signature: orientation correction, white alpha composite, foreground crop, aspect-preserving letterbox to 600×240. The classifier applies its published 224×224 RGB ImageNet-normalized transform. This normalization can change acquisition artifacts; results still require validation.
- Enrollment face captures: saved as PNG, normalized to 480×480. YuNet finds landmarks; SFace aligns each usable face.
- Video V3: original clip is stored, timestamp duration is verified via PyAV when installed, four uniformly spread groups of decoded frames are sampled independently of FPS metadata, and at least three sampled single-face crops are required. Crop/full-frame disagreement is flagged. rPPG separately processes the temporal clip with timing corrected from decoded duration.
- Audio: original PCM WAV retained for model inference. Resampled to 16 kHz using polyphase resampling. Low-energy windows are excluded using an energy threshold; this is not semantic speech segmentation. A band-pass filtered, edge-trimmed copy is created for human listening; models use the original.

## Download and execution integrity
The model catalog pins Hugging Face revisions and SHA256 hashes. OpenCV assets are also checked against pinned SHA256 hashes, even though their download URLs point to a branch path. A changed upstream file fails the checksum check. No Hugging Face remote model code is enabled. The signature publisher serialized standard torchvision classes, which are loaded with `weights_only=True` and a small explicit framework-class allowlist. No unrestricted pickle execution is used. Speaker weights load through the tested Transformers/PyTorch versions. Other classifiers use safetensors.

First-time setup fetches model files and model cards only; it does not upload customer evidence. Application inference uses `local_files_only=True`. The single worker loads and releases the larger classifiers sequentially to limit memory, while face models remain cached. Model versions are saved with each result.

## What is still needed for “correct percentages”
To present calibrated probabilities, collect representative consenting test data, define labels and attack types, split by identity/source, select thresholds using validation data, evaluate on held-out customers and newer generators, and calibrate scores separately. Measure false acceptance, false rejection, failure-to-acquire and performance by capture condition and language. A percentage display alone does not provide these guarantees. BankShield includes no fabricated accuracy benchmark.

## Sources and licenses
Weights are downloaded from the authors rather than redistributed in the code ZIP. Check each model card and dataset conditions before reuse beyond research.

- Signature model / MIT model-card declaration: https://huggingface.co/NethranjaliSE/resnet34-signature-verification
- Visual classifier / Apache-2.0 model-card declaration: https://huggingface.co/dima806/deepfake_vs_real_image_detection
- Audio classifier / Apache-2.0 model-card declaration: https://huggingface.co/MelodyMachine/Deepfake-audio-detection
- Speaker verification model and linked license: https://huggingface.co/microsoft/wavlm-base-plus-sv
- OpenCV face detector and per-model license: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- OpenCV face recognition and per-model license: https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
- Model-specific README files are retained in `weights/` after setup.

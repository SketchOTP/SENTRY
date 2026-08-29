# SENTRY M3 — Primary-user identity

M3 adds one deliberately enrolled local identity, `primary_user`, while
keeping `unknown` and `unresolved` as first-class outcomes. Identity is an
annotation on an existing person track; it never controls room occupancy.

## Backend and provenance

The implementation uses OpenCV 4.12's native `FaceDetectorYN` and
`FaceRecognizerSF` APIs:

- YuNet: `face_detection_yunet_2023mar.onnx`, OpenCV Zoo revision
  `47534e27c9851bb1128ccc0102f1145e27f23f98`, MIT license, source at
  `https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet`.
  Exact download source:
  `https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx`.
  Size: `232,589` bytes.
  Local SHA-256:
  `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
- SFace: `face_recognition_sface_2021dec.onnx`, the same OpenCV Zoo
  revision, Apache-2.0 license, source at
  `https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface`.
  Exact download source:
  `https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/face_recognition_sface_2021dec.onnx`.
  Size: `38,696,353` bytes.
  Local SHA-256:
  `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`.

The model files are downloaded to ignored
`perception-data/models/opencv-zoo/`. They are not committed. The current
configuration records the hashes and refuses a mismatched artifact.

## Runtime contract

The camera frame is processed transiently as:

```text
YuNet face + landmarks -> unique geometric association to an existing person track
-> face-size/clip/sharpness gate -> SFace alignCrop/feature -> cosine match
```

Identity runs at a configurable 2 Hz cadence while the room is not empty.
No face inference runs for an empty room. A face loss, poor-quality face,
ambiguous association, or model failure yields `unresolved`; a usable
non-match yields `unknown`.

The initial conservative defaults are a YuNet score of `0.90`, minimum face
size `60px`, Laplacian sharpness `20`, cosine threshold `0.45`, and three
matching observations within two seconds. These are starting configuration,
not M3 acceptance evidence; enrollment and held-out negative evaluation must
calibrate the final threshold.

## Enrollment and storage

Run enrollment deliberately with the configured camera:

```text
python tools/sentry_enroll_identity.py --display-name "<name>"
```

Press Enter only when the intended single-face pose is ready. Sixteen accepted
samples across modest pose/distance variation are the default. Frames and
individual embeddings are discarded after each in-memory feature extraction;
only a normalized mean prototype is stored.

To explicitly remove the active profile:

```text
python tools/sentry_identity_admin.py delete
```

The profile is stored in schema version 3 of the local SQLite database and is
included only in SQLite-consistent Atlas snapshots. Its metadata records the
YuNet and SFace model hashes together as the profile provenance. API persons
and identity events never expose the prototype. No prototype, enrollment
frame, unknown embedding, or raw frame is written to Git, Notion, logs, or
Codex/Luna.

## Qualification boundary

Static model loading and deterministic identity contracts are regression
evidence. M3 is not qualified until the owner/operator supplies a fresh
high-quality primary-user holdout and a consenting non-primary negative
segment. The required decision is conservative: at least 98% accepted-ID
precision and at least 80% high-quality genuine recognition, with no false
primary-user assignment in the controlled negative segment.

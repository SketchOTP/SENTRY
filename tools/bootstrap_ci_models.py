"""Download the public, checksummed model artifacts required by CI tests.

Production model files remain ignored and locally managed.  This helper exists
only so the public GitHub Actions runner can reproduce model-loading contract
tests without private configuration, Atlas storage, or hardware.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


ARTIFACTS = (
    (
        "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/"
        "models_bin/1/person-detection-0202/FP32/person-detection-0202.xml",
        ROOT / "perception-data/models/person-detection-0202/FP32/person-detection-0202.xml",
        "sha384",
        "fc218405d14ca82811a239f841a90eb9f6e1a8d2e8269956471e79bfaba34f3f5ac7070e1d33aa5d2101460854b72a6a",
    ),
    (
        "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/"
        "models_bin/1/person-detection-0202/FP32/person-detection-0202.bin",
        ROOT / "perception-data/models/person-detection-0202/FP32/person-detection-0202.bin",
        "sha384",
        "e807fab165c5327cf726eea6f5d70832dd4bbaec865d929b1ead67061759cf809debf0e43d53b23d612b4c3320eab578",
    ),
    (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
        "47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/"
        "face_detection_yunet_2023mar.onnx",
        ROOT / "perception-data/models/opencv-zoo/yunet/face_detection_yunet_2023mar.onnx",
        "sha256",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
        "47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/"
        "face_recognition_sface_2021dec.onnx",
        ROOT / "perception-data/models/opencv-zoo/sface/face_recognition_sface_2021dec.onnx",
        "sha256",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
    (
        "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx",
        ROOT / "perception-data/models/yolox-s/yolox_s.official.onnx",
        "sha256",
        "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063",
    ),
)


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def ensure_artifact(url: str, path: Path, algorithm: str, expected: str) -> None:
    if path.is_file() and digest(path, algorithm) == expected:
        print(f"verified {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    request = Request(url, headers={"User-Agent": "SENTRY-CI-model-bootstrap/1"})
    with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    actual = digest(temporary, algorithm)
    if actual != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"checksum mismatch for {path.name}: {actual}")
    os.replace(temporary, path)
    print(f"downloaded and verified {path.relative_to(ROOT)}")


def ensure_yolox_ir() -> None:
    output_dir = ROOT / "perception-data/models/yolox-s/converted_openvino"
    xml = output_dir / "yolox_s.xml"
    binary = output_dir / "yolox_s.bin"
    if xml.is_file() and binary.is_file():
        print(f"found {xml.relative_to(ROOT)}")
        return
    from openvino import convert_model, serialize

    output_dir.mkdir(parents=True, exist_ok=True)
    source = ROOT / "perception-data/models/yolox-s/yolox_s.official.onnx"
    model = convert_model(str(source))
    serialize(model, str(xml), str(binary))
    print(f"converted {xml.relative_to(ROOT)}")


def main() -> int:
    for artifact in ARTIFACTS:
        ensure_artifact(*artifact)
    ensure_yolox_ir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

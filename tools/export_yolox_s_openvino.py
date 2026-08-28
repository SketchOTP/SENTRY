"""Convert the official YOLOX-S ONNX release artifact to OpenVINO IR.

This is an isolated export utility.  PyTorch/training dependencies are not
part of SENTRY production; the official ONNX artifact is the reproducible
upstream export input and the generated IR remains ignored under
``perception-data/models``.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="official YOLOX-S ONNX artifact")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.input.is_file():
        parser.error(f"input ONNX file not found: {args.input}")
    try:
        from openvino import convert_model, serialize
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("openvino is required for YOLOX-S export") from exc
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_xml = args.output_dir / "yolox_s.xml"
    model = convert_model(str(args.input))
    serialize(model, str(output_xml), str(args.output_dir / "yolox_s.bin"))
    print(output_xml)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

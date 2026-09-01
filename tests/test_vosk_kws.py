"""Focused Vosk evaluator tests without requiring a Vosk model artifact."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from perception.vosk_kws import VoskKwsEvaluator


class _Recognizer:
    def __init__(self, _model, _sample_rate, grammar):
        self.grammar = grammar
        self.payload = {"partial": ""}
        self.final = False

    def AcceptWaveform(self, _pcm):
        return self.final

    def PartialResult(self):
        return json.dumps(self.payload)

    def Result(self):
        return json.dumps(self.payload)


class VoskKwsTests(unittest.TestCase):
    def _evaluator(self, **kwargs) -> VoskKwsEvaluator:
        model = Path(tempfile.mkdtemp())
        self.recognizer = _Recognizer(None, 16_000, "")
        self.grammar = None

        def recognizer_factory(_model, _sample_rate, grammar):
            self.grammar = grammar
            return self.recognizer

        return VoskKwsEvaluator(
            model,
            model_factory=lambda _path: object(),
            recognizer_factory=recognizer_factory,
            **kwargs,
        )

    def test_vocab_retains_unknown_token_and_exact_wake_is_emitted_once(self) -> None:
        evaluator = self._evaluator()
        self.assertEqual('["sentry", "[unk]"]', self.grammar)
        self.recognizer.payload = {"partial": "sentry"}
        self.assertEqual(1, len(evaluator.feed(np.zeros(1_280, dtype=np.int16))))
        self.assertEqual([], evaluator.feed(np.zeros(1_280, dtype=np.int16)))

    def test_nonwake_and_pcm_shape_are_rejected(self) -> None:
        evaluator = self._evaluator()
        self.recognizer.payload = {"partial": "[unk]"}
        self.assertEqual([], evaluator.feed(np.zeros(1_280, dtype=np.int16)))
        with self.assertRaisesRegex(ValueError, "signed 16-bit"):
            evaluator.feed(np.zeros(16, dtype=np.float32))

    def test_final_only_ignores_partial_wake(self) -> None:
        evaluator = self._evaluator(detect_partial=False)
        self.recognizer.payload = {"partial": "sentry"}
        self.assertEqual([], evaluator.feed(np.zeros(1_280, dtype=np.int16)))

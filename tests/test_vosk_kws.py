"""Focused Vosk evaluator tests without requiring a Vosk model artifact."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from perception.vosk_kws import (
    VoskKwsEvaluator,
    VoskRuntimeUnavailable,
    VoskSharedModel,
    VoskStreamingCommandRecognizer,
)


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

    def SetWords(self, value):
        self.words = value

    def SetPartialWords(self, value):
        self.partial_words = value

    def Reset(self):
        self.payload = {"partial": ""}
        self.final = False


class _RecognizerFactory:
    def __init__(self):
        self.instances = []

    def __call__(self, model, sample_rate, grammar=None):
        recognizer = _Recognizer(model, sample_rate, grammar)
        recognizer.is_wake = grammar is not None
        self.instances.append(recognizer)
        return recognizer


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
        detections = evaluator.feed(np.zeros(1_280, dtype=np.int16))
        self.assertEqual(1, len(detections))
        self.assertEqual(detections[0].wake_token, "sentry")
        self.assertEqual(detections[0].detection_source, "partial")
        self.assertEqual(detections[0].detected_sample, 1_280)
        self.assertIsInstance(detections[0].wake_event_id, str)
        self.assertEqual([], evaluator.feed(np.zeros(1_280, dtype=np.int16)))

    def test_final_word_timing_is_metadata_only(self) -> None:
        evaluator = self._evaluator()
        self.recognizer.final = True
        self.recognizer.payload = {
            "text": "sentry",
            "result": [{"word": "sentry", "start": 0.1, "end": 0.4}],
        }
        detection = evaluator.feed(np.zeros(16_000, dtype=np.int16))[0]
        self.assertEqual(detection.detection_source, "final")
        self.assertEqual(detection.token_end_sample, 6_400)
        self.assertEqual(detection.samples_after_token, 9_600)
        self.assertFalse(hasattr(detection, "queued_before"))
        self.assertFalse(hasattr(detection, "queued_after_token"))

    def test_transient_partial_wake_is_not_enough_to_activate(self) -> None:
        evaluator = self._evaluator(partial_confirmation_frames=2)
        self.recognizer.payload = {"partial": "sentry"}
        self.assertEqual([], evaluator.feed(np.zeros(512, dtype=np.int16)))
        self.recognizer.payload = {"partial": "[unk]"}
        self.assertEqual([], evaluator.feed(np.zeros(512, dtype=np.int16)))
        self.assertNotEqual(evaluator.last_result_class, "wake")

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

    def test_shared_model_creates_independent_wake_and_command_recognizers(self) -> None:
        model_path = Path(tempfile.mkdtemp())
        factory = _RecognizerFactory()
        model_loads = []
        shared = VoskSharedModel(
            model_path,
            model_factory=lambda path: model_loads.append(path) or object(),
            recognizer_factory=factory,
        )
        wake = VoskKwsEvaluator(model_path, shared_model=shared)
        command = VoskStreamingCommandRecognizer(shared)

        self.assertEqual(len(model_loads), 1)
        self.assertEqual(len(factory.instances), 2)
        self.assertIsNot(factory.instances[0], factory.instances[1])
        self.assertEqual(factory.instances[0].grammar, '["sentry", "[unk]"]')
        self.assertIsNone(factory.instances[1].grammar)
        self.assertTrue(factory.instances[1].partial_words)
        wake.close()
        command.close()

    def test_command_stream_reports_progress_without_exposing_text(self) -> None:
        model_path = Path(tempfile.mkdtemp())
        factory = _RecognizerFactory()
        shared = VoskSharedModel(
            model_path,
            model_factory=lambda _path: object(),
            recognizer_factory=factory,
        )
        command = VoskStreamingCommandRecognizer(shared)
        recognizer = factory.instances[-1]
        recognizer.payload = {
            "partial": "move the controlled file",
            "partial_result": [{"word": "move"}, {"word": "the"}, {"word": "controlled"}, {"word": "file"}],
        }
        update = command.feed(np.zeros(512, dtype=np.int16))
        self.assertTrue(update.progressed)
        self.assertEqual(update.partial_word_count, 4)
        self.assertFalse(hasattr(update, "text"))

        same = command.feed(np.zeros(512, dtype=np.int16))
        self.assertFalse(same.progressed)
        recognizer.final = True
        recognizer.payload = {"text": "move the controlled file"}
        finalized = command.feed(np.zeros(512, dtype=np.int16))
        self.assertTrue(finalized.progressed)
        self.assertEqual(finalized.finalized_segment_count, 1)
        command.reset()
        self.assertEqual(command.last_result_class, "reset")

    def test_command_stream_malformed_result_fails_closed(self) -> None:
        model_path = Path(tempfile.mkdtemp())
        factory = _RecognizerFactory()
        shared = VoskSharedModel(
            model_path,
            model_factory=lambda _path: object(),
            recognizer_factory=factory,
        )
        command = VoskStreamingCommandRecognizer(shared)
        factory.instances[-1].PartialResult = lambda: "not-json"
        with self.assertRaises(VoskRuntimeUnavailable):
            command.feed(np.zeros(512, dtype=np.int16))

    def test_missing_shared_model_fails_explicitly(self) -> None:
        with self.assertRaises(VoskRuntimeUnavailable):
            VoskSharedModel(Path(tempfile.mkdtemp()) / "missing")

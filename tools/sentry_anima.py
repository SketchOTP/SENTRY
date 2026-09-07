"""Opt-in, host-owned ANIMA lifecycle for the existing resident voice turn.

Only the separately installed client module is loaded: no ANIMA Core imports,
house credentials, conversation persistence, or autonomous-to-owner conversion.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

VOICE_SURFACE: ContextVar[str | None] = ContextVar(
    "sentry_anima_voice_surface", default=None
)
TURN_SECONDS = 270
FINAL_RESERVE_SECONDS = 15


@contextmanager
def voice_origin(source_surface: str) -> Iterator[None]:
    """Do not infer authority from request text, model output, or sensor events."""
    token = VOICE_SURFACE.set(
        source_surface if source_surface == "always_on_voice" else None
    )
    try:
        yield
    finally:
        VOICE_SURFACE.reset(token)


def config_path() -> Path:
    return (
        Path(os.environ.get("SENTRY_ANIMA_CONFIG", "~/.config/sentry/anima.json"))
        .expanduser()
        .absolute()
    )


def binding_root() -> Path:
    return (
        Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser().absolute()
        / "sentry/anima-turns"
    )


def private_json(path: Path) -> dict[str, Any]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ValueError("private file required")
        with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as stream:
            raw = stream.read(65537)
        if len(raw.encode("utf-8")) > 65536:
            raise ValueError("private file too large")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError("private object required")
        return value
    finally:
        os.close(fd)


def filesystem_denies(filesystem: dict[str, Any], protected: Path) -> bool:
    """Prove literal deny coverage, never string prefixes or symlink aliases.

    More-specific read/write grants invalidate an ancestor proof, including
    grants below protected directories such as the per-turn binding root.
    """

    # We cannot prove precedence for arbitrary absolute glob grants. Generated
    # resident profiles use glob rules only under the separate workspace table.
    if any(
        isinstance(key, str)
        and Path(key).is_absolute()
        and mode != "deny"
        and any(mark in key for mark in ("*", "?", "["))
        for key, mode in filesystem.items()
    ):
        return False

    def covers(parent: Path, child: Path) -> bool:
        return child.is_relative_to(parent) and child.resolve().is_relative_to(
            parent.resolve()
        )

    rules = [
        (Path(key), mode)
        for key, mode in filesystem.items()
        if isinstance(key, str)
        and Path(key).is_absolute()
        and not any(mark in key for mark in ("*", "?", "["))
        and ".." not in Path(key).parts
    ]
    candidates = [
        path for path, mode in rules if mode == "deny" and covers(path, protected)
    ]
    if not candidates:
        return False
    closest = max(candidates, key=lambda path: len(path.parts))
    return not any(
        mode != "deny"
        and covers(closest, path)
        and (covers(path, protected) or covers(protected, path))
        for path, mode in rules
    )


@dataclass(frozen=True)
class AnimaConfig:
    endpoint: str
    token_file: Path
    worker_id: str
    client_directory: Path
    path: Path

    @classmethod
    def load(cls, path: Path | None = None) -> AnimaConfig | None:
        path = path or config_path()
        try:
            data = private_json(path)
        except FileNotFoundError:
            return None
        if data.get("enabled") is not True:
            return None
        for key in ("endpoint", "token_file", "worker_id", "client_directory"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ValueError("incomplete ANIMA configuration")
        token = Path(data["token_file"])
        client = Path(data["client_directory"])
        if not token.is_absolute() or not client.is_absolute() or token.is_symlink():
            raise ValueError("absolute host-owned paths required")
        return cls(
            data["endpoint"],
            token.resolve(),
            data["worker_id"],
            client.resolve(),
            path.resolve(),
        )

    def validate_workspace(self, workspace: Path) -> None:
        for protected in (
            self.token_file,
            self.client_directory,
            self.path,
            binding_root().resolve(),
        ):
            if protected.is_relative_to(workspace.resolve()):
                raise ValueError("ANIMA host paths cannot be in the model workspace")

    def client(self) -> Any:
        # The private host configuration chooses this installed, fixed module;
        # neither model arguments nor browser requests select Python/executables.
        path = self.client_directory / "anima_household_client.py"
        spec = importlib.util.spec_from_file_location("sentry_anima_client", path)
        if spec is None or spec.loader is None:
            raise ValueError("ANIMA client unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        client = module.AnimaHouseholdClient(
            self.endpoint, str(self.token_file), timeout=2.0
        )
        client.worker_id = self.worker_id
        return client


def _identity_observation(speaker_context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate SENTRY's bounded camera result into an ANIMA observation.

    ANIMA still maps the profile server-side.  The profile id is an observed
    SENTRY profile reference, never an authoritative household principal.
    """
    if not isinstance(speaker_context, dict):
        return None
    status = str(speaker_context.get("status", "unavailable"))
    recognized = status == "recognized"
    observation: dict[str, Any] = {
        "endpoint_id": "sentry-voice",
        "profile_state": "recognized" if recognized else status,
        "state": status,
        "local_proximity": False,
    }
    if recognized and isinstance(speaker_context.get("person_id"), str):
        observation["profile_id"] = speaker_context["person_id"]
        confidence = speaker_context.get("identity_confidence")
        if isinstance(confidence, (int, float)):
            observation["confidence"] = round(max(0.0, min(1.0, float(confidence))) * 100)
    observed_at = speaker_context.get("observed_at")
    if isinstance(observed_at, str) and observed_at:
        observation["observed_at"] = observed_at
    return observation


class ResidentAnimaTurn:
    """One direct interaction, no retries; bindings never enter model context."""

    def __init__(self) -> None:
        self.path: Path | None = None
        self.directory: tempfile.TemporaryDirectory[str] | None = None
        self.client: Any = None
        self.request_id = ""
        self.binding = ""
        self.deadline = 0.0
        self.diagnostics: dict[str, Any] = {"status": "DISABLED"}
        self._stop = threading.Event()
        self._renewal: threading.Thread | None = None
        self._lease_failed = False
        self._submitted = False

    def _diagnostic(self, stage: str, exc: Exception | None = None) -> None:
        self.diagnostics = {"status": "UNAVAILABLE", "stage": stage}
        if exc is not None:
            self.diagnostics["exception_type"] = type(exc).__name__

    def prepare(
        self,
        question: str,
        sentry_request_id: str,
        workspace: Path,
        *,
        profile_data: dict[str, Any],
        speaker_context: dict[str, Any] | None = None,
    ) -> None:
        if VOICE_SURFACE.get() != "always_on_voice":
            return
        stage = "CONFIG"
        try:
            config = AnimaConfig.load()
            if config is None:
                return
            server = profile_data.get("mcp_servers", {}).get("anima_household", {})
            filesystem = (
                profile_data.get("permissions", {})
                .get("sentry-resident", {})
                .get("filesystem", {})
            )
            protected = (config.path, config.token_file, binding_root().resolve())
            if (
                server.get("env_vars") != ["ANIMA_PREBOUND_FILE"]
                or server.get("args")
                != [str(config.client_directory / "anima_household_mcp.py")]
                or any(not filesystem_denies(filesystem, path) for path in protected)
            ):
                self._diagnostic("PROFILE_NOT_ENABLED")
                return
            config.validate_workspace(workspace)
            self.client = config.client()
            stage = "OPEN_DIRECT"
            self.deadline = time.monotonic() + TURN_SECONDS
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=TURN_SECONDS)
            opened = self.client.open_direct_interaction(
                sentry_request_id,
                "always_on_voice",
                question,
                _identity_observation(speaker_context),
            )
            if opened.get("status") != "CLAIMED":
                raise ValueError("direct interaction not claimed")
            self.request_id = str(opened["request_id"])
            self.binding = str(opened["binding"])
            if not self.request_id or not self.binding:
                raise ValueError("empty interaction")
            stage = "PROVIDER_START"
            if (
                self.client.provider_start(self.request_id, self.binding).get("status")
                != "PROVIDER_RUNNING"
            ):
                raise ValueError("provider start rejected")
            stage = "PRIVATE_BINDING"
            root = binding_root()
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = root.lstat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700
            ):
                raise ValueError("private binding directory required")
            self.directory = tempfile.TemporaryDirectory(prefix="turn-", dir=root)
            self.path = Path(self.directory.name) / "binding.json"
            value = {
                "version": 1,
                "request_id": self.request_id,
                "binding": self.binding,
                "sentry_request_id": sentry_request_id,
                "source_surface": "always_on_voice",
                "endpoint": config.endpoint,
                "token_file": str(config.token_file),
                "worker_id": config.worker_id,
                "expires_at": expires_at.isoformat(),
                "persistent_thread": True,
                "workspace_root": str(workspace.resolve()),
            }
            for path, content in (
                (self.path, value),
                (
                    self.path.with_name("metadata.json"),
                    {"version": 1, "status": "READY", "calls": 0},
                ),
            ):
                with open(
                    path,
                    "x",
                    encoding="utf-8",
                    opener=lambda p, f: os.open(p, f, 0o600),
                ) as stream:
                    json.dump(content, stream)
            self.diagnostics = {"status": "BOUND"}
        except Exception as exc:  # noqa: BLE001 - optional client failure cannot disable ordinary SENTRY
            self._diagnostic(stage, exc)
            # A known binding can be closed once; an ambiguous open is never retried.
            if self.binding:
                self._submit("UNKNOWN_RESULT", None)
            self.close()

    def start_execution(self) -> None:
        if self.path is None:
            return
        self._renewal = threading.Thread(
            target=self._renew, name="sentry-anima-lease", daemon=True
        )
        self._renewal.start()

    def _renew(self) -> None:
        while not self._stop.wait(15):
            try:
                if time.monotonic() >= self.deadline - FINAL_RESERVE_SECONDS:
                    raise ValueError("binding deadline")
                if (
                    self.client.renew(self.request_id, self.binding).get("status")
                    != "RENEWED"
                ):
                    raise ValueError("lease lost")
            except Exception:  # noqa: BLE001 - any client failure revokes the household capability
                self._lease_failed = True
                self.revoke()
                return

    def revoke(self) -> None:
        if self.path is not None:
            self.path.unlink(missing_ok=True)

    def stop_execution(self) -> None:
        self._stop.set()
        if self._renewal is not None:
            self._renewal.join(timeout=3)
            if self._renewal.is_alive():
                self._lease_failed = True

    def _submit(self, status: str, response: str | None) -> None:
        if self._submitted or not self.binding:
            return
        self._submitted = True
        try:
            outcome = self.client.submit_result(
                self.request_id,
                self.binding,
                status=status,
                response=response,
                provider_ambiguous=status == "UNKNOWN_RESULT",
            )
            self.diagnostics = {
                "status": "RECORDED"
                if outcome.get("status") == "RECORDED"
                else "UNKNOWN_RESULT",
                "result_status": status,
            }
        except Exception as exc:  # noqa: BLE001 - submission ambiguity is terminal, never retried
            self.diagnostics = {
                "status": "UNKNOWN_RESULT",
                "stage": "RESULT_SUBMIT",
                "exception_type": type(exc).__name__,
            }

    def finish(self, result: dict[str, Any] | None, *, success: bool) -> None:
        self.stop_execution()
        if self.path is None:
            return
        self.revoke()
        status = "UNKNOWN_RESULT"
        answer = None
        try:
            if (
                success
                and not self._lease_failed
                and time.monotonic() < self.deadline
                and isinstance(result, dict)
            ):
                metadata = private_json(self.path.with_name("metadata.json"))
                allowed = {
                    "READY",
                    "SUCCEEDED",
                    "PARTIAL",
                    "UNKNOWN_RESULT",
                    "WAITING_CONFIRMATION",
                    "WAITING_STRONGER_AUTH",
                    "FAILED",
                    "UNAVAILABLE",
                }
                if (
                    metadata.get("version") != 1
                    or metadata.get("status") not in allowed
                    or type(metadata.get("calls")) is not int
                    or not 0 <= metadata["calls"] <= 8
                ):
                    raise ValueError("invalid tool outcome metadata")
                status = metadata["status"]
                status = (
                    "RESPONSE"
                    if status == "SUCCEEDED"
                    else "PARTIAL"
                    if status == "READY"
                    else status
                )
                raw_answer = result.get("answer")
                if isinstance(raw_answer, str) and raw_answer.strip():
                    answer = raw_answer.strip()[:4000]
                else:
                    status = "UNKNOWN_RESULT"
                if result.get("status") != "completed" and status == "RESPONSE":
                    status = "PARTIAL"
        except (OSError, ValueError, TypeError, KeyError):
            status = "UNKNOWN_RESULT"
        self._submit(status, answer if status != "UNKNOWN_RESULT" else None)

    def close(self) -> None:
        self.stop_execution()
        if self.directory is not None:
            self.directory.cleanup()
        self.path = None
        self.binding = ""

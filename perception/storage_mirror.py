"""Local SQLite recovery and Atlas snapshot mirroring for SENTRY.

The live database must remain on a filesystem local to the SENTRY host. Atlas
is used only for complete SQLite snapshot files, never as the active database.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


class StorageTopologyError(RuntimeError):
    """Raised when the configured live database is not provably local."""


class PersistenceRecoveryError(RuntimeError):
    """Raised when neither the local database nor an Atlas snapshot is usable."""


NETWORK_FILESYSTEMS = {
    "9p",
    "cifs",
    "fuse.sshfs",
    "nfs",
    "nfs4",
    "smb3",
    "sshfs",
}


@dataclass(frozen=True)
class FilesystemInfo:
    filesystem_type: str
    source: str

    @property
    def is_network_or_fuse(self) -> bool:
        return self.filesystem_type.lower() in NETWORK_FILESYSTEMS or self.filesystem_type.lower().startswith("fuse.")


@dataclass
class MirrorStatus:
    enabled: bool
    status: str
    last_successful_mirror: str | None = None
    snapshot_sha256: str | None = None
    last_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "status": self.status,
            "last_successful_mirror": self.last_successful_mirror,
            "snapshot_sha256": self.snapshot_sha256,
            "last_error": self.last_error,
        }


def filesystem_info(path: str | Path) -> FilesystemInfo:
    """Return the mount type/source for ``path`` using Linux ``findmnt``."""

    target = Path(path).expanduser()
    try:
        result = subprocess.run(
            ["findmnt", "-T", str(target), "-no", "FSTYPE,SOURCE"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StorageTopologyError(f"unable to inspect filesystem for {target}: {exc}") from exc
    if result.returncode != 0 or not result.stdout.strip():
        raise StorageTopologyError(f"unable to determine filesystem for {target}: {result.stderr.strip()}")
    fields = result.stdout.strip().split(maxsplit=1)
    if len(fields) != 2:
        raise StorageTopologyError(f"unexpected findmnt output for {target}: {result.stdout.strip()}")
    return FilesystemInfo(fields[0], fields[1])


def ensure_local_database_path(path: str | Path) -> Path:
    """Create the parent and reject network/FUSE-backed live SQLite paths."""

    resolved = Path(path).expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    info = filesystem_info(resolved.parent)
    if info.is_network_or_fuse:
        raise StorageTopologyError(
            f"live SQLite database must be local; {resolved} is on {info.filesystem_type} ({info.source})"
        )
    return resolved


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_sqlite_file(path: str | Path) -> None:
    """Run an integrity check without opening the file for writes."""

    target = Path(path).resolve()
    uri = f"file:{quote(str(target))}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    except sqlite3.Error as exc:
        raise PersistenceRecoveryError(f"unable to open SQLite snapshot {target}: {exc}") from exc
    try:
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error as exc:
            raise PersistenceRecoveryError(f"SQLite integrity check failed for {target}: {exc}") from exc
        if not result or result[0] != "ok":
            raise PersistenceRecoveryError(f"SQLite integrity check failed for {target}: {result!r}")
    finally:
        connection.close()


def restore_from_atlas(local_path: Path, atlas_path: Path) -> str:
    """Copy and validate an Atlas snapshot before publishing it locally."""

    if not atlas_path.is_file():
        raise PersistenceRecoveryError(f"Atlas snapshot not found: {atlas_path}")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{local_path.name}.restore-", suffix=".tmp", dir=local_path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(atlas_path, temporary)
        validate_sqlite_file(temporary)
        checksum = sha256_file(temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, local_path)
        return checksum
    except Exception as exc:
        if isinstance(exc, PersistenceRecoveryError):
            raise
        raise PersistenceRecoveryError(f"unable to restore Atlas snapshot {atlas_path}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def recover_local_database(local_path: Path, atlas_path: Path | None) -> dict[str, Any]:
    """Validate the local DB, or preserve/restore it from Atlas when needed."""

    if not local_path.exists():
        if atlas_path is None or not atlas_path.is_file():
            return {"recovered": False, "reason": "new_database"}
        checksum = restore_from_atlas(local_path, atlas_path)
        return {"recovered": True, "reason": "missing_local_database", "snapshot_sha256": checksum}

    try:
        validate_sqlite_file(local_path)
        return {"recovered": False, "reason": "local_database_valid"}
    except PersistenceRecoveryError as local_error:
        if atlas_path is None or not atlas_path.is_file():
            raise PersistenceRecoveryError(
                f"local database is corrupt and no usable Atlas snapshot exists: {local_error}"
            ) from local_error
        quarantine = local_path.with_name(
            f"{local_path.name}.corrupt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        )
        os.replace(local_path, quarantine)
        try:
            checksum = restore_from_atlas(local_path, atlas_path)
        except Exception as restore_error:
            raise PersistenceRecoveryError(
                f"local database quarantined at {quarantine}, Atlas restore failed: {restore_error}"
            ) from restore_error
        return {
            "recovered": True,
            "reason": "corrupt_local_database",
            "quarantine_path": str(quarantine),
            "snapshot_sha256": checksum,
        }


class AtlasSnapshotMirror:
    """Publish consistent local SQLite snapshots to an Atlas path."""

    def __init__(self, local_database_path: Path, atlas_snapshot_path: Path, interval_seconds: float = 60.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("mirror interval must be positive")
        self.local_database_path = local_database_path
        self.atlas_snapshot_path = atlas_snapshot_path
        self.interval_seconds = interval_seconds
        self.status = MirrorStatus(enabled=True, status="pending")
        self._last_attempt_monotonic: float | None = None
        self.manifest_path = atlas_snapshot_path.with_name(atlas_snapshot_path.name + ".manifest.json")
        self._load_manifest()

    def _load_manifest(self) -> None:
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if manifest.get("snapshot_filename") != self.atlas_snapshot_path.name:
                return
            if not self.atlas_snapshot_path.is_file():
                return
            checksum = sha256_file(self.atlas_snapshot_path)
            if checksum != manifest.get("snapshot_sha256"):
                self.status = MirrorStatus(enabled=True, status="degraded", last_error="Atlas snapshot manifest checksum mismatch")
                return
            self.status = MirrorStatus(
                enabled=True,
                status="ok",
                last_successful_mirror=manifest.get("published_at"),
                snapshot_sha256=checksum,
            )
        except (OSError, ValueError, TypeError):
            return

    def should_mirror(self, now_monotonic: float, *, force: bool = False) -> bool:
        return force or self._last_attempt_monotonic is None or now_monotonic - self._last_attempt_monotonic >= self.interval_seconds

    def mirror(self, connection: sqlite3.Connection, *, force: bool = False) -> bool:
        now_monotonic = time.monotonic()
        if not self.should_mirror(now_monotonic, force=force):
            return False
        self._last_attempt_monotonic = now_monotonic
        snapshot: Path | None = None
        atlas_temporary: Path | None = None
        try:
            self.local_database_path.parent.mkdir(parents=True, exist_ok=True)
            fd, snapshot_name = tempfile.mkstemp(
                prefix=f".{self.local_database_path.name}.snapshot-",
                suffix=".tmp",
                dir=self.local_database_path.parent,
            )
            os.close(fd)
            snapshot = Path(snapshot_name)
            snapshot_connection = sqlite3.connect(snapshot)
            try:
                connection.backup(snapshot_connection)
            finally:
                snapshot_connection.close()
            validate_sqlite_file(snapshot)
            checksum = sha256_file(snapshot)

            self.atlas_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            fd, atlas_name = tempfile.mkstemp(
                prefix=f".{self.atlas_snapshot_path.name}.",
                suffix=".tmp",
                dir=self.atlas_snapshot_path.parent,
            )
            os.close(fd)
            atlas_temporary = Path(atlas_name)
            shutil.copyfile(snapshot, atlas_temporary)
            with atlas_temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            if sha256_file(atlas_temporary) != checksum:
                raise PersistenceRecoveryError("Atlas snapshot checksum changed during publication")
            os.replace(atlas_temporary, self.atlas_snapshot_path)
            published_at = datetime.now(timezone.utc).isoformat()
            manifest = json.dumps(
                {
                    "format_version": 1,
                    "snapshot_filename": self.atlas_snapshot_path.name,
                    "snapshot_sha256": checksum,
                    "published_at": published_at,
                },
                sort_keys=True,
            ).encode("utf-8")
            fd, manifest_name = tempfile.mkstemp(
                prefix=f".{self.manifest_path.name}.",
                suffix=".tmp",
                dir=self.manifest_path.parent,
            )
            os.close(fd)
            manifest_temporary = Path(manifest_name)
            try:
                manifest_temporary.write_bytes(manifest)
                with manifest_temporary.open("rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(manifest_temporary, self.manifest_path)
            finally:
                manifest_temporary.unlink(missing_ok=True)
            self.status = MirrorStatus(
                enabled=True,
                status="ok",
                last_successful_mirror=published_at,
                snapshot_sha256=checksum,
            )
            return True
        except Exception as exc:  # Atlas outage must not break local perception.
            self.status.last_error = f"{type(exc).__name__}: {exc}"
            self.status.status = "degraded"
            return False
        finally:
            if snapshot is not None:
                snapshot.unlink(missing_ok=True)
            if atlas_temporary is not None:
                atlas_temporary.unlink(missing_ok=True)

"""Safe, bounded read access to WMI packages (directories or ZIP archives).

Nothing is ever extracted to disk. Archive member names are checked before
use; symlinks are rejected in both containers.
"""

from __future__ import annotations

import os
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .constants import MANIFEST_NAME
from .report import Report

PORTABLE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$", re.IGNORECASE)
MAX_PATH_LENGTH = 240


@dataclass
class Limits:
    max_entries: int = 10_000
    max_manifest_bytes: int = 8 * 1024**2
    max_file_bytes: int = 2 * 1024**3
    max_total_bytes: int = 16 * 1024**3
    max_pixels: int = 1 << 28
    max_compression_ratio: float = 1000.0


class PackageError(Exception):
    def __init__(self, code: str, message: str, file: str | None = None):
        super().__init__(message)
        self.code = code
        self.file = file


def unsafe_reason(name: str) -> str | None:
    """Why an archive member name is unsafe to resolve, or None if safe."""
    if not name:
        return "empty name"
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        return "contains control characters"
    if "\\" in name:
        return "contains a backslash"
    if name.startswith("/"):
        return "is an absolute path"
    if re.match(r"^[A-Za-z]:", name) or ":" in name:
        return "contains a drive letter or colon"
    parts = name.rstrip("/").split("/")
    if any(p == "" for p in parts):
        return "contains an empty path segment"
    if any(p in (".", "..") for p in parts):
        return "contains '.' or '..' segments"
    return None


def portability_problem(path: str) -> str | None:
    """Why a referenced path is not portable, or None if it is."""
    if unsafe_reason(path):
        return unsafe_reason(path)
    if len(path) > MAX_PATH_LENGTH:
        return f"is longer than {MAX_PATH_LENGTH} characters"
    if path.endswith("/"):
        return "names a directory"
    for seg in path.split("/"):
        if not PORTABLE_SEGMENT.match(seg):
            return f"segment {seg!r} must match [A-Za-z0-9][A-Za-z0-9._-]*"
        if seg.endswith("."):
            return f"segment {seg!r} ends with a dot"
        if WINDOWS_RESERVED.match(seg):
            return f"segment {seg!r} is a reserved device name on Windows"
    return None


class PackageSource:
    kind = "abstract"

    def files(self) -> list[str]:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        return path in self._index

    def size(self, path: str) -> int:
        raise NotImplementedError

    def read(self, path: str, max_bytes: int) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass


class DirectorySource(PackageSource):
    kind = "directory"

    def __init__(self, root: Path, limits: Limits, report: Report):
        self.root = root.resolve()
        self.limits = limits
        self._index: dict[str, int] = {}
        self._scan(report)

    def _scan(self, report: Report) -> None:
        count = 0
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            base = Path(dirpath)
            for d in list(dirnames):
                full = base / d
                if _is_link(full):
                    rel = full.relative_to(self.root).as_posix()
                    report.error("package.symlink", f"'{rel}' is a symlink or junction; links are not allowed in packages", file=rel)
                    dirnames.remove(d)
            dirnames.sort()
            for f in sorted(filenames):
                full = base / f
                rel = full.relative_to(self.root).as_posix()
                if _is_link(full):
                    report.error("package.symlink", f"'{rel}' is a symlink; links are not allowed in packages", file=rel)
                    continue
                count += 1
                if count > self.limits.max_entries:
                    raise PackageError("limit.entries", f"package has more than {self.limits.max_entries} files")
                self._index[rel] = full.stat().st_size

    def files(self) -> list[str]:
        return sorted(self._index)

    def size(self, path: str) -> int:
        return self._index[path]

    def read(self, path: str, max_bytes: int) -> bytes:
        if path not in self._index:
            raise PackageError("file.missing", f"'{path}' does not exist in the package", file=path)
        full = self.root.joinpath(*path.split("/"))
        if _is_link(full) or not full.resolve().is_relative_to(self.root):
            raise PackageError("package.symlink", f"'{path}' resolves outside the package", file=path)
        size = full.stat().st_size
        if size > max_bytes:
            raise PackageError("limit.file_size", f"'{path}' is {size} bytes, above the {max_bytes}-byte limit", file=path)
        with open(full, "rb") as fh:
            data = fh.read(size)
            grew = fh.read(1)
        if grew or len(data) > max_bytes:
            raise PackageError("limit.file_size", f"'{path}' exceeds the {max_bytes}-byte limit", file=path)
        return data


class ZipSource(PackageSource):
    kind = "zip"

    def __init__(self, path: Path, limits: Limits, report: Report):
        self.limits = limits
        try:
            self.zf = zipfile.ZipFile(path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            raise PackageError("archive.invalid", f"not a readable ZIP archive: {exc}") from exc
        self._index: dict[str, zipfile.ZipInfo] = {}
        self._scan(report)

    def _scan(self, report: Report) -> None:
        infos = self.zf.infolist()
        if len(infos) > self.limits.max_entries:
            raise PackageError("limit.entries", f"archive has {len(infos)} entries, above the {self.limits.max_entries} limit")
        total = 0
        folded: dict[str, str] = {}
        for info in infos:
            name = info.filename
            reason = unsafe_reason(name)
            if reason:
                report.error("archive.unsafe_path", f"archive entry {name!r} {reason}; it will not be read", file=name)
                continue
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                report.error("archive.symlink", f"archive entry {name!r} is a symlink; links are not allowed", file=name)
                continue
            if info.flag_bits & 0x1:
                report.error("archive.encrypted", f"archive entry {name!r} is encrypted", file=name)
                continue
            if info.is_dir():
                continue
            if name in self._index:
                report.error("archive.duplicate_entry", f"archive contains more than one entry named {name!r}", file=name)
                continue
            key = name.casefold()
            if key in folded:
                report.error(
                    "path.case_collision",
                    f"archive entries {folded[key]!r} and {name!r} differ only by case",
                    file=name,
                )
                continue
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                report.error(
                    "archive.compression",
                    f"archive entry {name!r} uses compression method {info.compress_type}; only stored (0) and deflate (8) are portable",
                    file=name,
                )
                continue
            if info.compress_size and info.file_size / max(info.compress_size, 1) > self.limits.max_compression_ratio:
                report.error(
                    "limit.compression_ratio",
                    f"archive entry {name!r} expands {info.file_size / info.compress_size:.0f}x, above the limit",
                    file=name,
                )
                continue
            total += info.file_size
            if total > self.limits.max_total_bytes:
                raise PackageError("limit.total_size", f"archive expands to more than {self.limits.max_total_bytes} bytes")
            folded[key] = name
            self._index[name] = info

    def files(self) -> list[str]:
        return sorted(self._index)

    def size(self, path: str) -> int:
        return self._index[path].file_size

    def read(self, path: str, max_bytes: int) -> bytes:
        info = self._index.get(path)
        if info is None:
            raise PackageError("file.missing", f"'{path}' does not exist in the archive", file=path)
        if info.file_size > max_bytes:
            raise PackageError("limit.file_size", f"'{path}' is {info.file_size} bytes, above the {max_bytes}-byte limit", file=path)
        try:
            with self.zf.open(info) as fh:
                data = fh.read(info.file_size + 1)
        except (zipfile.BadZipFile, OSError, EOFError) as exc:
            raise PackageError("archive.corrupt", f"'{path}' could not be read: {exc}", file=path) from exc
        if len(data) > max_bytes or len(data) != info.file_size:
            raise PackageError("archive.corrupt", f"'{path}' size does not match its archive header", file=path)
        return data

    def close(self) -> None:
        self.zf.close()


def _is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if hasattr(os.path, "isjunction") and os.path.isjunction(path):
            return True
        st = os.lstat(path)
        attrs = getattr(st, "st_file_attributes", 0)
        return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except OSError:
        return False


def open_package(target, limits: Limits, report: Report) -> PackageSource:
    path = Path(target)
    if path.is_dir():
        report.container = "directory"
        return DirectorySource(path, limits, report)
    if path.is_file():
        report.container = "zip"
        return ZipSource(path, limits, report)
    raise PackageError("package.not_found", f"'{target}' is neither a directory nor a file")


def find_nested_manifest(source: PackageSource) -> str | None:
    for name in source.files():
        parts = name.split("/")
        if len(parts) == 2 and parts[1] == MANIFEST_NAME:
            return name
    return None

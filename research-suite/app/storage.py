"""
Project storage: one JSON file per project.

Plain JSON rather than a database, for the same reason the nursery tracker in
this repo keeps its data as one JSON document: a research project is a small
object you want to be able to read, grep, diff, email to a supervisor, and
restore from a copy without any tooling. A SQLite file would be faster at a scale
this will never reach, and unreadable at the scale it will.

Writes are atomic — a temporary file in the same directory, then a rename — so an
interrupted save cannot leave a half-written project. Losing an afternoon's
screening decisions to a crash mid-write is exactly the failure a research tool
must not have.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from dataclasses import fields as dataclass_fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    Appraisal, AppraisalItem, Author, Claim, EvidenceLevel, Extraction, Project,
    StyleProfile, SupportType, TitlePage, Work, WorkType,
)

SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProjectStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.samples_dir = directory / "writing-samples"
        self.samples_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------- lifecycle

    def new_project(self, topic: str, question: str = "",
                    academic_level: str = "graduate") -> Project:
        project = Project(
            project_id=self._make_id(topic),
            topic=topic.strip(),
            question=question.strip(),
            academic_level=academic_level,
            created_at=_now(),
            updated_at=_now(),
        )
        project.title_page = TitlePage(variant="student", title=topic.strip())
        from .apa.document import default_running_head
        project.title_page.running_head = default_running_head(topic)
        self.save(project)
        return project

    def _make_id(self, topic: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40] or "project"
        candidate = slug
        # A short random suffix on collision rather than an incrementing number,
        # so two projects created from the same topic never race to the same file.
        while (self.directory / f"{candidate}.json").exists():
            candidate = f"{slug}-{secrets.token_hex(2)}"
        return candidate

    def path_for(self, project_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "", project_id)
        if not safe or safe in (".", ".."):
            raise ValueError(f"unsafe project id {project_id!r}")
        return self.directory / f"{safe}.json"

    def list_projects(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            project = payload.get("project", {})
            summaries.append({
                "project_id": project.get("project_id", path.stem),
                "topic": project.get("topic", ""),
                "question": project.get("question", ""),
                "academic_level": project.get("academic_level", ""),
                "sources": len(project.get("works", [])),
                "claims": len(project.get("claims", [])),
                "updated_at": project.get("updated_at", ""),
            })
        summaries.sort(key=lambda s: s["updated_at"], reverse=True)
        return summaries

    def load(self, project_id: str) -> Project:
        path = self.path_for(project_id)
        if not path.exists():
            raise FileNotFoundError(f"no project named {project_id!r}")
        payload = json.loads(path.read_text("utf-8"))
        return _project_from_dict(payload.get("project", {}))

    def save(self, project: Project) -> Path:
        project.updated_at = _now()
        path = self.path_for(project.project_id)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "saved_at": project.updated_at,
            "project": _to_jsonable(project),
        }
        # Atomic: write beside the target, fsync, then rename. A rename within a
        # directory is atomic on every platform that matters, so a crash leaves
        # either the old file or the new one, never a truncated one.
        handle, temporary = tempfile.mkstemp(dir=str(self.directory), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return path

    def delete(self, project_id: str) -> bool:
        path = self.path_for(project_id)
        if not path.exists():
            return False
        # Keep a copy rather than destroying work: a mis-click should not lose a
        # screened literature set.
        backup = self.directory / f"{path.stem}.deleted-{_now()[:19].replace(':', '')}.json"
        path.rename(backup)
        return True

    # -------------------------------------------------------- writing samples

    def save_sample(self, name: str, text: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "-", name)[:80] or "sample"
        path = self.samples_dir / f"{safe}.txt"
        path.write_text(text, "utf-8")
        return path

    def list_samples(self) -> list[dict[str, Any]]:
        out = []
        for path in sorted(self.samples_dir.glob("*.txt")):
            try:
                text = path.read_text("utf-8")
            except OSError:
                continue
            out.append({"name": path.stem, "words": len(text.split()),
                        "characters": len(text)})
        return out

    def read_samples(self) -> list[str]:
        samples = []
        for path in sorted(self.samples_dir.glob("*.txt")):
            try:
                samples.append(path.read_text("utf-8"))
            except OSError:
                continue
        return samples

    def delete_sample(self, name: str) -> bool:
        safe = re.sub(r"[^A-Za-z0-9._-]", "-", name)[:80]
        path = self.samples_dir / f"{safe}.txt"
        if path.exists():
            path.unlink()
            return True
        return False


# ------------------------------------------------------------ serialisation

_ENUMS = {"work_type": WorkType, "level": EvidenceLevel, "support_type": SupportType}


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_jsonable(getattr(value, f.name))
                for f in dataclass_fields(value)}
    if isinstance(value, (WorkType, EvidenceLevel, SupportType)):
        return value.value
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _fill(cls, payload: dict[str, Any]):
    """Build a dataclass from a dict, tolerating fields it does not know.

    Forward-compatible on purpose: a project file written by a later version
    opens in an earlier one with the unknown fields dropped rather than raising.
    """
    if not isinstance(payload, dict):
        return cls()
    kwargs: dict[str, Any] = {}
    for field in dataclass_fields(cls):
        if field.name not in payload:
            continue
        raw = payload[field.name]
        if field.name in _ENUMS:
            try:
                kwargs[field.name] = _ENUMS[field.name](raw)
            except (ValueError, TypeError):
                pass
            continue
        kwargs[field.name] = raw
    return cls(**kwargs)


def _project_from_dict(payload: dict[str, Any]) -> Project:
    project = _fill(Project, {
        k: v for k, v in payload.items()
        if k not in ("works", "appraisals", "extractions", "claims", "style",
                     "title_page")
    })
    project.title_page = _fill(TitlePage, payload.get("title_page") or {})
    project.style = _fill(StyleProfile, payload.get("style") or {})

    project.works = []
    for raw in payload.get("works") or []:
        work = _fill(Work, {k: v for k, v in raw.items()
                            if k not in ("authors", "editors")})
        work.authors = [_fill(Author, a) for a in raw.get("authors") or []]
        work.editors = [_fill(Author, a) for a in raw.get("editors") or []]
        work.ensure_key()
        project.works.append(work)

    project.appraisals = []
    for raw in payload.get("appraisals") or []:
        appraisal = _fill(Appraisal, {k: v for k, v in raw.items() if k != "items"})
        appraisal.items = [_fill(AppraisalItem, i) for i in raw.get("items") or []]
        project.appraisals.append(appraisal)

    project.extractions = [_fill(Extraction, e)
                           for e in payload.get("extractions") or []]
    project.claims = [_fill(Claim, c) for c in payload.get("claims") or []]
    return project

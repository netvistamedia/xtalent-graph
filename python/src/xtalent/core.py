"""Core data models for the xTalent Graph protocol.

This module is authoritative for two protocol documents:

* ``XTalentCV``   — the immutable CV, serialized as Markdown with YAML frontmatter
  (schema ``xtalent/cv/v1``).
* ``ProfileRoot`` — the mutable profile root, serialized as JSON
  (schema ``xtalent/profile-root/v1``).

Both are Pydantic v2 models. All other modules (publish, search, api) depend on
these types and must not re-define protocol fields.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

CV_SCHEMA_ID: Literal["xtalent/cv/v1"] = "xtalent/cv/v1"
PROFILE_ROOT_SCHEMA_ID: Literal["xtalent/profile-root/v1"] = "xtalent/profile-root/v1"

_HANDLE_RE = re.compile(r"^@[\w]+$")
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<frontmatter>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp.

    Preferred over :func:`datetime.utcnow`, which is deprecated in Python 3.12+.
    """
    return datetime.now(UTC)


class Status(str, Enum):
    """High-level employment status signal on the profile."""

    OPEN = "open"
    PASSIVE = "passive"
    CLOSED = "closed"
    HIRED = "hired"
    INACTIVE = "inactive"


class Availability(str, Enum):
    """How actively the holder is entertaining new opportunities."""

    LOOKING = "looking"
    NOT_LOOKING = "not_looking"
    NEXT_AVAILABLE = "next_available"


class XTalentCV(BaseModel):
    """An xTalent CV document.

    Serialized as a Markdown file with YAML frontmatter (``cv-vN.md``). Once a
    version is pinned and referenced by a profile root, its bytes must not
    change — corrections are issued as a new version.

    Required body sections (Markdown, in order):

    * ``## Summary``
    * ``## Experience``
    * ``## Projects``

    Optional:

    * ``## Endorsements``
    """

    model_config = {"extra": "forbid", "use_enum_values": False}

    schema_id: Literal["xtalent/cv/v1"] = Field(default=CV_SCHEMA_ID, alias="schema")
    handle: str = Field(pattern=r"^@[\w]+$", description="Unique @handle.")
    version: int = Field(default=1, ge=1)
    last_updated: datetime = Field(default_factory=_utcnow)
    status: Status = Status.OPEN
    availability: Availability = Availability.LOOKING
    next_available_date: datetime | None = None
    expires_at: datetime | None = None
    freshness_score: int = Field(default=80, ge=0, le=100)
    salary_expectation: dict[str, Any] | None = None
    location_prefs: list[str] = Field(default_factory=list)
    skills_matrix: list[dict[str, Any]] = Field(default_factory=list)
    ai_twin_enabled: bool = True
    privacy: dict[str, Any] = Field(default_factory=dict)

    full_name: str
    title: str
    summary: str
    experience: str
    projects: str
    endorsements: str = ""

    @model_validator(mode="after")
    def _check_handle(self) -> XTalentCV:
        if not _HANDLE_RE.match(self.handle):
            raise ValueError(f"invalid handle: {self.handle!r}")
        return self

    @model_validator(mode="after")
    def _check_next_available(self) -> XTalentCV:
        if self.availability == Availability.NEXT_AVAILABLE and self.next_available_date is None:
            raise ValueError(
                "next_available_date is required when availability == next_available"
            )
        return self

    # ---------------------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------------------

    def _frontmatter_dict(self) -> dict[str, Any]:
        """Frontmatter payload, ordered for human readability."""
        data = self.model_dump(mode="json", by_alias=True, exclude_none=False)
        body_keys = ("full_name", "title", "summary", "experience", "projects", "endorsements")
        return {k: v for k, v in data.items() if k not in body_keys}

    def to_markdown(self) -> str:
        """Serialize to the canonical ``cv-vN.md`` form.

        The output is a single UTF-8 Markdown document with YAML frontmatter
        delimited by ``---``. Field order is stable: serializing the same model
        twice produces byte-identical output (and therefore the same CID).
        """
        frontmatter = yaml.safe_dump(
            self._frontmatter_dict(),
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).rstrip()

        body_parts = [
            f"# {self.full_name}",
            "",
            f"_{self.title}_",
            "",
            "## Summary",
            self.summary.strip(),
            "",
            "## Experience",
            self.experience.strip(),
            "",
            "## Projects",
            self.projects.strip(),
        ]
        if self.endorsements.strip():
            body_parts += ["", "## Endorsements", self.endorsements.strip()]

        body = "\n".join(body_parts).rstrip() + "\n"
        return f"---\n{frontmatter}\n---\n\n{body}"

    @classmethod
    def from_markdown(cls, text: str) -> XTalentCV:
        """Parse a ``cv-vN.md`` document into an :class:`XTalentCV`.

        Raises :class:`ValueError` if the document lacks frontmatter or any
        required section.
        """
        match = _FRONTMATTER_RE.match(text)
        if not match:
            raise ValueError("document is missing YAML frontmatter delimited by '---'")
        fm = yaml.safe_load(match.group("frontmatter")) or {}
        body = match.group("body")

        sections = _parse_sections(body)
        for required in ("Summary", "Experience", "Projects"):
            if required not in sections:
                raise ValueError(f"missing required section: ## {required}")

        full_name, title = _parse_title_block(body)
        payload: dict[str, Any] = dict(fm)
        payload.update(
            full_name=full_name,
            title=title,
            summary=sections["Summary"],
            experience=sections["Experience"],
            projects=sections["Projects"],
            endorsements=sections.get("Endorsements", ""),
        )
        return cls.model_validate(payload)

    @classmethod
    def from_markdown_file(cls, path: str | Path) -> XTalentCV:
        """Convenience loader. Reads UTF-8 and delegates to :meth:`from_markdown`."""
        return cls.from_markdown(Path(path).read_text(encoding="utf-8"))

    def to_profile_root(self, latest_cid: str) -> ProfileRoot:
        """Project this CV onto a mutable profile root pointing at ``latest_cid``."""
        return ProfileRoot(
            handle=self.handle,
            latest_cid=latest_cid,
            version=self.version,
            status=self.status,
            availability=self.availability,
            next_available_date=self.next_available_date,
            freshness_score=self.freshness_score,
        )


class ProfileRoot(BaseModel):
    """Mutable pointer document. The only thing that actually changes."""

    model_config = {"extra": "forbid", "use_enum_values": False}

    schema_id: Literal["xtalent/profile-root/v1"] = Field(
        default=PROFILE_ROOT_SCHEMA_ID, alias="schema"
    )
    handle: str = Field(pattern=r"^@[\w]+$")
    latest_cid: str = Field(min_length=1)
    version: int = Field(ge=1)
    status: Status
    availability: Availability
    next_available_date: datetime | None = None
    freshness_score: int = Field(ge=0, le=100)
    updated_at: datetime = Field(default_factory=_utcnow)
    tombstoned: bool = False
    tombstone_reason: str | None = None

    def tombstone(self, reason: str | None = None) -> ProfileRoot:
        """Return a copy with ``tombstoned=True``.

        Profile roots are treated as immutable values within the process — any
        state transition produces a new root.
        """
        return self.model_copy(
            update={
                "tombstoned": True,
                "tombstone_reason": reason,
                "updated_at": _utcnow(),
            }
        )


# ---------------------------------------------------------------------------
# Markdown body parsing helpers
# ---------------------------------------------------------------------------


def _parse_sections(body: str) -> dict[str, str]:
    """Split a Markdown body into ``{section_title: content}`` entries.

    A section starts at a line matching ``## Title`` and runs until the next
    ``## `` heading (or end of document).
    """
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def _parse_title_block(body: str) -> tuple[str, str]:
    """Extract ``(full_name, title)`` from the leading ``# Name`` / ``_Title_`` block.

    Tolerates missing italics on the title line. If the body has no ``# `` heading
    at all, returns ``("", "")`` — the caller's Pydantic validation will reject
    a CV with empty ``full_name``/``title``.
    """
    full_name = ""
    title = ""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not full_name and stripped.startswith("# "):
            full_name = stripped[2:].strip()
            continue
        if full_name and not title:
            title = stripped.strip("_* ").strip()
            break
    return full_name, title

#!/usr/bin/env python3
"""Shared identity helpers for stable artwork ids and filenames.

This module provides the single source of truth for converting an
artwork's metadata (artist, title, category, variant) and its source
URL into a **stable**, **globally unique** id and filename. It is used
by:

* ``scripts/run_artvee_nightly_batch.py`` — when downloading a new
  artwork, the resulting image/metadata filenames are derived from
  ``make_stable_artwork_id(...)``.
* ``scripts/build_artvee_gallery.py`` — when emitting the web data
  layer, each record's ``id`` field is the same stable id, and the
  file paths come from ``make_image_basename(...)`` /
  ``make_metadata_basename(...)``.
* ``scripts/plan_gallery_collision_migration.py`` — to back-compute
  the new id for every pre-P4B artwork whose filename was a
  human-readable collision.

The P4B migration step is what motivates this module. Prior to P4B
the local image filename was
``<Artist>_<Title>_<category>_<variant>.jpg`` — derived purely from
human-readable strings, so two different Artvee URLs with the same
parsed title would collide on disk and last-write-wins would
overwrite the earlier image. After P4B, the filename gains a
``short hash of the source URL`` suffix:

    <norm_artist>_<norm_title>_<norm_cat>_<variant>_<hash8>.<ext>

where ``hash8 = short_source_hash(source_url)`` is the first 8 hex
characters of ``sha1(source_url)``. This guarantees that distinct
source URLs produce distinct filenames even when the human-readable
parts match, while still being debuggable (the human parts are
preserved).

The module is pure stdlib and has no side effects. It does not read
or write any file.

Public API
----------
* ``slugify_part(text: str) -> str``
    Normalize a single human-readable part (artist or title) into a
    filesystem-safe slug. Replaces whitespace with ``_``, strips
    unsafe characters, and collapses runs of underscores.
* ``short_source_hash(source_url: str) -> str``
    Return the first 8 hex characters of ``sha1(source_url)``.
    Same source URL always returns the same hash.
* ``make_stable_artwork_id(artist, title, category, source_url, variant) -> str``
    Return the stable artwork id used as the ``id`` field in
    ``web/data/artworks.json`` and as the basename stem for images,
    metadata, and thumbnails.
* ``make_image_basename(stable_id: str, ext: str = ".jpg") -> str``
    Return the image filename, e.g. ``<stable_id>.jpg``.
* ``make_metadata_basename(stable_id: str) -> str``
    Return the metadata filename, e.g. ``<stable_id>.json``.
* ``parse_source_hash(stable_id: str) -> str | None``
    Extract the trailing ``_<hash8>`` suffix from a stable id, or
    ``None`` if the id is in the pre-P4B format. Used by the
    integrity check to distinguish migrated vs legacy records.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Final

_HASH_LEN: Final = 8
_HASH_RE: Final = re.compile(r"^[a-f0-9]{8}$")

# Pre-compiled character class: anything that is not [A-Za-z0-9._-] or a
# unicode letter/digit is treated as a separator.
_UNSAFE_RE: Final = re.compile(r"[^A-Za-z0-9._\-\u00C0-\u017F\u4e00-\u9fff]+")
_MULTI_UNDERSCORE_RE: Final = re.compile(r"_+")


def slugify_part(text: str) -> str:
    """Normalize a human-readable part into a filesystem-safe slug.

    * Convert to NFKC form to unify full-width / half-width variants.
    * Strip leading / trailing whitespace and dots.
    * Replace any non-allowed run with a single underscore.
    * Collapse repeated underscores.
    * Lowercase the result.
    """
    if text is None:
        return ""
    s = unicodedata.normalize("NFKC", str(text)).strip()
    if not s:
        return ""
    s = _UNSAFE_RE.sub("_", s)
    s = _MULTI_UNDERSCORE_RE.sub("_", s)
    s = s.strip("._-")
    return s.lower()


def short_source_hash(source_url: str) -> str:
    """Return the first 8 hex characters of ``sha1(source_url)``.

    Empty / non-string input returns the hash of the empty string,
    which is a stable value (cbf29ce484222325) but callers are
    expected to never pass an empty URL.
    """
    if not source_url:
        return ""
    h = hashlib.sha1(source_url.encode("utf-8")).hexdigest()
    return h[:_HASH_LEN]


def make_stable_artwork_id(
    artist: str,
    title: str,
    category: str,
    source_url: str,
    variant: str = "standard",
) -> str:
    """Return a stable, globally-unique artwork id.

    The id is built as
    ``<norm_artist>_<norm_title>_<norm_cat>_<variant>_<hash8>``.

    Each human-readable part is slugified. The trailing ``<hash8>``
    is the short source hash; it disambiguates when two distinct
    source URLs share the same human-readable parts.
    """
    parts = [
        slugify_part(artist),
        slugify_part(title),
        slugify_part(category),
        slugify_part(variant) or "standard",
    ]
    base = "_".join(p for p in parts if p)
    h = short_source_hash(source_url)
    if not h:
        # Caller is expected to always pass a real source_url, but
        # degrade gracefully.
        return base
    return f"{base}_{h}"


def make_image_basename(stable_id: str, ext: str = ".jpg") -> str:
    """Return the image filename, e.g. ``<stable_id>.jpg``."""
    if not ext.startswith("."):
        ext = "." + ext
    return f"{stable_id}{ext}"


def make_metadata_basename(stable_id: str) -> str:
    """Return the metadata filename, e.g. ``<stable_id>.json``."""
    return f"{stable_id}.json"


def parse_source_hash(stable_id: str) -> str | None:
    """Extract the trailing ``_<hash8>`` suffix from a stable id.

    Returns the 8-hex-char hash if the id is in the post-P4B format,
    or ``None`` if the id is in the pre-P4B ``<artist>_<title>_<cat>_<variant>``
    format.
    """
    if not stable_id:
        return None
    parts = stable_id.rsplit("_", 1)
    if len(parts) != 2:
        return None
    candidate = parts[1]
    if _HASH_RE.match(candidate):
        return candidate
    return None

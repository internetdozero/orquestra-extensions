"""Retention purging and dry-run estimation across harness session stores."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import discovery, policy
from .delete import delete_session
from .models import session_is_live


def _parse_iso(timestamp_str: str | None) -> datetime | None:
    if not timestamp_str:
        return None
    try:
        clean = timestamp_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return None


def estimate_purge(
    older_than_days: int | None = None,
    harness: str | None = None,
    session_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Estimate which sessions would be purged, respecting pin and active protection."""
    return purge_sessions(
        older_than_days=older_than_days,
        harness=harness,
        session_ids=session_ids,
        dry_run=True,
    )


def purge_sessions(
    older_than_days: int | None = None,
    harness: str | None = None,
    session_ids: list[str] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Purge expired or candidate sessions, skipping active and pinned sessions."""
    retention_policy = policy.get_retention_policy()
    default_ttl = retention_policy.get("defaultTtlDays", 30)
    overrides = retention_policy.get("harnessOverrides", {})

    cutoff_days = older_than_days if older_than_days is not None else default_ttl
    now = datetime.now(timezone.utc)

    adapters = (
        [discovery.get_adapter(harness)]
        if harness
        else list(discovery.adapters_for())
    )
    pins = policy.get_pins()

    candidates: list[dict[str, Any]] = []
    skipped_pins = 0
    skipped_active = 0
    total_reclaimed_bytes = 0

    target_id_set = set(session_ids) if session_ids else None

    for adapter in adapters:
        if not adapter.available():
            continue
        effective_ttl = overrides.get(adapter.id, cutoff_days)
        threshold = now - timedelta(days=effective_ttl)

        for summary in adapter.list_sessions(limit=200):
            sid = summary.session_id
            if target_id_set is not None and sid not in target_id_set:
                continue

            # Check age if not explicitly targeted by session_ids
            if target_id_set is None and summary.updated_at:
                dt = _parse_iso(summary.updated_at)
                if dt and dt > threshold:
                    continue

            # Check pin protection
            if (adapter.id, sid) in pins:
                skipped_pins += 1
                continue

            # Check active protection
            if session_is_live(summary):
                skipped_active += 1
                continue

            # Candidate for purge
            if dry_run:
                est_bytes = 0
                if hasattr(adapter, "_path_for"):
                    p = adapter._path_for(sid)
                    if p and p.exists():
                        est_bytes = (
                            p.stat().st_size
                            if p.is_file()
                            else sum(
                                f.stat().st_size
                                for f in p.glob("**/*")
                                if f.is_file()
                            )
                        )
                total_reclaimed_bytes += est_bytes
                candidates.append(
                    {
                        "harness": adapter.id,
                        "session_id": sid,
                        "title": summary.title,
                        "updated_at": summary.updated_at,
                        "estimated_bytes": est_bytes,
                    }
                )
            else:
                try:
                    res = delete_session(adapter.id, sid, force=False)
                    reclaimed = res.get("reclaimed_bytes", 0)
                    total_reclaimed_bytes += reclaimed
                    candidates.append(
                        {
                            "harness": adapter.id,
                            "session_id": sid,
                            "reclaimed_bytes": reclaimed,
                        }
                    )
                except Exception:
                    continue

    return {
        "dry_run": dry_run,
        "candidates_count": len(candidates),
        "reclaimed_bytes": total_reclaimed_bytes,
        "skipped_pins_count": skipped_pins,
        "skipped_active_count": skipped_active,
        "sessions": candidates,
    }


__all__ = ["estimate_purge", "purge_sessions"]

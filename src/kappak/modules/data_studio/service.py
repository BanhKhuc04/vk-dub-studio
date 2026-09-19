"""
Data Studio Module Service for KAPPAK.
Provides media asset management, smart collections, SHA-256 duplicate detection,
storage analytics, and 8-tier project directory tree traversal.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from kappak.core.db import db_session
from kappak.domain.asset import Asset
from kappak.modules.downloader.service import format_duration

logger = logging.getLogger(__name__)


@dataclass
class StorageOverview:
    total_assets: int
    total_bytes: int
    total_duration_sec: float
    duplicate_groups_count: int
    category_breakdown: dict[str, int]
    platform_breakdown: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        total_mb = round(self.total_bytes / (1024 * 1024), 2)
        if self.total_bytes < 1024:
            fmt = f"{self.total_bytes} B"
        elif self.total_bytes < 1024 * 1024:
            fmt = f"{round(self.total_bytes / 1024, 1)} KB"
        elif total_mb < 1024:
            fmt = f"{total_mb} MB"
        else:
            fmt = f"{round(total_mb / 1024, 2)} GB"

        return {
            "total_assets": self.total_assets,
            "total_bytes": self.total_bytes,
            "total_size_mb": total_mb,
            "total_size_formatted": fmt,
            "total_duration_sec": self.total_duration_sec,
            "formatted_duration": format_duration(self.total_duration_sec),
            "duplicate_groups_count": self.duplicate_groups_count,
            "category_breakdown": self.category_breakdown,
            "platform_breakdown": self.platform_breakdown,
        }


def get_storage_overview() -> StorageOverview:
    """Calculate aggregated storage statistics across all managed assets."""
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM assets").fetchall()

    total_assets = len(rows)
    total_bytes = sum(int(r["file_size"] or 0) for r in rows)
    total_duration_sec = sum(float(r["duration_sec"] or 0.0) for r in rows)

    category_counts: dict[str, int] = {}
    platform_counts: dict[str, int] = {}
    hash_counts: dict[str, int] = {}

    for r in rows:
        cat = r["category"] or "00_Inbox"
        category_counts[cat] = category_counts.get(cat, 0) + 1

        plat = r["platform"] or "Khác"
        platform_counts[plat] = platform_counts.get(plat, 0) + 1

        sha = r["sha256_hash"]
        if sha:
            hash_counts[sha] = hash_counts.get(sha, 0) + 1

    dup_groups = sum(1 for h, count in hash_counts.items() if count > 1)

    return StorageOverview(
        total_assets=total_assets,
        total_bytes=total_bytes,
        total_duration_sec=total_duration_sec,
        duplicate_groups_count=dup_groups,
        category_breakdown=category_counts,
        platform_breakdown=platform_counts,
    )


def list_assets(
    collection: str = "all",
    search: str = "",
    project_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    List assets with smart collection filtering and search.
    Collections:
      - 'all': All assets
      - 'video': Assets with video extensions (.mp4, .mov, .mkv, .webm)
      - 'audio': Assets with audio extensions (.mp3, .wav, .m4a, .aac)
      - 'unused': Assets with status == 'Unused'
      - 'inbox': Assets in category '00_Inbox'
      - 'final': Assets in category '07_FinalExport'
    """
    clauses = []
    params: list[Any] = []

    if search:
        clauses.append("(name LIKE ? OR creator LIKE ? OR tags LIKE ?)")
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)

    if collection == "video":
        clauses.append("(local_path LIKE '%.mp4' OR local_path LIKE '%.mov' OR local_path LIKE '%.mkv' OR local_path LIKE '%.webm')")
    elif collection == "audio":
        clauses.append("(local_path LIKE '%.mp3' OR local_path LIKE '%.wav' OR local_path LIKE '%.m4a' OR local_path LIKE '%.aac')")
    elif collection == "unused":
        clauses.append("status = 'Unused'")
    elif collection == "inbox":
        clauses.append("category = '00_Inbox'")
    elif collection == "final":
        clauses.append("category = '07_FinalExport'")

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    query = f"""
        SELECT * FROM assets
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with db_session() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "name": r["name"],
            "local_path": r["local_path"],
            "project_id": r["project_id"],
            "source_url": r["source_url"],
            "platform": r["platform"],
            "creator": r["creator"],
            "duration_sec": r["duration_sec"],
            "duration_formatted": format_duration(r["duration_sec"]),
            "resolution": r["resolution"],
            "file_size": r["file_size"],
            "file_size_mb": round((r["file_size"] or 0) / (1024 * 1024), 2),
            "sha256_hash": r["sha256_hash"],
            "sha_short": r["sha256_hash"][:8] if r["sha256_hash"] else "",
            "tags": r["tags"],
            "category": r["category"],
            "status": r["status"],
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
        })

    return results


def find_duplicate_assets() -> list[dict[str, Any]]:
    """Detect all asset groups sharing the exact same SHA-256 hash."""
    with db_session() as conn:
        dup_hashes = conn.execute(
            """
            SELECT sha256_hash, COUNT(*) as cnt, SUM(file_size) as total_size
            FROM assets
            WHERE sha256_hash != '' AND sha256_hash IS NOT NULL
            GROUP BY sha256_hash
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            """
        ).fetchall()

        groups = []
        for h in dup_hashes:
            sha = h["sha256_hash"]
            items = conn.execute(
                "SELECT * FROM assets WHERE sha256_hash = ? ORDER BY created_at ASC",
                (sha,),
            ).fetchall()
            item_dicts = []
            for it in items:
                item_dicts.append({
                    "id": it["id"],
                    "name": it["name"],
                    "local_path": it["local_path"],
                    "platform": it["platform"],
                    "file_size": it["file_size"],
                    "file_size_mb": round((it["file_size"] or 0) / (1024 * 1024), 2),
                    "duration_sec": it["duration_sec"],
                    "category": it["category"],
                    "created_at": str(it["created_at"]),
                })
            groups.append({
                "sha256_hash": sha,
                "sha_short": sha[:8],
                "count": h["cnt"],
                "wasted_bytes": (h["cnt"] - 1) * (items[0]["file_size"] or 0),
                "wasted_mb": round(((h["cnt"] - 1) * (items[0]["file_size"] or 0)) / (1024 * 1024), 2),
                "items": item_dicts,
            })

    return groups


def delete_asset(asset_id: str, delete_file: bool = False) -> bool:
    """Delete an asset record, optionally deleting its local file on disk."""
    with db_session() as conn:
        row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if not row:
            return False

        file_path = Path(row["local_path"]) if row["local_path"] else None
        conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))

    if delete_file and file_path and file_path.is_file():
        try:
            # Check if other assets reference the exact same file before deleting
            with db_session() as conn:
                other = conn.execute(
                    "SELECT COUNT(*) as c FROM assets WHERE local_path = ?", (str(file_path),)
                ).fetchone()
                if other and other["c"] == 0:
                    file_path.unlink(missing_ok=True)
        except Exception as err:
            logger.warning("Could not delete physical file %s: %s", file_path, err)

    return True


def get_project_folder_tree(project_root: Path | str) -> dict[str, Any]:
    """Inspect and return the 8-tier folder structure of a KAPPAK project."""
    root = Path(project_root)
    if not root.is_dir():
        return {"name": root.name, "exists": False, "tiers": []}

    tiers = []
    expected_tiers = [
        "00_Inbox",
        "01_RawFootage",
        "02_AudioVoice",
        "03_Subtitles",
        "04_MasksBlurs",
        "05_BrollAssets",
        "06_ProjectsDrafts",
        "07_FinalExport",
    ]

    for tier_name in expected_tiers:
        tier_dir = root / tier_name
        file_list = []
        if tier_dir.is_dir():
            for f in tier_dir.iterdir():
                if f.is_file():
                    file_list.append({
                        "name": f.name,
                        "size_bytes": f.stat().st_size,
                        "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                        "suffix": f.suffix.lower(),
                    })
        tiers.append({
            "tier": tier_name,
            "exists": tier_dir.is_dir(),
            "file_count": len(file_list),
            "files": file_list[:20],  # cap for preview
        })

    return {
        "name": root.name,
        "path": str(root),
        "exists": True,
        "tiers": tiers,
    }

from datetime import UTC, datetime
from pathlib import Path

from vkdub.services.usage_service import UsageLedger


class TTSUsage:
    """Separate numeric character accounting; never infer a price or free request."""

    def __init__(self, path: Path | None = None) -> None:
        self.ledger = UsageLedger(path)
        with self.ledger.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS tts_usage (id INTEGER PRIMARY KEY, "
                "month TEXT NOT NULL, characters INTEGER NOT NULL, status TEXT NOT NULL)"
            )

    def begin(self, characters: int) -> int:
        with self.ledger.connect() as db:
            cursor = db.execute(
                "INSERT INTO tts_usage(month, characters, status) VALUES (?, ?, 'unknown')",
                (datetime.now(UTC).strftime("%Y-%m"), characters),
            )
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def finish(self, identifier: int) -> None:
        with self.ledger.connect() as db:
            db.execute("UPDATE tts_usage SET status='received' WHERE id=?", (identifier,))

    def monthly(self) -> tuple[int, int, int]:
        with self.ledger.connect() as db:
            row = db.execute(
                "SELECT count(*), coalesce(sum(characters),0), "
                "coalesce(sum(status='unknown'),0) FROM tts_usage WHERE month=?",
                (datetime.now(UTC).strftime("%Y-%m"),),
            ).fetchone()
        return int(row[0]), int(row[1]), int(row[2])

    def reset(self) -> None:
        with self.ledger.connect() as db:
            db.execute("DELETE FROM tts_usage")

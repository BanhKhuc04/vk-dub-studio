import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vkdub.services.cost_service import estimate_usd, load_pricing
from vkdub.utils.paths import data_root


class UsageLedger:
    """Only numeric accounting data; never credentials, transcripts, or response bodies."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or data_root() / "usage.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY, month TEXT NOT NULL, model TEXT NOT NULL,
                input_tokens INTEGER, output_tokens INTEGER, usd REAL,
                status TEXT NOT NULL DEFAULT 'unknown')""")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def begin(self, model: str) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO usage (month, model) VALUES (?, ?)",
                (datetime.now(UTC).strftime("%Y-%m"), model),
            )
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def finish(self, identifier: int, incoming: int, outgoing: int, usd: float) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE usage SET input_tokens=?, output_tokens=?, usd=?, "
                "status='reported' WHERE id=?",
                (incoming, outgoing, usd, identifier),
            )

    def rejected(self, identifier: int) -> None:
        with self.connect() as db:
            db.execute("UPDATE usage SET status='rejected' WHERE id=?", (identifier,))

    def monthly(self, month: str | None = None) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                """SELECT count(*), coalesce(sum(input_tokens),0), coalesce(sum(output_tokens),0),
                coalesce(sum(usd),0), coalesce(sum(status='unknown'),0) FROM usage WHERE month=?""",
                (month or datetime.now(UTC).strftime("%Y-%m"),),
            ).fetchone()
        return dict(
            zip(("requests", "input_tokens", "output_tokens", "usd", "unknown"), row, strict=True)
        )

    def reset(self) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM usage")


class UsageRecorder:
    def __init__(self, ledger: UsageLedger) -> None:
        self.ledger = ledger
        self.prices = load_pricing()
        self.models: dict[int, str] = {}

    def begin(self, model: str) -> int:
        identifier = self.ledger.begin(model)
        self.models[identifier] = model
        return identifier

    def response(self, identifier: int, data: Any, status: int) -> None:
        if 400 <= status < 500:
            self.ledger.rejected(identifier)
            return
        usage = data.get("usageMetadata") if isinstance(data, dict) else None
        if not isinstance(usage, dict):
            return
        values = [
            usage.get("promptTokenCount"),
            usage.get("candidatesTokenCount"),
            usage.get("thoughtsTokenCount", 0),
        ]
        if any(type(v) is not int or v < 0 for v in values):
            return
        incoming, outgoing, thoughts = values
        try:
            prices = load_pricing(self.models.get(identifier, ""))
        except ValueError:
            return  # Unknown model prices must never be replaced with another model's rate.
        self.ledger.finish(
            identifier,
            incoming,
            outgoing + thoughts,
            estimate_usd(incoming, outgoing + thoughts, prices),
        )

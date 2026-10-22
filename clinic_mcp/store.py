"""In-memory clinic store loaded from the JSON files and reset at the start of every run."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Store:
    data_dir: Path
    clinic: dict = field(default_factory=dict)
    patients: dict[str, dict] = field(default_factory=dict)
    medications: list[dict] = field(default_factory=list)
    appointments: list[dict] = field(default_factory=list)
    refill_requests: list[dict] = field(default_factory=list)
    routes: list[dict] = field(default_factory=list)
    flags: list[dict] = field(default_factory=list)
    drafts: list[dict] = field(default_factory=list)
    tokens: dict[str, dict] = field(default_factory=dict)
    # Message receipt time; set per message so "today 9:00" can be refused once it has passed.
    now: datetime | None = None
    _source: dict = field(default_factory=dict, repr=False)

    @property
    def today(self) -> date:
        return date.fromisoformat(self.clinic["today"])

    def reset(self) -> None:
        src = copy.deepcopy(self._source)
        self.clinic = src["clinic"]
        self.patients = {p["id"]: p for p in src["patients"]}
        self.medications = src["medications"]
        self.appointments = src["appointments"]
        self.refill_requests, self.routes, self.flags, self.drafts = [], [], [], []
        self.tokens = {}
        self.now = None

    def meds_for(self, patient_id: str) -> list[dict]:
        return [m for m in self.medications if m["patient_id"] == patient_id]


def load_store(data_dir: Path = DATA_DIR) -> Store:
    data_dir = Path(data_dir)
    source = {
        name: json.loads((data_dir / f"{name}.json").read_text())
        for name in ("clinic", "patients", "medications", "appointments")
    }
    store = Store(data_dir=data_dir, _source=source)
    store.reset()
    return store

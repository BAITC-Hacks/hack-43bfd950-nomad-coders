import os
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database: Path
    demo_enabled: bool
    frontend_dist: Path

    @classmethod
    def from_env(cls):
        return cls(
            database=Path(os.getenv('NOMAD_DB', str(PROJECT / 'runtime' / 'nomad.sqlite3'))),
            demo_enabled=os.getenv('NOMAD_DEMO', '0') == '1',
            frontend_dist=PROJECT / 'frontend' / 'dist',
        )

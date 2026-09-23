import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database: Path
    demo_enabled: bool
    frontend_dist: Path
    database_url: str | None = field(default=None, repr=False)
    public_demo: bool = False

    def __post_init__(self):
        if self.public_demo and (not self.demo_enabled or not self.database_url):
            raise ValueError('Публичное демо требует NOMAD_DEMO=1 и DATABASE_URL для постоянного хранения')

    @classmethod
    def from_env(cls):
        return cls(
            database=Path(os.getenv('NOMAD_DB', str(PROJECT / 'runtime' / 'nomad.sqlite3'))),
            demo_enabled=os.getenv('NOMAD_DEMO', '0') == '1',
            frontend_dist=PROJECT / 'frontend' / 'dist',
            database_url=os.getenv('DATABASE_URL') or None,
            public_demo=os.getenv('NOMAD_PUBLIC_DEMO', '0') == '1',
        )

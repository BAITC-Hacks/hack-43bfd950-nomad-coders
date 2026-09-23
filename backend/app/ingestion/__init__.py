"""Known Excel layout adapters. Never modify source workbooks."""
from dataclasses import dataclass
from app.contracts import NormalizedDataset, Supplier


@dataclass(frozen=True)
class SourceWorkbook:
    filename: str
    content: bytes


def import_workbooks(files: list[SourceWorkbook], supplier: Supplier) -> NormalizedDataset:
    raise NotImplementedError('Импорт Excel ещё не подключён')

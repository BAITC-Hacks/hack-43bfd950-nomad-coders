"""Known Excel layout adapters. Never modify source workbooks."""
from dataclasses import dataclass
from app.contracts import NormalizedDataset, Supplier


@dataclass(frozen=True)
class SourceWorkbook:
    filename: str
    content: bytes


class ImportFailure(ValueError):
    pass


def import_workbooks(files: list[SourceWorkbook], supplier: Supplier) -> NormalizedDataset:
    from .excel import import_known_workbooks
    return import_known_workbooks(files, supplier)

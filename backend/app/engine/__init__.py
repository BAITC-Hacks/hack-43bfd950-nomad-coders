"""Pure calculation boundary; implementation belongs to the backend captain."""
from app.contracts import CalculationSettings, EngineOutput, NormalizedDataset


def calculate(dataset: NormalizedDataset, settings: CalculationSettings) -> EngineOutput:
    raise NotImplementedError('Реальный расчёт ещё не подключён')

"""Pure calculation boundary; implementation belongs to the backend captain."""
from app.contracts import CalculationSettings, EngineOutput, NormalizedDataset


def calculate(dataset: NormalizedDataset, settings: CalculationSettings) -> EngineOutput:
    from .planning import plan_orders
    return plan_orders(dataset, settings)

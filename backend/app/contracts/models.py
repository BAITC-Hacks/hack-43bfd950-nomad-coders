"""Shared contract. Only the integration owner changes these models."""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Number = Annotated[float, Field(allow_inf_nan=False)]
Quantity = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Identifier = Annotated[str, Field(min_length=1, max_length=200)]
Supplier = Literal['systeme', 'iek', 'demo']


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SourceRef(Model):
    file: str
    sheet: str | None = None
    cell: str | None = None
    row: int | None = None
    note: str | None = None


class Issue(Model):
    code: str
    message: str
    severity: Literal['warning', 'blocking'] = 'warning'
    sku: str | None = None
    source: SourceRef | None = None


class ApiError(Model):
    code: str
    message: str
    details: list[Issue] = Field(default_factory=list)


class ErrorResponse(Model):
    error: ApiError


class Health(Model):
    status: Literal['ok'] = 'ok'
    version: str = '0.1.0'
    demo_enabled: bool


class Dataset(Model):
    id: Identifier
    version: Identifier
    name: str
    suppliers: list[Supplier]
    is_synthetic: bool
    created_at: datetime
    sources: list[SourceRef] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)


class Product(Model):
    sku: Identifier
    article: str
    name: str
    supplier: Supplier
    unit: str | None
    category: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)


class Transaction(Model):
    sku: str
    date: date
    document_id: str
    document_type: str
    quantity: Number | None
    unit: str | None
    warehouse: str | None
    customer_id: str | None = None
    source: SourceRef


class MonthlyObservation(Model):
    sku: str
    month: date
    quantity: Number | None
    kind: Literal['sales', 'opening_stock']
    is_complete: bool
    source: SourceRef


class StockSnapshot(Model):
    sku: str
    as_of: date
    available: Number | None
    on_hand: Number | None = None
    reserved: Number | None = None
    unit: str | None
    warehouse: str | None = None
    is_current: bool = False
    source: SourceRef


class Inbound(Model):
    sku: str
    quantity: Quantity
    arrival_date: date | None
    unit: str | None
    source: SourceRef


class SeasonalFactor(Model):
    supplier: Supplier
    month: Annotated[int, Field(ge=1, le=12)]
    factor: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    source: SourceRef


class OrderConstraint(Model):
    sku: str
    minimum: Quantity | None = None
    multiple: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    unit: str | None
    source: SourceRef


class StockoutInterval(Model):
    sku: str
    start: date
    end: date
    source: SourceRef

    @model_validator(mode='after')
    def ordered(self):
        if self.end < self.start:
            raise ValueError('Конец периода раньше начала')
        return self


class TransactionCoverage(Model):
    start: date
    end: date
    is_complete: bool
    source: SourceRef

    @model_validator(mode='after')
    def ordered(self):
        if self.end < self.start:
            raise ValueError('Конец покрытия раньше начала')
        return self


class NormalizedDataset(Model):
    dataset: Dataset
    products: list[Product]
    transactions: list[Transaction] = Field(default_factory=list)
    monthly: list[MonthlyObservation] = Field(default_factory=list)
    stocks: list[StockSnapshot] = Field(default_factory=list)
    inbound: list[Inbound] = Field(default_factory=list)
    seasonality: list[SeasonalFactor] = Field(default_factory=list)
    constraints: list[OrderConstraint] = Field(default_factory=list)
    stockouts: list[StockoutInterval] = Field(default_factory=list)
    transaction_coverage: TransactionCoverage | None = None


class PlanningOverride(Model):
    sku: str
    available_stock: Quantity | None = None
    growth_factor: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    reason: Annotated[str, Field(min_length=1, max_length=1000)]


class CalculationSettings(Model):
    as_of: date
    lead_time_days: Annotated[int, Field(ge=0, le=365)] = 14
    review_days: Annotated[int, Field(ge=1, le=365)] = 7
    buffer_days: Annotated[int, Field(ge=0, le=365)] = 7
    demand_source: Literal['transactions', 'monthly'] = 'transactions'
    category_buffer_days: dict[str, Annotated[int, Field(ge=0, le=365)]] = Field(default_factory=dict)
    overrides: list[PlanningOverride] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class HistoryPoint(Model):
    date: date
    raw: Number | None
    cleaned: Number | None
    adjusted: Number | None
    forecast: Quantity | None = None


class AnomalyDecision(Model):
    document_id: str
    date: date
    quantity: Number
    decision: Literal['excluded', 'recurring', 'review', 'retained']
    reason: str
    sources: list[SourceRef] = Field(default_factory=list)


class CalculationComponents(Model):
    daily_demand: Quantity | None
    horizon_days: int
    forecast_demand: Quantity | None
    safety_stock: Quantity | None
    available_stock: Number | None
    eligible_inbound: Quantity | None
    raw_need: Quantity | None
    minimum: Quantity | None = None
    multiple: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    growth_factor: Number | None = None
    stockout_lost_demand: Quantity | None = None


class Recommendation(Model):
    id: Identifier
    product: Product
    stock_date: date | None
    quantity: Quantity | None
    urgency: Literal['order_now', 'expedite', 'covered', 'needs_input']
    explanation: str
    demand_source: Literal['transactions', 'monthly', 'demo_fixture']
    components: CalculationComponents
    issues: list[Issue] = Field(default_factory=list)

    @model_validator(mode='after')
    def missing_is_blocked(self):
        if self.quantity is None and self.urgency != 'needs_input':
            raise ValueError('Неизвестное количество требует needs_input')
        if self.urgency == 'needs_input' and self.quantity is not None:
            raise ValueError('needs_input не должно содержать количество')
        return self


class ItemExplanation(Model):
    calculation_id: str
    dataset_version: str
    is_synthetic: bool
    recommendation: Recommendation
    history: list[HistoryPoint] = Field(default_factory=list)
    inbound: list[Inbound] = Field(default_factory=list)
    anomalies: list[AnomalyDecision] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class CalculationRequest(Model):
    dataset_id: str
    settings: CalculationSettings
    supplier: Supplier | None = None


class CalculationResult(Model):
    id: Identifier
    dataset_id: str
    dataset_version: str
    created_at: datetime
    is_synthetic: bool
    engine_version: str
    settings: CalculationSettings
    recommendations: list[Recommendation]
    issues: list[Issue] = Field(default_factory=list)


class EngineOutput(Model):
    recommendations: list[Recommendation]
    explanations: list[ItemExplanation]
    issues: list[Issue] = Field(default_factory=list)


class OrderCreate(Model):
    calculation_id: str
    supplier: Supplier
    recommendation_ids: Annotated[list[str], Field(min_length=1)]


class ManagerOverride(Model):
    recommendation_id: str
    quantity: Quantity
    reason: Annotated[str, Field(min_length=1, max_length=1000)]


class OrderPatch(Model):
    expected_revision: Annotated[int, Field(ge=1)]
    overrides: Annotated[list[ManagerOverride], Field(min_length=1)]


class OrderApproval(Model):
    expected_revision: Annotated[int, Field(ge=1)]
    confirmed: Literal[True]


class OrderLine(Model):
    recommendation_id: str
    product: Product
    recommended_quantity: Quantity
    quantity: Quantity
    override_quantity: Quantity | None = None
    override_reason: str | None = None


class OrderDraft(Model):
    id: Identifier
    calculation_id: str
    dataset_version: str
    supplier: Supplier
    is_synthetic: bool
    revision: Annotated[int, Field(ge=1)]
    status: Literal['draft', 'approved']
    approved_revision: int | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[OrderLine]

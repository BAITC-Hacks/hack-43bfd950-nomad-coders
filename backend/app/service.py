from datetime import datetime, timezone
from fractions import Fraction
from uuid import uuid4

from app import engine, ingestion
from app.api.errors import DomainError
from app.contracts import (
    CalculationResult, Dataset, ItemExplanation, NormalizedDataset, OrderDraft, OrderLine,
)
from app.demo import DEMO_DATASET, demo_bundle, demo_settings
from app.export.csv_export import export_csv
from app.storage.repository import Repository


def now():
    return datetime.now(timezone.utc)


class Service:
    def __init__(self, settings):
        self.settings = settings
        self.repo = Repository(settings.database)

    def _visible(self, model):
        if model.is_synthetic and not self.settings.demo_enabled:
            raise DomainError(404, 'DEMO_DISABLED', 'Демонстрационный режим выключен')
        return model

    def _get(self, kind, identifier, model):
        data = self.repo.get(kind, identifier)
        if data is None:
            raise DomainError(404, 'NOT_FOUND', 'Ресурс не найден')
        return self._visible(model.model_validate(data))

    def datasets(self):
        return [Dataset.model_validate(d) for d in self.repo.list('dataset')
                if self.settings.demo_enabled or not d['is_synthetic']]

    def import_dataset(self, sources, supplier):
        try:
            normalized = ingestion.import_workbooks(sources, supplier)
        except NotImplementedError:
            raise DomainError(501, 'IMPORT_NOT_IMPLEMENTED', 'Импорт Excel ещё не реализован')
        except ingestion.ImportFailure as exc:
            raise DomainError(422, 'IMPORT_FAILED', str(exc))
        self._visible(normalized.dataset)
        existing = self.repo.get('dataset', normalized.dataset.id)
        if existing:
            return Dataset.model_validate(existing)
        self.repo.save_bundle([('dataset', normalized.dataset.id, normalized.dataset),
                               ('normalized', normalized.dataset.id, normalized)], ignore=True)
        return Dataset.model_validate(self.repo.get('dataset', normalized.dataset.id))

    def calculate(self, request):
        dataset = self._get('dataset', request.dataset_id, Dataset)
        if request.supplier and request.supplier not in dataset.suppliers:
            raise DomainError(422, 'INVALID_SUPPLIER', 'Поставщик отсутствует в наборе')
        if dataset.id == DEMO_DATASET:
            if request.settings.model_dump(exclude={'assumptions'}) != demo_settings().model_dump(exclude={'assumptions'}):
                raise DomainError(501, 'DEMO_SETTINGS_FIXED', 'Этот пример использует фиксированные параметры; для пересчёта выберите набор данных движка')
            _, calculation, explanations = demo_bundle()
            calculation = calculation.model_copy(update={'id': str(uuid4()), 'created_at': now()})
        else:
            normalized = NormalizedDataset.model_validate(self.repo.get('normalized', dataset.id))
            try:
                output = engine.calculate(normalized, request.settings)
            except NotImplementedError:
                raise DomainError(501, 'ENGINE_NOT_IMPLEMENTED', 'Реальный расчёт ещё не реализован')
            except ValueError as exc:
                raise DomainError(422, 'INVALID_CALCULATION_INPUT', str(exc))
            recommendations = [r for r in output.recommendations
                               if not request.supplier or r.product.supplier == request.supplier]
            ids = {r.id for r in recommendations}
            explanations = [e for e in output.explanations if e.recommendation.id in ids]
            calculation = CalculationResult(
                id=str(uuid4()), dataset_id=dataset.id, dataset_version=dataset.version,
                created_at=now(), is_synthetic=dataset.is_synthetic, engine_version='statistical-v1',
                settings=request.settings, recommendations=recommendations, issues=output.issues)
        self._save_calculation(calculation, explanations)
        return calculation

    def _save_calculation(self, calculation, explanations):
        ids = [r.id for r in calculation.recommendations]
        if len(set(ids)) != len(ids) or sorted(e.recommendation.id for e in explanations) != sorted(ids):
            raise DomainError(422, 'INVALID_ENGINE_OUTPUT', 'Расчёт должен содержать уникальные строки и объяснение каждой строки')
        entries = [('calculation', calculation.id, calculation)]
        for explanation in explanations:
            explanation = explanation.model_copy(update={'calculation_id': calculation.id,
                'dataset_version': calculation.dataset_version, 'is_synthetic': calculation.is_synthetic})
            entries.append(('explanation', f'{calculation.id}/{explanation.recommendation.id}', explanation))
        self.repo.save_bundle(entries)

    def calculation(self, identifier):
        return self._get('calculation', identifier, CalculationResult)

    def explanation(self, calculation_id, item_id):
        return self._get('explanation', f'{calculation_id}/{item_id}', ItemExplanation)

    @staticmethod
    def _validate_quantity(quantity, recommendation):
        if quantity == 0:
            return
        minimum, multiple = recommendation.components.minimum, recommendation.components.multiple
        if minimum is not None and quantity < minimum:
            raise DomainError(422, 'BELOW_MINIMUM', 'Количество меньше минимальной отгрузки')
        if multiple is not None and Fraction(str(quantity)) % Fraction(str(multiple)) != 0:
            raise DomainError(422, 'INVALID_MULTIPLE', 'Количество должно соответствовать кратности упаковки')

    def create_order(self, request):
        calculation = self.calculation(request.calculation_id)
        ids = request.recommendation_ids
        if len(set(ids)) != len(ids):
            raise DomainError(422, 'DUPLICATE_ITEM', 'Строка заказа повторяется')
        recommendations = {r.id: r for r in calculation.recommendations}
        lines = []
        for identifier in ids:
            r = recommendations.get(identifier)
            if r is None or r.product.supplier != request.supplier:
                raise DomainError(422, 'INVALID_ITEM', 'Строка не принадлежит расчёту или поставщику')
            if r.quantity is None or not r.product.unit or any(i.severity == 'blocking' for i in r.issues):
                raise DomainError(422, 'BLOCKED_ITEM', 'Сначала устраните ограничения выбранной строки')
            self._validate_quantity(r.quantity, r)
            lines.append(OrderLine(recommendation_id=r.id, product=r.product,
                                   recommended_quantity=r.quantity, quantity=r.quantity))
        order = OrderDraft(id=str(uuid4()), calculation_id=calculation.id,
            dataset_version=calculation.dataset_version, supplier=request.supplier,
            is_synthetic=calculation.is_synthetic, revision=1, status='draft',
            created_at=now(), updated_at=now(), lines=lines)
        self.repo.create_order(order)
        return order

    def order(self, identifier):
        return self._get('order', identifier, OrderDraft)

    def _update(self, identifier, expected_revision, transform):
        def change(data):
            if data is None:
                raise DomainError(404, 'NOT_FOUND', 'Заказ не найден')
            order = self._visible(OrderDraft.model_validate(data))
            if order.revision != expected_revision:
                raise DomainError(409, 'STALE_REVISION', 'Заказ уже изменён. Загрузите актуальную версию')
            transform(order)
            order.revision += 1
            order.updated_at = now()
            if order.status == 'approved':
                order.approved_revision = order.revision
            return order
        return self.repo.mutate_order(identifier, change)

    def patch_order(self, identifier, request):
        original = self.order(identifier)
        recommendations = {r.id: r for r in self.calculation(original.calculation_id).recommendations}
        def transform(order):
            lines = {line.recommendation_id: line for line in order.lines}
            seen = set()
            for override in request.overrides:
                item = override.recommendation_id
                if item in seen or item not in lines:
                    raise DomainError(422, 'INVALID_ITEM', 'Неизвестная или повторяющаяся строка заказа')
                seen.add(item)
                if not override.reason.strip():
                    raise DomainError(422, 'REASON_REQUIRED', 'Укажите причину правки')
                self._validate_quantity(override.quantity, recommendations[item])
                lines[item].quantity = override.quantity
                lines[item].override_quantity = override.quantity
                lines[item].override_reason = override.reason.strip()
            order.status = 'draft'
            order.approved_revision = None
        return self._update(identifier, request.expected_revision, transform)

    def approve_order(self, identifier, request):
        def transform(order):
            if order.status == 'approved':
                raise DomainError(409, 'ALREADY_APPROVED', 'Эта версия уже согласована')
            order.status = 'approved'
        return self._update(identifier, request.expected_revision, transform)

    def export_order(self, identifier, revision):
        order = self.order(identifier)
        if order.revision != revision or order.status != 'approved' or order.approved_revision != revision:
            raise DomainError(409, 'APPROVAL_REQUIRED', 'Экспорт доступен только для актуальной согласованной версии')
        return export_csv(order)

    def seed_demo(self):
        if not self.settings.demo_enabled:
            raise DomainError(422, 'DEMO_DISABLED', 'Для загрузки синтетики явно включите NOMAD_DEMO=1')
        normalized, calculation, explanations = demo_bundle()
        entries = [('dataset', normalized.dataset.id, normalized.dataset),
                   ('normalized', normalized.dataset.id, normalized),
                   ('calculation', calculation.id, calculation)]
        entries.extend(('explanation', f'{calculation.id}/{e.recommendation.id}', e) for e in explanations)
        self.repo.save_bundle(entries, ignore=True)

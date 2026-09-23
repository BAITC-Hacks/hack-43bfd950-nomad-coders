from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException

from app.api.errors import DomainError
from app.config import Settings
from app.contracts import (
    CalculationRequest, CalculationResult, Dataset, ErrorResponse, Health,
    ItemExplanation, OrderApproval, OrderCreate, OrderDraft, OrderPatch, Supplier,
)
from app.ingestion import SourceWorkbook
from app.service import Service


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title='Nomad Coders — закупки', version='0.1.0', responses={
        code: {'model': ErrorResponse} for code in (404, 409, 422, 501)
    })
    service = Service(settings)
    app.state.service = service

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={'error': {
            'code': exc.code, 'message': exc.message,
            'details': [issue.model_dump(mode='json') for issue in exc.details],
        }})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={'error': {
            'code': 'VALIDATION_ERROR', 'message': 'Проверьте поля запроса',
            'details': [{'code': 'INVALID_FIELD', 'severity': 'blocking',
                         'message': '.'.join(str(p) for p in e['loc']), 'sku': None, 'source': None}
                        for e in exc.errors()],
        }})

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={'error': {
            'code': 'NOT_FOUND' if exc.status_code == 404 else 'HTTP_ERROR',
            'message': 'Ресурс не найден' if exc.status_code == 404 else 'Запрос не поддерживается',
            'details': [],
        }})

    @app.get('/api/health', response_model=Health)
    def health():
        return Health(demo_enabled=settings.demo_enabled)

    @app.get('/api/datasets', response_model=list[Dataset])
    def datasets():
        return service.datasets()

    @app.post('/api/datasets', response_model=Dataset, status_code=201)
    async def import_dataset(files: Annotated[list[UploadFile], File()], supplier: Annotated[Supplier, Form()]):
        sources = []
        total = 0
        for upload in files:
            if not upload.filename or not upload.filename.lower().endswith('.xlsx'):
                raise DomainError(422, 'INVALID_FILE', 'Разрешены только книги XLSX')
            content = await upload.read(30 * 1024 * 1024 + 1)
            total += len(content)
            if total > 30 * 1024 * 1024:
                raise DomainError(422, 'UPLOAD_TOO_LARGE', 'Общий размер файлов превышает 30 МБ')
            sources.append(SourceWorkbook(Path(upload.filename).name, content))
        return service.import_dataset(sources, supplier)

    @app.post('/api/calculations', response_model=CalculationResult, status_code=201)
    def calculate(body: CalculationRequest):
        return service.calculate(body)

    @app.get('/api/calculations/{calculation_id}', response_model=CalculationResult)
    def calculation(calculation_id: str):
        return service.calculation(calculation_id)

    @app.get('/api/calculations/{calculation_id}/items/{item_id}', response_model=ItemExplanation)
    def explanation(calculation_id: str, item_id: str):
        return service.explanation(calculation_id, item_id)

    @app.post('/api/orders', response_model=OrderDraft, status_code=201)
    def create_order(body: OrderCreate):
        return service.create_order(body)

    @app.get('/api/orders/{order_id}', response_model=OrderDraft)
    def order(order_id: str):
        return service.order(order_id)

    @app.patch('/api/orders/{order_id}', response_model=OrderDraft)
    def patch_order(order_id: str, body: OrderPatch):
        return service.patch_order(order_id, body)

    @app.post('/api/orders/{order_id}/approve', response_model=OrderDraft)
    def approve_order(order_id: str, body: OrderApproval):
        return service.approve_order(order_id, body)

    @app.get('/api/orders/{order_id}/export', response_class=Response,
             responses={200: {'content': {'text/csv': {'schema': {'type': 'string', 'format': 'binary'}}}}})
    def export_order(order_id: str, revision: Annotated[int, Query(ge=1)], format: Literal['csv'] = 'csv'):
        content = service.export_order(order_id, revision)
        return Response(content, media_type='text/csv; charset=utf-8', headers={
            'Content-Disposition': f'attachment; filename="order-{order_id}-r{revision}.csv"',
        })

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path == 'api' or path.startswith('api/'):
            raise DomainError(404, 'NOT_FOUND', 'Маршрут API не найден')
        root = settings.frontend_dist.resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise DomainError(404, 'NOT_FOUND', 'Файл не найден')
        if target.is_file():
            return FileResponse(target)
        if Path(path).suffix:
            raise DomainError(404, 'NOT_FOUND', 'Файл не найден')
        index = root / 'index.html'
        if index.exists():
            return FileResponse(index)
        raise DomainError(404, 'FRONTEND_NOT_BUILT', 'Соберите интерфейс командой npm run build')

    return app

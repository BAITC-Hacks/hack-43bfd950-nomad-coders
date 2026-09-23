from app.api.errors import DomainError


class Service:
    def __init__(self, settings):
        self.settings = settings

    def datasets(self):
        return []

    def unavailable(self, *args, **kwargs):
        raise DomainError(501, 'NOT_IMPLEMENTED', 'Операция ещё не подключена к каркасу')

    import_dataset = unavailable
    calculate = unavailable
    calculation = unavailable
    explanation = unavailable
    create_order = unavailable
    order = unavailable
    patch_order = unavailable
    approve_order = unavailable
    export_order = unavailable

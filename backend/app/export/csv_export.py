import csv
from io import StringIO

from app.contracts import OrderDraft


def safe_text(value):
    text = '' if value is None else str(value)
    if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        return "'" + text
    return text


def export_csv(order: OrderDraft) -> bytes:
    stream = StringIO(newline='')
    writer = csv.writer(stream, delimiter=';', lineterminator='\r\n')
    writer.writerow(['Заказ', 'Версия', 'Синтетика', 'Поставщик', 'Код', 'Артикул', 'Наименование',
                     'Единица', 'Рекомендовано', 'Согласовано', 'Причина правки'])
    for line in order.lines:
        writer.writerow([
            safe_text(order.id), order.revision, 'Да' if order.is_synthetic else 'Нет',
            safe_text(order.supplier), safe_text(line.product.sku), safe_text(line.product.article),
            safe_text(line.product.name), safe_text(line.product.unit),
            format(line.recommended_quantity, '.15g'), format(line.quantity, '.15g'),
            safe_text(line.override_reason),
        ])
    return stream.getvalue().encode('utf-8-sig')

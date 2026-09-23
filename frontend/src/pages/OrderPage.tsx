import { useState } from 'react'
import { ApiError, type Calculation, type Order } from '../api/client'
import { date, ErrorNotice, quantity, suppliers } from '../components/common'
export type Edits = Record<string, { quantity: string; reason: string }>
type Props = { order: Order; calculation: Calculation | null; edits: Edits; onEdit: (id: string, field: 'quantity' | 'reason', value: string) => void; busy: boolean; error: unknown; onSave: () => void; onReload: () => void; onDiscard: () => void; onApprove: () => void; onExport: () => void }
export function OrderPage(p: Props) {
  const [confirm, setConfirm] = useState<'discard' | 'reload' | null>(null)
  const dirty = Object.keys(p.edits).length > 0
  const conflict = p.error instanceof ApiError && p.error.status === 409
  return <section className="panel"><div className="section-heading"><div><h2>Проверка заказа</h2><p className="muted">{suppliers[p.order.supplier]} · сохранён {date(p.order.updated_at)} в {new Date(p.order.updated_at).toLocaleTimeString('ru-RU')}</p></div><span className="badge">{p.order.status === 'approved' ? 'Согласован' : 'Черновик'} · версия {p.order.revision}</span></div>
    <p className="muted">Исходная рекомендация сохраняется. Каждая правка требует причины и повторного согласования.{p.order.is_synthetic && ' Заказ содержит синтетические данные.'}</p>
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Строки заказа"><table><thead><tr><th>Товар / единица</th><th className="numeric">Рекомендовано</th><th>В заказе</th><th>Причина правки</th></tr></thead><tbody>{p.order.lines.map(line => {
      const r = p.calculation?.recommendations.find(r => r.id === line.recommendation_id)
      const edit = p.edits[line.recommendation_id]
      const invalid = edit && (!edit.quantity.trim() || !Number.isFinite(Number(edit.quantity)) || Number(edit.quantity) < 0)
      return <tr key={line.recommendation_id}><td className="product-cell"><b>{line.product.name}</b><small>{line.product.sku} · {line.product.article} · {line.product.unit ?? 'Единица неизвестна'}</small>{r && <small>Минимум: {quantity(r.components.minimum)} · кратность: {quantity(r.components.multiple)}</small>}</td><td className="numeric">{quantity(line.recommended_quantity)} {line.product.unit}</td>
        <td><input className="order-input" aria-label={'Количество ' + line.product.sku} aria-invalid={invalid || undefined} disabled={p.busy} type="number" min="0" step="any" value={edit?.quantity ?? String(line.quantity)} onChange={e => p.onEdit(line.recommendation_id, 'quantity', e.target.value)} />{invalid && <small className="field-error">Введите число от нуля</small>}</td>
        <td><input className="reason-input" aria-label={'Причина ' + line.product.sku} aria-invalid={edit && !edit.reason.trim() || undefined} disabled={p.busy} value={edit?.reason ?? line.override_reason ?? ''} onChange={e => p.onEdit(line.recommendation_id, 'reason', e.target.value)} placeholder="Обязательна при изменении" />{edit && !edit.reason.trim() && <small className="field-error">Укажите причину правки</small>}</td></tr>
    })}</tbody></table></div>
    {dirty && <p className="notice warning" role="status">Есть несохранённые изменения. Сохраните их или явно отмените перед переходом. Согласование и экспорт недоступны.</p>}
    <ErrorNotice error={p.error} />{conflict && <div className="notice warning"><p>Ваши значения сохранены на экране. Загрузка актуальной версии заменит их данными сервера.</p><button disabled={p.busy} onClick={() => dirty ? setConfirm('reload') : p.onReload()}>Загрузить актуальную версию</button></div>}
    {confirm && <div className="notice warning" role="alert"><p>{confirm === 'reload' ? 'Заменить введённые значения актуальной версией сервера?' : 'Отменить все несохранённые правки?'}</p><div className="toolbar"><button disabled={p.busy} onClick={() => { confirm === 'reload' ? p.onReload() : p.onDiscard(); setConfirm(null) }}>Да, {confirm === 'reload' ? 'загрузить версию' : 'отменить правки'}</button><button onClick={() => setConfirm(null)}>Продолжить редактирование</button></div></div>}
    <div className="action-bar"><button className={dirty ? 'primary' : ''} disabled={p.busy || !dirty} onClick={p.onSave}>Сохранить правки</button><button className={!dirty && p.order.status !== 'approved' ? 'primary' : ''} disabled={p.busy || dirty || p.order.status === 'approved'} onClick={p.onApprove}>Согласовать заказ</button>
      {p.order.status === 'approved' && !dirty && <button className="primary" disabled={p.busy} onClick={p.onExport}>Скачать CSV</button>}
      <button disabled={p.busy || dirty} onClick={p.onReload}>Загрузить сохранённый заказ</button>{dirty && <button disabled={p.busy} onClick={() => setConfirm('discard')}>Отменить несохранённые правки</button>}
    </div>{p.busy && <p role="status">Выполняем запрос…</p>}<p className="muted">CSV содержит сохранённую согласованную версию. Заказ поставщику автоматически не отправляется.</p>
  </section>
}

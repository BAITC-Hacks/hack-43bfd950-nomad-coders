import type { components } from '../api/generated/schema'
import { ApiError, type Recommendation } from '../api/client'

export const quantity = (value: number | null | undefined) => value == null ? 'Нет данных' : value.toLocaleString('ru-RU', { maximumFractionDigits: 3 })
export const date = (value: string | null | undefined) => value ? new Date(value.length === 10 ? value + 'T00:00:00' : value).toLocaleDateString('ru-RU') : 'Дата неизвестна'
export const suppliers = { systeme: 'Systeme Electric', iek: 'IEK', demo: 'Демонстрационный поставщик' }
export const statuses = { order_now: 'Заказать', expedite: 'Срочно', covered: 'Запас достаточен', needs_input: 'Нужны данные' }
export const demandSources = { transactions: 'Транзакции', monthly: 'Месячные продажи', demo_fixture: 'Фиксированный пример' }
export const canSelect = (r: Recommendation) => r.quantity != null && !!r.product.unit && !(r.issues ?? []).some(i => i.severity === 'blocking')
export const sourceText = (s: components['schemas']['SourceRef']) => [s.file, s.sheet, s.cell, s.row != null ? `строка ${s.row}` : null, s.note].filter(Boolean).join(' · ')
export function Issues({ issues = [] }: { issues?: components['schemas']['Issue'][] }) {
  return issues.length ? <ul className="issues">{issues.map((issue, i) => <li key={i} className={issue.severity === 'blocking' ? 'blocking' : ''}>
    <strong>{issue.severity === 'blocking' ? 'Блокирует заказ' : 'Предупреждение'}</strong> — {issue.message}
    {issue.sku && <small>SKU: {issue.sku}</small>}{issue.source && <small>{sourceText(issue.source)}</small>}
  </li>)}</ul> : null
}
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null
  return <div className="notice error" role="alert"><strong>{error instanceof ApiError && error.status === 409 ? 'Версия заказа изменилась. ' : error instanceof ApiError && error.status === 501 ? 'Функция пока недоступна. ' : 'Не удалось выполнить действие. '}</strong>
    {error instanceof Error ? error.message : String(error)}
    {error instanceof ApiError && <Issues issues={error.details} />}
  </div>
}
export function RecommendationQuantity({ value, unit }: { value: number | null; unit: string | null }) {
  return value == null ? <span className="badge warning">Нужны данные</span> : value === 0 ? <span className="zero-quantity"><b>0 {unit}</b><small>Заказывать не нужно</small></span> : <b>{quantity(value)} {unit}</b>
}

import type { components } from './generated/schema'

export type Dataset = components['schemas']['Dataset']
export type Calculation = components['schemas']['CalculationResult']
export type Explanation = components['schemas']['ItemExplanation']
export type Order = components['schemas']['OrderDraft']
export type Recommendation = components['schemas']['Recommendation']

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string,
    public details: components['schemas']['Issue'][] = []) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...init, headers: { ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...init?.headers } })
  } catch { throw new ApiError(0, 'NETWORK_ERROR', 'Нет соединения с сервером. Проверьте, что backend запущен.') }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, body?.error?.code ?? 'HTTP_ERROR', body?.error?.message ?? 'Не удалось выполнить запрос', body?.error?.details ?? [])
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<components['schemas']['Health']>('/health'),
  datasets: () => request<Dataset[]>('/datasets'),
  calculate: (body: components['schemas']['CalculationRequest']) => request<Calculation>('/calculations', { method: 'POST', body: JSON.stringify(body) }),
  calculation: (id: string) => request<Calculation>(`/calculations/${encodeURIComponent(id)}`),
  explanation: (calculation: string, item: string) => request<Explanation>(`/calculations/${encodeURIComponent(calculation)}/items/${encodeURIComponent(item)}`),
  createOrder: (body: components['schemas']['OrderCreate']) => request<Order>('/orders', { method: 'POST', body: JSON.stringify(body) }),
  order: (id: string) => request<Order>(`/orders/${encodeURIComponent(id)}`),
  patchOrder: (id: string, body: components['schemas']['OrderPatch']) => request<Order>(`/orders/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  approve: (id: string, revision: number) => request<Order>(`/orders/${encodeURIComponent(id)}/approve`, { method: 'POST', body: JSON.stringify({ expected_revision: revision, confirmed: true }) }),
  upload: (files: File[], supplier: 'systeme' | 'iek') => {
    const body = new FormData(); files.forEach(file => body.append('files', file)); body.append('supplier', supplier)
    return request<Dataset>('/datasets', { method: 'POST', body })
  },
  exportUrl: (order: Order) => `/api/orders/${encodeURIComponent(order.id)}/export?revision=${order.revision}&format=csv`,
}

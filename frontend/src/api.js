/*
 * Leaky-Buckets API client
 * All API calls go through here.
 */

const API_BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const token = sessionStorage.getItem('idToken')
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: token } : {}),
    ...options.headers,
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  const data = await res.json()

  if (!res.ok) {
    throw new Error(data.error || `Request failed: ${res.status}`)
  }
  return data
}

export const api = {
  // Health
  health: () => request('/health'),

  // Upload
  upload: (fileName, source, csvContent) =>
    request('/upload', {
      method: 'POST',
      body: JSON.stringify({ fileName, source, csvContent }),
    }),
  uploadFile: (fileName, source, fileContent) =>
    request('/upload', {
      method: 'POST',
      body: JSON.stringify({ fileName, source, fileContent }),
    }),

  // Transactions
  getTransactions: (monthKey) => request(`/transactions?monthKey=${monthKey}`),
  updateTransaction: (transactionId, bucket, rememberMerchant = false, monthKey = '') =>
    request(`/transactions/${transactionId}`, {
      method: 'PUT',
      body: JSON.stringify({ bucket, rememberMerchant, monthKey }),
    }),

  // Buckets
  getBuckets: () => request('/buckets'),
  updateBucket: (bucketId, updates) =>
    request(`/buckets/${bucketId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),
  seedBuckets: () => request('/buckets/seed', { method: 'POST' }),

  // Month
  getMonthSummary: (monthKey) => request(`/month/${monthKey}`),
  lockMonth: (monthKey) =>
    request(`/month/${monthKey}/lock`, { method: 'POST' }),

  // Delete all data
  deleteAllData: () =>
    request('/delete-all-data', {
      method: 'POST',
      body: JSON.stringify({ confirmation: 'DELETE' }),
    }),

  // Paystubs (The Faucet 🚰)
  uploadPaystub: (fileName, source, fileContent) =>
    request('/paystub', {
      method: 'POST',
      body: JSON.stringify({ fileName, source, fileContent }),
    }),
  getPaystubs: (monthKey) => request(`/paystub?monthKey=${monthKey}`),
  updatePaystub: (paystubId, updates) =>
    request(`/paystub/${paystubId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),
  deletePaystub: (paystubId) =>
    request(`/paystub/${paystubId}`, { method: 'DELETE' }),
}

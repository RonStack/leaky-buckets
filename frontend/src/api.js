/*
 * ChestCheck API client
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

  if (!res.ok) {
    let message = `Request failed: ${res.status}`
    try {
      const data = await res.json()
      if (data.error) message = data.error
    } catch {
      message = `${res.status} ${res.statusText || 'Gateway Timeout'}`
    }
    throw new Error(message)
  }

  return res.json()
}

export const api = {
  // Health
  health: () => request('/health'),

  // User & Household
  getMe: () => request('/me'),
  joinHousehold: (householdId) =>
    request('/household/join', {
      method: 'POST',
      body: JSON.stringify({ householdId }),
    }),

  // Categories (Chests)
  getCategories: () => request('/categories'),
  createCategory: (category) =>
    request('/categories', {
      method: 'POST',
      body: JSON.stringify(category),
    }),
  updateCategory: (categoryId, updates) =>
    request(`/categories/${categoryId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  // Transactions (Spends)
  getTransactions: (monthKey) =>
    request(`/transactions?monthKey=${monthKey}`),
  logSpend: (transaction) =>
    request('/transactions', {
      method: 'POST',
      body: JSON.stringify(transaction),
    }),
  deleteTransaction: (transactionId) =>
    request(`/transactions/${transactionId}`, { method: 'DELETE' }),

  // Summary
  getSummary: (monthKey) =>
    request(`/summary?monthKey=${monthKey}`),

  // Data management
  deleteAllData: () =>
    request('/data', { method: 'DELETE' }),
}

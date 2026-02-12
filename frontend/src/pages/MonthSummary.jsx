import React, { useState, useEffect } from 'react'
import { api } from '../api'

function getMonthOptions() {
  const options = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    options.push({ value, label })
  }
  return options
}

function formatDollars(cents) {
  const abs = Math.abs(cents)
  const sign = cents < 0 ? '-' : ''
  return `${sign}$${(abs / 100).toFixed(2)}`
}

function stateLabel(state) {
  switch (state) {
    case 'healthy': return '✅ Healthy'
    case 'low': return '⚠️ Low'
    case 'almost-empty': return '🔥 Almost Empty'
    case 'cracked': return '💀 Cracked'
    default: return state
  }
}

export default function MonthSummary() {
  const months = getMonthOptions()
  const [monthKey, setMonthKey] = useState(months[0].value)
  const [summary, setSummary] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')

    Promise.all([
      api.getSummary(monthKey),
      api.getTransactions(monthKey),
    ])
      .then(([sumData, txnData]) => {
        if (cancelled) return
        setSummary(sumData)
        setTransactions(txnData.transactions || [])
      })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [monthKey])

  const monthLabel = months.find((m) => m.value === monthKey)?.label || monthKey

  return (
    <div className="month-summary">
      <div className="summary-header">
        <h2>Month Summary</h2>
        <select value={monthKey} onChange={(e) => setMonthKey(e.target.value)} className="month-picker">
          {months.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      {loading && <div className="loading">Loading…</div>}
      {error && <div className="error-msg">{error}</div>}

      {summary && !loading && (
        <>
          {/* Overall totals */}
          <div className="summary-totals">
            <div className="total-card">
              <div className="total-label">Total Spent</div>
              <div className="total-value spent">{formatDollars(summary.totalSpentCents)}</div>
            </div>
            <div className="total-card">
              <div className="total-label">Total Limit</div>
              <div className="total-value">{formatDollars(summary.totalLimitCents)}</div>
            </div>
            <div className="total-card">
              <div className="total-label">Remaining</div>
              <div className={`total-value ${summary.totalRemainingCents < 0 ? 'overspent' : 'remaining'}`}>
                {formatDollars(summary.totalRemainingCents)}
              </div>
            </div>
            <div className="total-card">
              <div className="total-label">Transactions</div>
              <div className="total-value">{summary.transactionCount}</div>
            </div>
          </div>

          {/* Category breakdown */}
          <h3>Category Breakdown</h3>
          <div className="category-breakdown">
            {summary.chests.map((chest) => (
              <div key={chest.categoryId} className={`breakdown-row state-${chest.state}`}>
                <span className="breakdown-emoji">{chest.emoji}</span>
                <span className="breakdown-name">{chest.name}</span>
                <span className="breakdown-spent">{formatDollars(chest.spentCents)}</span>
                <span className="breakdown-sep">/</span>
                <span className="breakdown-limit">{formatDollars(chest.monthlyLimitCents)}</span>
                <span className="breakdown-state">{stateLabel(chest.state)}</span>
              </div>
            ))}
          </div>

          {/* Transaction list */}
          <h3>Transactions ({transactions.length})</h3>
          {transactions.length === 0 ? (
            <p className="empty-state">No transactions this month.</p>
          ) : (
            <div className="txn-list">
              {transactions.map((txn) => (
                <div key={txn.transactionId} className="txn-row">
                  <span className="txn-amount">{formatDollars(txn.amountCents)}</span>
                  <span className="txn-note">{txn.note || '—'}</span>
                  <span className="txn-date">
                    {new Date(txn.createdAt).toLocaleDateString('en-US', {
                      month: 'short', day: 'numeric',
                    })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

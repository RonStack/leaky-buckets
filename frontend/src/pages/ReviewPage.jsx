import React, { useState, useEffect } from 'react'
import { api } from '../api'

const BUCKETS = [
  'Home & Utilities',
  'Groceries',
  'Shopping',
  'Dining & Coffee',
  'Subscriptions',
  'Health',
  'Transport',
  'Fun & Travel',
  'One-Off & Big Hits',
]

export default function ReviewPage({ monthKey, setPage }) {
  const [transactions, setTransactions] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lockLoading, setLockLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState('')

  useEffect(() => {
    loadTransactions()
  }, [monthKey])

  async function loadTransactions() {
    setLoading(true)
    setError('')
    try {
      const data = await api.getTransactions(monthKey)
      setTransactions(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleCategorize(txnId, bucket, remember) {
    try {
      await api.updateTransaction(txnId, bucket, remember, monthKey)
      await loadTransactions() // Refresh
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleDeleteExpenses() {
    const label = getMonthLabel(monthKey)
    if (!window.confirm(`Delete ALL expense transactions for ${label}?\n\nThis cannot be undone.`)) return
    setDeleteLoading('expenses')
    try {
      const result = await api.deleteExpenses(monthKey)
      alert(`✅ ${result.message}`)
      await loadTransactions()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleteLoading('')
    }
  }

  async function handleDeleteIncome() {
    const label = getMonthLabel(monthKey)
    if (!window.confirm(`Delete ALL income/paystub data for ${label}?\n\nThis cannot be undone.`)) return
    setDeleteLoading('income')
    try {
      const result = await api.deleteIncome(monthKey)
      alert(`✅ ${result.message}`)
      setPage('dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleteLoading('')
    }
  }

  async function handleLock() {
    if (!window.confirm(`Lock ${monthKey}? Transactions will become immutable.`)) return
    setLockLoading(true)
    try {
      await api.lockMonth(monthKey)
      setPage('dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setLockLoading(false)
    }
  }

  if (loading) return <div className="loading">Loading transactions... 📋</div>
  if (error) return <div className="error-box">{error}</div>
  if (!transactions) return null

  const { needsReview, categorized, total } = transactions

  return (
    <div className="review-page">
      <div className="review-header">
        <h2>Review — {getMonthLabel(monthKey)}</h2>
        <div className="review-header-row">
          <div className="review-stats">
            <span>{total} total</span>
            <span className={needsReview.length > 0 ? 'needs-attention' : 'all-good'}>
              {needsReview.length > 0
                ? `⚡ ${needsReview.length} need attention`
                : '✅ All categorized!'}
            </span>
          </div>
          <div className="review-delete-actions">
            <button
              className="delete-month-btn"
              onClick={handleDeleteExpenses}
              disabled={!!deleteLoading}
              title="Delete all expense transactions for this month"
            >
              {deleteLoading === 'expenses' ? 'Deleting...' : '🗑️ Delete Expenses'}
            </button>
            <button
              className="delete-month-btn"
              onClick={handleDeleteIncome}
              disabled={!!deleteLoading}
              title="Delete all income/paystub data for this month"
            >
              {deleteLoading === 'income' ? 'Deleting...' : '🗑️ Delete Income'}
            </button>
          </div>
        </div>
      </div>

      {needsReview.length > 0 && (
        <section className="review-section">
          <h3>⚡ Needs Your Input</h3>
          <div className="transaction-list">
            {needsReview.map((txn) => (
              <TransactionCard
                key={txn.transactionId || txn.sk}
                txn={txn}
                onCategorize={handleCategorize}
              />
            ))}
          </div>
        </section>
      )}

      {categorized.length > 0 && (
        <section className="review-section">
          <h3>✅ Categorized ({categorized.length})</h3>
          <div className="transaction-list compact">
            {categorized.map((txn) => (
              <CategorizedRow
                key={txn.transactionId || txn.sk}
                txn={txn}
                onCategorize={handleCategorize}
              />
            ))}
          </div>
        </section>
      )}

      {needsReview.length === 0 && total > 0 && (
        <div className="lock-section">
          <p>Everything looks good! Ready to lock this month?</p>
          <button
            className="lock-btn"
            onClick={handleLock}
            disabled={lockLoading}
          >
            {lockLoading ? 'Locking...' : '🔒 Lock ' + getMonthLabel(monthKey)}
          </button>
        </div>
      )}
    </div>
  )
}

function CategorizedRow({ txn, onCategorize }) {
  const [editing, setEditing] = useState(false)
  const [selectedBucket, setSelectedBucket] = useState(txn.bucket || '')
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!selectedBucket || selectedBucket === txn.bucket) {
      setEditing(false)
      return
    }
    setSaving(true)
    await onCategorize(txn.transactionId, selectedBucket, false)
    setSaving(false)
    setEditing(false)
  }

  function handleCancel() {
    setSelectedBucket(txn.bucket || '')
    setEditing(false)
  }

  return (
    <div className="txn-row">
      <span className="txn-date">{txn.date}</span>
      <span className="txn-desc">{txn.description}</span>
      {editing ? (
        <span className="txn-bucket-edit">
          <select
            value={selectedBucket}
            onChange={(e) => setSelectedBucket(e.target.value)}
          >
            {BUCKETS.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
          <button className="inline-save-btn" onClick={handleSave} disabled={saving}>
            {saving ? '...' : '✓'}
          </button>
          <button className="inline-cancel-btn" onClick={handleCancel}>✕</button>
        </span>
      ) : (
        <span className="txn-bucket clickable" onClick={() => setEditing(true)} title="Click to change bucket">
          {txn.bucket}
        </span>
      )}
      <span className={`txn-amount ${txn.amount < 0 ? 'negative' : 'positive'}`}>
        ${Math.abs(txn.amount).toLocaleString()}
      </span>
    </div>
  )
}

function TransactionCard({ txn, onCategorize }) {
  const [selectedBucket, setSelectedBucket] = useState(txn.bucket || '')
  const [remember, setRemember] = useState(true)

  function handleSave() {
    if (!selectedBucket) return
    onCategorize(txn.transactionId, selectedBucket, remember)
  }

  return (
    <div className="txn-card">
      <div className="txn-card-top">
        <span className="txn-date">{txn.date}</span>
        <span className={`txn-amount ${txn.amount < 0 ? 'negative' : 'positive'}`}>
          ${Math.abs(txn.amount).toLocaleString()}
        </span>
      </div>
      <div className="txn-description">{txn.description}</div>
      {txn.categorizationReasoning && txn.bucket && (
        <div className="txn-ai-hint">
          💡 AI suggests: <strong>{txn.bucket}</strong>
          <span className="confidence">({Math.round((txn.confidence || 0) * 100)}% sure)</span>
        </div>
      )}
      <div className="txn-card-actions">
        <select
          value={selectedBucket}
          onChange={(e) => setSelectedBucket(e.target.value)}
        >
          <option value="">Choose a bucket...</option>
          {BUCKETS.map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
        <label className="remember-label">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
          />
          Remember this merchant
        </label>
        <button
          className="categorize-btn"
          onClick={handleSave}
          disabled={!selectedBucket}
        >
          ✓ Set
        </button>
      </div>
    </div>
  )
}

function getMonthLabel(monthKey) {
  const [year, month] = monthKey.split('-')
  const date = new Date(parseInt(year), parseInt(month) - 1, 1)
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

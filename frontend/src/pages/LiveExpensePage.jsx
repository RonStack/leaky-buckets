import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function LiveExpensePage({ monthKey, setPage }) {
  const [buckets, setBuckets] = useState([])
  const [amount, setAmount] = useState('')
  const [bucketId, setBucketId] = useState('')
  const [note, setNote] = useState('')
  const [date, setDate] = useState(todayStr())
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [recentExpenses, setRecentExpenses] = useState([])
  const [loadingRecent, setLoadingRecent] = useState(true)

  useEffect(() => {
    loadBuckets()
    loadRecent()
  }, [monthKey])

  async function loadBuckets() {
    try {
      await api.seedBuckets()
      const data = await api.getBuckets()
      const list = data.buckets || data || []
      setBuckets(list)
      if (list.length > 0 && !bucketId) {
        setBucketId(list[0].bucketId)
      }
    } catch (err) {
      setError('Failed to load buckets')
    }
  }

  async function loadRecent() {
    setLoadingRecent(true)
    try {
      const data = await api.getLiveExpenses(monthKey)
      setRecentExpenses(data.expenses || [])
    } catch {
      // API may not be deployed yet
      setRecentExpenses([])
    } finally {
      setLoadingRecent(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!amount || !bucketId) return

    setSubmitting(true)
    setError('')
    setSuccess('')

    const selectedBucket = buckets.find(b => b.bucketId === bucketId)

    try {
      await api.addLiveExpense({
        amount: parseFloat(amount),
        bucketId,
        bucketName: selectedBucket?.name || bucketId,
        note,
        date,
      })
      setSuccess(`$${parseFloat(amount).toFixed(2)} recorded to ${selectedBucket?.emoji || ''} ${selectedBucket?.name || bucketId}`)
      setAmount('')
      setNote('')
      // Reload recent
      loadRecent()
      // Clear success after 3s
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(expense) {
    if (!confirm('Delete this expense?')) return
    try {
      await api.deleteLiveExpense(expense.expenseId, expense.sk)
      loadRecent()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="live-expense-page">
      <h2>⚡ Add Expense</h2>
      <p className="page-subtitle">Record a purchase as it happens</p>

      <form className="live-expense-form" onSubmit={handleSubmit}>
        {/* Amount */}
        <div className="live-field">
          <label htmlFor="live-amount">Amount</label>
          <div className="live-amount-input">
            <span className="dollar-prefix">$</span>
            <input
              id="live-amount"
              type="number"
              step="0.01"
              min="0.01"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              autoFocus
            />
          </div>
        </div>

        {/* Bucket */}
        <div className="live-field">
          <label htmlFor="live-bucket">Bucket</label>
          <div className="live-bucket-grid">
            {buckets.map(b => (
              <button
                key={b.bucketId}
                type="button"
                className={`live-bucket-option ${bucketId === b.bucketId ? 'selected' : ''}`}
                onClick={() => setBucketId(b.bucketId)}
              >
                <span className="live-bucket-emoji">{b.emoji}</span>
                <span className="live-bucket-name">{b.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Date */}
        <div className="live-field">
          <label htmlFor="live-date">Date</label>
          <input
            id="live-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="live-date-input"
          />
        </div>

        {/* Note */}
        <div className="live-field">
          <label htmlFor="live-note">Note <span className="optional">(optional)</span></label>
          <input
            id="live-note"
            type="text"
            placeholder="Coffee, gas, groceries..."
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="live-note-input"
          />
        </div>

        {error && <div className="error-msg">{error}</div>}
        {success && <div className="live-success">{success}</div>}

        <button
          type="submit"
          className="primary-btn live-submit-btn"
          disabled={submitting || !amount || !bucketId}
        >
          {submitting ? 'Recording...' : 'Record Expense 💧'}
        </button>
      </form>

      {/* Recent expenses this month */}
      <div className="live-recent">
        <h3>Recent — {getMonthLabel(monthKey)}</h3>
        {loadingRecent ? (
          <p className="loading-small">Loading...</p>
        ) : recentExpenses.length === 0 ? (
          <p className="no-expenses">No live expenses recorded this month yet.</p>
        ) : (
          <div className="live-expense-list">
            {recentExpenses.map(exp => (
              <div key={exp.expenseId} className="live-expense-row">
                <span className="live-exp-date">{formatDate(exp.date)}</span>
                <span className="live-exp-bucket">
                  {buckets.find(b => b.bucketId === exp.bucketId)?.emoji || '🪣'}{' '}
                  {exp.bucketName}
                </span>
                <span className="live-exp-note">{exp.note || '—'}</span>
                <span className="live-exp-amount">${exp.amount.toFixed(2)}</span>
                <button
                  className="live-exp-delete"
                  onClick={() => handleDelete(exp)}
                  title="Delete"
                >
                  ✕
                </button>
              </div>
            ))}
            <div className="live-expense-total">
              <span>Total</span>
              <span>${recentExpenses.reduce((s, e) => s + e.amount, 0).toFixed(2)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const [y, m, d] = dateStr.split('-')
  return `${parseInt(m)}/${parseInt(d)}`
}

function getMonthLabel(monthKey) {
  const [year, month] = monthKey.split('-')
  const date = new Date(parseInt(year), parseInt(month) - 1, 1)
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

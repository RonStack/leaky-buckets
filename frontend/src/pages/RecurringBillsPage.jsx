import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function RecurringBillsPage({ monthKey }) {
  const [bills, setBills] = useState([])
  const [buckets, setBuckets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Add form
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [bucketId, setBucketId] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      await api.seedBuckets()
      const [billData, bucketData] = await Promise.all([
        api.getRecurringBills(),
        api.getBuckets(),
      ])
      setBills(billData.bills || [])
      const list = bucketData.buckets || bucketData || []
      setBuckets(list)
      if (list.length > 0 && !bucketId) setBucketId(list[0].bucketId)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleAdd(e) {
    e.preventDefault()
    if (!name.trim() || !amount || !bucketId) return

    setSubmitting(true)
    setError('')
    try {
      const bucket = buckets.find(b => b.bucketId === bucketId)
      await api.addRecurringBill({
        name: name.trim(),
        amount: parseFloat(amount),
        bucketId,
        bucketName: bucket?.name || '',
      })
      setName('')
      setAmount('')
      setShowForm(false)
      setSuccess('Bill added!')
      setTimeout(() => setSuccess(''), 2000)
      await loadData()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(billId) {
    try {
      await api.deleteRecurringBill(billId)
      setBills(prev => prev.filter(b => b.billId !== billId))
      setSuccess('Bill removed.')
      setTimeout(() => setSuccess(''), 2000)
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <div className="loading">Loading recurring bills...</div>

  // Build a map for bucket emoji lookup
  const bucketMap = {}
  for (const b of buckets) bucketMap[b.bucketId] = b

  // Group bills by bucket
  const totalMonthly = bills.reduce((sum, b) => sum + (b.amount || 0), 0)

  return (
    <div className="recurring-page">
      <div className="recurring-header">
        <h2>🔁 Recurring Bills</h2>
        <p className="recurring-subtitle">
          Bills that repeat every month. Apply them to any month from the Dashboard.
        </p>
      </div>

      {error && <div className="error-box">{error}</div>}
      {success && <div className="success-msg">{success}</div>}

      {/* Summary */}
      {bills.length > 0 && (
        <div className="recurring-summary">
          <span className="recurring-summary-count">{bills.length} bill{bills.length !== 1 ? 's' : ''}</span>
          <span className="recurring-summary-total">${totalMonthly.toLocaleString()} / month</span>
        </div>
      )}

      {/* Bill list */}
      {bills.length === 0 && !showForm ? (
        <div className="empty-state">
          <div className="empty-icon">🔁</div>
          <h3>No recurring bills yet</h3>
          <p>Add your monthly bills like rent, subscriptions, and utilities.</p>
          <button className="primary-btn" onClick={() => setShowForm(true)}>
            Add First Bill →
          </button>
        </div>
      ) : (
        <>
          <div className="recurring-list">
            {bills.map(bill => {
              const bucket = bucketMap[bill.bucketId]
              return (
                <div key={bill.billId} className="recurring-item">
                  <span className="recurring-item-emoji">{bucket?.emoji || '📦'}</span>
                  <div className="recurring-item-info">
                    <span className="recurring-item-name">{bill.name}</span>
                    <span className="recurring-item-bucket">{bill.bucketName || bucket?.name || 'Unknown'}</span>
                  </div>
                  <span className="recurring-item-amount">${(bill.amount || 0).toLocaleString()}</span>
                  <button
                    className="recurring-item-delete"
                    onClick={() => handleDelete(bill.billId)}
                    title="Remove bill"
                  >
                    ✕
                  </button>
                </div>
              )
            })}
          </div>

          {!showForm && (
            <button className="recurring-add-btn" onClick={() => setShowForm(true)}>
              + Add Bill
            </button>
          )}
        </>
      )}

      {/* Add form */}
      {showForm && (
        <form className="recurring-form" onSubmit={handleAdd}>
          <h3>New Recurring Bill</h3>

          <label>
            Name
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g., Netflix, Rent, Car Payment"
              autoFocus
              required
            />
          </label>

          <label>
            Amount (per month)
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              placeholder="0.00"
              step="0.01"
              min="0.01"
              required
            />
          </label>

          <label>
            Bucket
            <div className="recurring-bucket-grid">
              {buckets.map(b => (
                <button
                  key={b.bucketId}
                  type="button"
                  className={`recurring-bucket-opt ${bucketId === b.bucketId ? 'selected' : ''}`}
                  onClick={() => setBucketId(b.bucketId)}
                >
                  <span className="opt-emoji">{b.emoji}</span>
                  <span className="opt-name">{b.name}</span>
                </button>
              ))}
            </div>
          </label>

          <div className="recurring-form-actions">
            <button type="submit" className="primary-btn" disabled={submitting}>
              {submitting ? 'Adding...' : 'Add Bill'}
            </button>
            <button type="button" className="secondary-btn" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  )
}

import React, { useState, useEffect, useRef } from 'react'
import { api } from '../api'

function formatDollars(cents) {
  return `$${(cents / 100).toFixed(2)}`
}

export default function LogSpend({ navigate, refresh }) {
  const [categories, setCategories] = useState([])
  const [selectedCat, setSelectedCat] = useState('')
  const [amount, setAmount] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const amountRef = useRef(null)

  useEffect(() => {
    api.getCategories()
      .then((data) => {
        const active = (data.categories || []).filter((c) => c.isActive !== false)
        setCategories(active)
        if (active.length > 0) setSelectedCat(active[0].categoryId)
      })
      .catch((err) => setError(err.message))
  }, [])

  // Auto-focus the amount field for speed
  useEffect(() => {
    if (amountRef.current) amountRef.current.focus()
  }, [categories])

  async function handleSave(e) {
    e.preventDefault()
    setError('')

    const cents = Math.round(parseFloat(amount) * 100)
    if (!cents || cents <= 0) {
      setError('Enter a valid amount')
      return
    }
    if (!selectedCat) {
      setError('Pick a category')
      return
    }

    setSaving(true)
    try {
      await api.logSpend({
        amountCents: cents,
        categoryId: selectedCat,
        note: note.trim(),
      })
      setToast('Logged ✓')
      setAmount('')
      setNote('')
      refresh()
      // Return to dashboard after brief toast
      setTimeout(() => navigate('dashboard'), 600)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="log-spend">
      <h2>Log Spend</h2>

      {toast && <div className="toast">{toast}</div>}

      <form onSubmit={handleSave} className="log-spend-form">
        {/* Amount */}
        <label htmlFor="amount">Amount</label>
        <div className="amount-input-wrap">
          <span className="dollar-sign">$</span>
          <input
            ref={amountRef}
            id="amount"
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0.01"
            placeholder="0.00"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
        </div>

        {/* Category picker */}
        <label>Category</label>
        <div className="category-picker">
          {categories.map((cat) => (
            <button
              key={cat.categoryId}
              type="button"
              className={`cat-btn ${selectedCat === cat.categoryId ? 'selected' : ''}`}
              onClick={() => setSelectedCat(cat.categoryId)}
            >
              <span className="cat-emoji">{cat.emoji}</span>
              <span className="cat-name">{cat.name}</span>
            </button>
          ))}
        </div>

        {/* Note */}
        <label htmlFor="note">Note (optional)</label>
        <input
          id="note"
          type="text"
          placeholder="e.g. Trader Joe's"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={100}
        />

        {error && <div className="error-msg">{error}</div>}

        <button type="submit" className="save-btn" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </form>
    </div>
  )
}

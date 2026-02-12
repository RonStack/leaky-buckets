import React, { useState, useEffect } from 'react'
import { api } from '../api'

function getCurrentMonthKey() {
  const d = new Date()
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
}

/** Shift a "YYYY-MM" key by `delta` months (negative = past). */
function shiftMonth(monthKey, delta) {
  const [y, m] = monthKey.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function formatDollars(cents) {
  const abs = Math.abs(cents)
  const sign = cents < 0 ? '-' : ''
  return `${sign}$${(abs / 100).toFixed(2)}`
}

function stateEmoji(state) {
  switch (state) {
    case 'healthy': return '💎'
    case 'low': return '⚠️'
    case 'almost-empty': return '🔥'
    case 'cracked': return '💀'
    default: return '📦'
  }
}

export default function Dashboard({ navigate, refreshKey }) {
  const [monthKey, setMonthKey] = useState(getCurrentMonthKey)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')

    // Ensure user is provisioned, then load summary
    api.getMe()
      .then(() => api.getSummary(monthKey))
      .then((data) => { if (!cancelled) setSummary(data) })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [monthKey, refreshKey])

  if (loading) {
    return <div className="loading">Loading chests…</div>
  }

  if (error) {
    return <div className="error-msg">{error}</div>
  }

  if (!summary) return null

  const monthLabel = new Date(monthKey + '-01').toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  })

  return (
    <div className="dashboard">
      {/* Month header with navigation */}
      <div className="month-header">
        <div className="month-nav">
          <button
            className="month-nav-btn"
            onClick={() => setMonthKey(shiftMonth(monthKey, -1))}
            aria-label="Previous month"
          >
            ‹
          </button>
          <h2>{monthLabel}</h2>
          <button
            className="month-nav-btn"
            onClick={() => setMonthKey(shiftMonth(monthKey, 1))}
            aria-label="Next month"
          >
            ›
          </button>
        </div>
        <div className="month-totals">
          <span className="spent">{formatDollars(summary.totalSpentCents)} spent</span>
          <span className="sep">of</span>
          <span className="limit">{formatDollars(summary.totalLimitCents)}</span>
          <span className="remaining">({formatDollars(summary.totalRemainingCents)} left)</span>
        </div>
      </div>

      {/* Chest grid */}
      <div className="chest-grid">
        {summary.chests.map((chest) => (
          <div key={chest.categoryId} className={`chest-card state-${chest.state}`}>
            <div className="chest-emoji">{chest.emoji}</div>
            <div className="chest-name">{chest.name}</div>
            <div className="chest-remaining">{formatDollars(chest.remainingCents)}</div>
            <div className="chest-bar">
              <div
                className="chest-bar-fill"
                style={{ width: `${Math.max(0, Math.min(100, chest.percentRemaining))}%` }}
              />
            </div>
            <div className="chest-state">{stateEmoji(chest.state)} {chest.state}</div>
          </div>
        ))}
      </div>

      {/* Log Spend button */}
      <button className="log-spend-fab" onClick={() => navigate('logspend')}>
        + Log Spend
      </button>
    </div>
  )
}

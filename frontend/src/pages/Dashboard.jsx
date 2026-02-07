import React, { useState, useEffect } from 'react'
import { api } from '../api'

const STATUS_EMOJI = {
  stable: '🟢',
  dripping: '🟡',
  overflowing: '🔴',
}

const STATUS_LABEL = {
  stable: 'Steady',
  dripping: 'Dripping',
  overflowing: 'Overflowing!',
}

export default function Dashboard({ monthKey, setPage }) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    seedAndLoad()
  }, [monthKey])

  async function seedAndLoad() {
    setLoading(true)
    setError('')
    try {
      // Ensure default buckets exist (idempotent)
      await api.seedBuckets()
      const data = await api.getMonthSummary(monthKey)
      setSummary(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="loading">Loading your buckets... 🪣</div>
  if (error) return <div className="error-box">{error}</div>
  if (!summary) return null

  const hasTransactions = summary.transactionCount > 0

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>
          {getMonthLabel(monthKey)}
          {summary.locked && <span className="locked-badge">🔒 Locked</span>}
        </h2>
        {hasTransactions && (
          <div className="summary-stats">
            <div className="stat">
              <span className="stat-value">${summary.totalSpent.toLocaleString()}</span>
              <span className="stat-label">spent</span>
            </div>
            <div className="stat">
              <span className="stat-value">{summary.transactionCount}</span>
              <span className="stat-label">transactions</span>
            </div>
            {summary.needsReview > 0 && (
              <div className="stat stat-warning" onClick={() => setPage('review')}>
                <span className="stat-value">{summary.needsReview}</span>
                <span className="stat-label">needs review ⚡</span>
              </div>
            )}
          </div>
        )}
      </div>

      {!hasTransactions ? (
        <div className="empty-state">
          <div className="empty-icon">🪣</div>
          <h3>No data yet for {getMonthLabel(monthKey)}</h3>
          <p>Upload your bank & credit card statements to get started.</p>
          <button className="primary-btn" onClick={() => setPage('upload')}>
            Upload Statements →
          </button>
        </div>
      ) : (
        <>
          <div className="bucket-grid">
            {summary.buckets.map((bucket) => (
              <BucketCard key={bucket.bucketId} bucket={bucket} onSetPage={setPage} />
            ))}
          </div>

          {summary.needsReview > 0 && !summary.locked && (
            <div className="cta-bar">
              <button className="primary-btn" onClick={() => setPage('review')}>
                Review {summary.needsReview} item{summary.needsReview > 1 ? 's' : ''} →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function BucketCard({ bucket, onSetPage }) {
  const pct = bucket.target > 0
    ? Math.min(Math.round((bucket.spent / bucket.target) * 100), 150)
    : 0

  return (
    <div className={`bucket-card bucket-${bucket.status}`}>
      <div className="bucket-header">
        <span className="bucket-emoji">{bucket.emoji}</span>
        <span className="bucket-status">{STATUS_EMOJI[bucket.status]}</span>
      </div>
      <h3 className="bucket-name">{bucket.name}</h3>
      <div className="bucket-amount">${bucket.spent.toLocaleString()}</div>
      {bucket.target > 0 ? (
        <>
          <div className="bucket-target">of ${bucket.target.toLocaleString()}</div>
          <div className="bucket-bar">
            <div
              className="bucket-bar-fill"
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
        </>
      ) : (
        <div
          className="bucket-no-target"
          onClick={() => onSetPage('settings')}
          title="Set a monthly target in Settings"
        >
          No target set
        </div>
      )}
      <div className="bucket-status-label">{STATUS_LABEL[bucket.status]}</div>
      <div className="bucket-count">{bucket.count} transaction{bucket.count !== 1 ? 's' : ''}</div>
    </div>
  )
}

function getMonthLabel(monthKey) {
  const [year, month] = monthKey.split('-')
  const date = new Date(parseInt(year), parseInt(month) - 1, 1)
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

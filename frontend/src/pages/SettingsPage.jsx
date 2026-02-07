import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function SettingsPage() {
  const [confirming, setConfirming] = useState(false)
  const [typed, setTyped] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  // Bucket targets
  const [buckets, setBuckets] = useState([])
  const [bucketsLoading, setBucketsLoading] = useState(true)
  const [savingId, setSavingId] = useState(null)
  const [bucketError, setBucketError] = useState('')

  useEffect(() => {
    loadBuckets()
  }, [])

  async function loadBuckets() {
    setBucketsLoading(true)
    try {
      await api.seedBuckets()
      const data = await api.getBuckets()
      setBuckets(data.buckets || [])
    } catch (err) {
      setBucketError(err.message)
    } finally {
      setBucketsLoading(false)
    }
  }

  function handleTargetChange(bucketId, value) {
    setBuckets((prev) =>
      prev.map((b) =>
        b.bucketId === bucketId ? { ...b, _editTarget: value } : b
      )
    )
  }

  async function saveTarget(bucket) {
    const raw = bucket._editTarget
    if (raw === undefined || raw === '') return
    const target = parseFloat(raw)
    if (isNaN(target) || target < 0) {
      setBucketError('Target must be a positive number')
      return
    }
    setSavingId(bucket.bucketId)
    setBucketError('')
    try {
      await api.updateBucket(bucket.bucketId, { monthlyTarget: target })
      await loadBuckets()
    } catch (err) {
      setBucketError(err.message)
    } finally {
      setSavingId(null)
    }
  }

  async function handleDelete() {
    if (typed !== 'DELETE') return
    setDeleting(true)
    setError('')
    try {
      const data = await api.deleteAllData()
      setResult(data)
      setConfirming(false)
      setTyped('')
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="settings-page">
      <h2>Settings</h2>
      <p className="page-subtitle">Manage your buckets and data.</p>

      {/* ---- Bucket Targets ---- */}
      <div className="settings-section">
        <h3>🪣 Monthly Bucket Targets</h3>
        <p className="settings-desc">
          Set a monthly spending target for each bucket. This controls the bucket status
          indicators: 🟢 under 80%, 🟡 80–100%, 🔴 over target. Leave at $0 for no target.
        </p>

        {bucketsLoading ? (
          <div className="loading">Loading buckets...</div>
        ) : (
          <div className="bucket-targets-list">
            {buckets.map((bucket) => {
              const editVal = bucket._editTarget !== undefined
                ? bucket._editTarget
                : bucket.monthlyTarget || ''
              const changed = bucket._editTarget !== undefined &&
                parseFloat(bucket._editTarget) !== (bucket.monthlyTarget || 0)
              return (
                <div key={bucket.bucketId} className="bucket-target-row">
                  <span className="bucket-target-emoji">{bucket.emoji}</span>
                  <span className="bucket-target-name">{bucket.name}</span>
                  <div className="bucket-target-input-group">
                    <span className="dollar-prefix">$</span>
                    <input
                      type="number"
                      min="0"
                      step="50"
                      value={editVal}
                      placeholder="0"
                      onChange={(e) => handleTargetChange(bucket.bucketId, e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && saveTarget(bucket)}
                      className="bucket-target-input"
                    />
                    {changed && (
                      <button
                        className="save-target-btn"
                        onClick={() => saveTarget(bucket)}
                        disabled={savingId === bucket.bucketId}
                      >
                        {savingId === bucket.bucketId ? '...' : '✓'}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
        {bucketError && <div className="error-msg">{bucketError}</div>}
      </div>

      {/* ---- Delete All Data ---- */}
      <div className="settings-section">
        <h3>🗑️ Delete All Data</h3>
        <p className="settings-desc">
          Permanently delete all transactions, buckets, merchant memories, monthly summaries,
          and uploaded files. <strong>This cannot be undone.</strong>
        </p>

        {result ? (
          <div className="delete-result">
            <div className="result-icon">🗑️</div>
            <h4>All data deleted</h4>
            <div className="delete-stats">
              <span>{result.deleted.transactions} transactions</span>
              <span>{result.deleted.buckets} buckets</span>
              <span>{result.deleted.merchants} merchants</span>
              <span>{result.deleted.summaries} summaries</span>
              <span>{result.deleted.s3_objects} files</span>
            </div>
            <p className="settings-desc">Upload new statements to start fresh.</p>
          </div>
        ) : !confirming ? (
          <button
            className="danger-btn"
            onClick={() => setConfirming(true)}
          >
            Delete All Data
          </button>
        ) : (
          <div className="delete-confirm">
            <p className="confirm-warning">
              ⚠️ Type <strong>DELETE</strong> to confirm permanent removal of all data:
            </p>
            <div className="confirm-actions">
              <input
                type="text"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder='Type "DELETE"'
                autoFocus
              />
              <button
                className="danger-btn"
                onClick={handleDelete}
                disabled={typed !== 'DELETE' || deleting}
              >
                {deleting ? 'Deleting...' : 'Confirm Delete'}
              </button>
              <button
                className="secondary-btn"
                onClick={() => { setConfirming(false); setTyped('') }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}
      </div>
    </div>
  )
}

import React, { useState } from 'react'
import { api } from '../api'

export default function SettingsPage() {
  const [confirming, setConfirming] = useState(false)
  const [typed, setTyped] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

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
      <p className="page-subtitle">Manage your data and preferences.</p>

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

import React, { useState, useCallback } from 'react'
import { api } from '../api'

export default function UploadPage({ monthKey, setPage }) {
  const [file, setFile] = useState(null)
  const [source, setSource] = useState('bank')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f && f.name.endsWith('.csv')) {
      setFile(f)
      setError('')
    } else {
      setError('Please drop a .csv file')
    }
  }, [])

  const handleFileSelect = (e) => {
    const f = e.target.files[0]
    if (f) {
      setFile(f)
      setError('')
    }
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setError('')
    setResult(null)

    try {
      const text = await file.text()
      const data = await api.upload(file.name, source, text)
      setResult(data)
      setFile(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="upload-page">
      <h2>Upload Statements</h2>
      <p className="page-subtitle">
        Drop your bank or credit card CSV below. We'll handle the rest.
      </p>

      <div className="source-toggle">
        <button
          className={source === 'bank' ? 'active' : ''}
          onClick={() => setSource('bank')}
        >
          🏦 Bank Statement
        </button>
        <button
          className={source === 'credit_card' ? 'active' : ''}
          onClick={() => setSource('credit_card')}
        >
          💳 Credit Card
        </button>
      </div>

      <div
        className={`drop-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-input').click()}
      >
        <input
          id="file-input"
          type="file"
          accept=".csv"
          onChange={handleFileSelect}
          hidden
        />
        {file ? (
          <div className="file-preview">
            <div className="file-icon">📄</div>
            <div className="file-name">{file.name}</div>
            <div className="file-size">{(file.size / 1024).toFixed(1)} KB</div>
          </div>
        ) : (
          <div className="drop-prompt">
            <div className="drop-icon">📂</div>
            <div>Drop your CSV here, or click to browse</div>
          </div>
        )}
      </div>

      {error && <div className="error-msg">{error}</div>}

      {file && !result && (
        <button
          className="primary-btn upload-btn"
          onClick={handleUpload}
          disabled={uploading}
        >
          {uploading ? 'Processing... 🔄' : `Upload ${source === 'bank' ? '🏦' : '💳'} Statement`}
        </button>
      )}

      {result && (
        <div className="upload-result">
          <div className="result-icon">✅</div>
          <h3>Upload complete!</h3>
          <div className="result-stats">
            <div className="result-stat">
              <span className="result-value">{result.transactionsProcessed}</span>
              <span>transactions processed</span>
            </div>
            <div className="result-stat">
              <span className="result-value">{result.needsReview}</span>
              <span>need review</span>
            </div>
            <div className="result-stat">
              <span className="result-value">${Math.abs(result.totalAmount).toLocaleString()}</span>
              <span>total</span>
            </div>
          </div>
          <div className="result-actions">
            {result.needsReview > 0 ? (
              <button className="primary-btn" onClick={() => setPage('review')}>
                Review {result.needsReview} items →
              </button>
            ) : (
              <button className="primary-btn" onClick={() => setPage('dashboard')}>
                View Dashboard →
              </button>
            )}
            <button className="secondary-btn" onClick={() => { setResult(null); setFile(null) }}>
              Upload another file
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

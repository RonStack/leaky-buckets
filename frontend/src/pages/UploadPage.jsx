import React, { useState, useCallback } from 'react'
import { api } from '../api'

const SOURCES = {
  bank: { label: '🏦 Bank Statement' },
  credit_card: { label: '💳 Credit Card' },
  paystub: { label: '📄 Paystub' },
}

const ACCEPTED_EXTENSIONS = ['.csv', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp']
const ACCEPTED_STRING = ACCEPTED_EXTENSIONS.join(',')

export default function UploadPage({ monthKey, setPage }) {
  const [file, setFile] = useState(null)
  const [source, setSource] = useState('bank')
  const [paystubSource, setPaystubSource] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [paystubResult, setPaystubResult] = useState(null)
  const [error, setError] = useState('')

  const isPaystub = source === 'paystub'

  function getFileType(file) {
    if (!file) return null
    const ext = file.name.split('.').pop().toLowerCase()
    if (ext === 'csv') return 'csv'
    if (ext === 'pdf') return 'pdf'
    if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return 'image'
    return null
  }

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) {
      const ext = f.name.split('.').pop().toLowerCase()
      if (ACCEPTED_EXTENSIONS.some(a => a.slice(1) === ext)) {
        setFile(f)
        setError('')
      } else {
        setError('Unsupported file type. Use CSV, PDF, or image (PNG/JPG).')
      }
    }
  }, [])

  const handleFileSelect = (e) => {
    const f = e.target.files[0]
    if (f) {
      setFile(f)
      setError('')
    }
  }

  function handleSourceChange(newSource) {
    setSource(newSource)
    setFile(null)
    setResult(null)
    setPaystubResult(null)
    setError('')
  }

  async function readFileAsBase64(f) {
    const arrayBuffer = await f.arrayBuffer()
    return btoa(
      new Uint8Array(arrayBuffer).reduce((data, byte) => data + String.fromCharCode(byte), '')
    )
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setError('')
    setResult(null)
    setPaystubResult(null)

    const fileType = getFileType(file)

    try {
      if (isPaystub) {
        // Paystub: PDF or image → base64 → paystub endpoint
        const base64 = await readFileAsBase64(file)
        const data = await api.uploadPaystub(file.name, paystubSource || 'Primary Job', base64)
        setPaystubResult(data)
        setFile(null)
      } else if (fileType === 'csv') {
        // Statement CSV: read as text → upload endpoint
        const text = await file.text()
        const data = await api.upload(file.name, source, text)
        setResult(data)
        setFile(null)
      } else {
        // Statement PDF/image: read as base64 → upload endpoint
        const base64 = await readFileAsBase64(file)
        const data = await api.uploadFile(file.name, source, base64)
        setResult(data)
        setFile(null)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="upload-page">
      <h2>Upload</h2>
      <p className="page-subtitle">
        Drop your statements or paystubs below. We'll handle the rest.
      </p>

      <div className="source-toggle">
        {Object.entries(SOURCES).map(([key, { label }]) => (
          <button
            key={key}
            className={source === key ? 'active' : ''}
            onClick={() => handleSourceChange(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {isPaystub && (
        <div className="paystub-source-input">
          <label>Income source name:</label>
          <input
            type="text"
            value={paystubSource}
            onChange={(e) => setPaystubSource(e.target.value)}
            placeholder="e.g., Primary Job, Side Gig, Freelance"
          />
        </div>
      )}

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
          accept={ACCEPTED_STRING}
          onChange={handleFileSelect}
          hidden
          key={source} // Reset input when source changes
        />
        {file ? (
          <div className="file-preview">
            <div className="file-icon">{isPaystub ? '📄' : '📊'}</div>
            <div className="file-name">{file.name}</div>
            <div className="file-size">{(file.size / 1024).toFixed(1)} KB</div>
          </div>
        ) : (
          <div className="drop-prompt">
            <div className="drop-icon">{isPaystub ? '📄' : '📂'}</div>
            <div>Drop your {isPaystub ? 'paystub' : 'statement'} here (CSV, PDF, or image)</div>
          </div>
        )}
      </div>

      {error && <div className="error-msg">{error}</div>}

      {file && !result && !paystubResult && (
        <button
          className="primary-btn upload-btn"
          onClick={handleUpload}
          disabled={uploading}
        >
          {uploading
            ? (isPaystub ? 'Parsing paystub with AI... 🤖' : (getFileType(file) === 'csv' ? 'Processing... 🔄' : 'Extracting transactions with AI... 🤖'))
            : `Upload ${SOURCES[source].label}`}
        </button>
      )}

      {/* CSV upload result */}
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

      {/* Paystub result */}
      {paystubResult && (
        <div className="upload-result paystub-result">
          <div className="result-icon">🚰</div>
          <h3>Paystub parsed!</h3>
          <p className="paystub-employer">{paystubResult.parsed.employer} — {paystubResult.parsed.payDate}</p>
          <div className="paystub-breakdown">
            <div className="paystub-line gross">
              <span>🚰 Gross Pay</span>
              <span className="paystub-amount">${paystubResult.parsed.grossPay.toLocaleString()}</span>
            </div>
            <div className="paystub-divider" />
            <div className="paystub-line">
              <span>🏛️ Federal Tax</span>
              <span className="paystub-amount deduction">-${paystubResult.parsed.federalTax.toLocaleString()}</span>
            </div>
            <div className="paystub-line">
              <span>🏛️ State Tax</span>
              <span className="paystub-amount deduction">-${paystubResult.parsed.stateTax.toLocaleString()}</span>
            </div>
            <div className="paystub-line">
              <span>🏛️ FICA / Medicare</span>
              <span className="paystub-amount deduction">-${paystubResult.parsed.ficaMedicare.toLocaleString()}</span>
            </div>
            <div className="paystub-line">
              <span>📈 Retirement (401k/IRA)</span>
              <span className="paystub-amount deduction">-${paystubResult.parsed.retirement.toLocaleString()}</span>
            </div>
            <div className="paystub-line">
              <span>🏥 HSA / FSA</span>
              <span className="paystub-amount deduction">-${paystubResult.parsed.hsaFsa.toLocaleString()}</span>
            </div>
            {paystubResult.parsed.debtPayments > 0 && (
              <div className="paystub-line">
                <span>💳 Debt Payments</span>
                <span className="paystub-amount deduction">-${paystubResult.parsed.debtPayments.toLocaleString()}</span>
              </div>
            )}
            {paystubResult.parsed.otherDeductions > 0 && (
              <div className="paystub-line">
                <span>📋 Other Deductions</span>
                <span className="paystub-amount deduction">-${paystubResult.parsed.otherDeductions.toLocaleString()}</span>
              </div>
            )}
            <div className="paystub-divider" />
            <div className="paystub-line net">
              <span>💧 Take-Home Pay</span>
              <span className="paystub-amount">${paystubResult.parsed.netPay.toLocaleString()}</span>
            </div>
          </div>
          <div className="result-actions">
            <button className="primary-btn" onClick={() => setPage('dashboard')}>
              View Dashboard →
            </button>
            <button className="secondary-btn" onClick={() => { setPaystubResult(null); setFile(null) }}>
              Upload another paystub
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

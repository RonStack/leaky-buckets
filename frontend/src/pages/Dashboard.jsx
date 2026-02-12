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

export default function Dashboard({ monthKey, setPage, mode }) {
  const [summary, setSummary] = useState(null)
  const [income, setIncome] = useState(null)
  const [liveData, setLiveData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [recurringStatus, setRecurringStatus] = useState(null) // { hasBills, alreadyApplied }
  const [applyingBills, setApplyingBills] = useState(false)

  const isLive = mode === 'live'

  useEffect(() => {
    if (isLive) {
      loadLiveData()
    } else {
      seedAndLoad()
    }
  }, [monthKey, isLive])

  async function seedAndLoad() {
    setLoading(true)
    setError('')
    try {
      await api.seedBuckets()
      const monthData = await api.getMonthSummary(monthKey)
      setSummary(monthData)

      // Paystubs may not be deployed yet — don't break the page
      try {
        const incomeData = await api.getPaystubs(monthKey)
        setIncome(incomeData)
      } catch {
        setIncome(null)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadLiveData() {
    setLoading(true)
    setError('')
    try {
      await api.seedBuckets()
      const data = await api.getLiveExpenses(monthKey)
      // Also load buckets for emoji/target data
      const bucketData = await api.getBuckets()
      const bucketList = bucketData.buckets || bucketData || []

      // Check recurring bills status
      try {
        const rbData = await api.getRecurringBills()
        const rbBills = rbData.bills || []
        if (rbBills.length > 0) {
          // Check if any have already been applied this month
          const expenses = data.expenses || []
          const appliedIds = new Set(
            expenses
              .filter(e => e.source === 'recurring' && e.recurringBillId)
              .map(e => e.recurringBillId)
          )
          const allApplied = rbBills.every(b => appliedIds.has(b.billId))
          setRecurringStatus({ hasBills: true, alreadyApplied: allApplied, count: rbBills.length })
        } else {
          setRecurringStatus({ hasBills: false, alreadyApplied: false, count: 0 })
        }
      } catch {
        setRecurringStatus(null)
      }

      // Merge live totals with bucket metadata
      const bucketMap = {}
      for (const b of bucketList) {
        bucketMap[b.bucketId] = b
      }

      const liveBuckets = bucketList.map(b => {
        const liveTot = (data.bucketTotals || []).find(t => t.bucketId === b.bucketId)
        const spent = liveTot ? liveTot.total : 0
        const count = liveTot ? liveTot.count : 0
        const target = b.target || 0
        let status = 'stable'
        if (target > 0) {
          const pct = spent / target
          if (pct >= 1) status = 'overflowing'
          else if (pct >= 0.7) status = 'dripping'
        }
        return {
          bucketId: b.bucketId,
          name: b.name,
          emoji: b.emoji,
          target,
          spent: Math.round(spent * 100) / 100,
          count,
          status,
        }
      })

      setLiveData({
        totalSpent: data.totalSpent || 0,
        count: data.count || 0,
        buckets: liveBuckets,
        expenses: data.expenses || [],
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="loading">Loading your buckets... 🪣</div>
  if (error) return <div className="error-box">{error}</div>

  async function handleApplyRecurring() {
    setApplyingBills(true)
    try {
      const result = await api.applyRecurringBills(monthKey)
      setRecurringStatus(prev => ({ ...prev, alreadyApplied: true }))
      await loadLiveData()
    } catch (err) {
      setError(err.message)
    } finally {
      setApplyingBills(false)
    }
  }

  // ── Live Mode Dashboard ──
  if (isLive) {
    if (!liveData) return null
    const hasExpenses = liveData.count > 0

    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h2>
            ⚡ {getMonthLabel(monthKey)}
            <span className="mode-badge live-badge">Live</span>
          </h2>
          {hasExpenses && (
            <div className="summary-stats">
              <div className="stat">
                <span className="stat-value">${liveData.totalSpent.toLocaleString()}</span>
                <span className="stat-label">recorded</span>
              </div>
              <div className="stat">
                <span className="stat-value">{liveData.count}</span>
                <span className="stat-label">expenses</span>
              </div>
            </div>
          )}
        </div>

        {!hasExpenses ? (
          <div className="empty-state">
            <div className="empty-icon">⚡</div>
            <h3>No live expenses for {getMonthLabel(monthKey)}</h3>
            <p>Start recording expenses as they happen.</p>
            {recurringStatus?.hasBills && !recurringStatus?.alreadyApplied && (
              <button
                className="recurring-apply-btn"
                onClick={handleApplyRecurring}
                disabled={applyingBills}
              >
                {applyingBills ? 'Applying...' : `🔁 Apply ${recurringStatus.count} Recurring Bill${recurringStatus.count !== 1 ? 's' : ''}`}
              </button>
            )}
            <button className="primary-btn" onClick={() => setPage('live')}>
              Add Expense →
            </button>
          </div>
        ) : (
          <>
            {/* Recurring bills prompt */}
            {recurringStatus?.hasBills && !recurringStatus?.alreadyApplied && (
              <div className="recurring-banner">
                <span className="recurring-banner-icon">🔁</span>
                <span className="recurring-banner-text">
                  You have {recurringStatus.count} recurring bill{recurringStatus.count !== 1 ? 's' : ''} not yet applied to {getMonthLabel(monthKey)}.
                </span>
                <button
                  className="recurring-apply-btn"
                  onClick={handleApplyRecurring}
                  disabled={applyingBills}
                >
                  {applyingBills ? 'Applying...' : 'Apply Now'}
                </button>
              </div>
            )}
            <div className="bucket-grid">
              {[...liveData.buckets]
                .filter(b => b.spent > 0)
                .sort((a, b) => b.spent - a.spent)
                .map((bucket, idx) => (
                  <BucketCard key={bucket.bucketId} bucket={bucket} rank={idx} onSetPage={setPage} />
                ))}
            </div>

            <div className="cta-bar">
              <button className="primary-btn" onClick={() => setPage('live')}>
                Add Another Expense ⚡
              </button>
            </div>
          </>
        )}
      </div>
    )
  }

  // ── Statements Mode Dashboard (original) ──
  if (!summary) return null

  const hasTransactions = summary.transactionCount > 0
  const hasIncome = income && income.count > 0
  const hasAnyData = hasTransactions || hasIncome

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>
          {getMonthLabel(monthKey)}
          {summary.locked && <span className="locked-badge">🔒 Locked</span>}
        </h2>
        {hasAnyData && (
          <div className="summary-stats">
            {hasIncome && (
              <div className="stat">
                <span className="stat-value">${income.totals.grossPay.toLocaleString()}</span>
                <span className="stat-label">earned</span>
              </div>
            )}
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

      {/* 🚰 The Faucet — Income Waterfall */}
      {hasIncome && <FaucetSection income={income} />}

      {!hasAnyData ? (
        <div className="empty-state">
          <div className="empty-icon">🪣</div>
          <h3>No data yet for {getMonthLabel(monthKey)}</h3>
          <p>Upload your paystubs, bank & credit card statements to get started.</p>
          <button className="primary-btn" onClick={() => setPage('upload')}>
            Upload →
          </button>
        </div>
      ) : (
        <>
          {hasTransactions && (
            <div className="bucket-grid">
              {[...summary.buckets]
                .sort((a, b) => b.spent - a.spent)
                .map((bucket, idx) => (
                  <BucketCard key={bucket.bucketId} bucket={bucket} rank={idx} onSetPage={setPage} />
                ))}
            </div>
          )}

          {!hasTransactions && hasIncome && (
            <div className="empty-state" style={{ paddingTop: '24px' }}>
              <h3>No spending data yet</h3>
              <p>Upload your bank & credit card statements to see your buckets fill up.</p>
              <button className="primary-btn" onClick={() => setPage('upload')}>
                Upload Statements →
              </button>
            </div>
          )}

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

function FaucetSection({ income }) {
  const t = income.totals
  const gross = t.grossPay || 0
  const federalTax = t.federalTax || 0
  const stateTax = t.stateTax || 0
  const fica = t.ficaMedicare || 0
  const retirement = t.retirement || 0
  const hsa = t.hsaFsa || 0
  const debt = t.debtPayments || 0
  const other = t.otherDeductions || 0
  const net = t.netPay || 0

  const totalTaxes = federalTax + stateTax + fica
  const totalInvesting = retirement + hsa
  const totalPreTakeHome = totalTaxes + totalInvesting + debt + other

  // Each waterfall row shows what's removed and what remains
  const rows = [
    { label: '🏛️ Taxes', sub: 'Federal + State + FICA', amount: totalTaxes, items: [
      { label: 'Federal', amount: federalTax },
      { label: 'State', amount: stateTax },
      { label: 'FICA / Medicare', amount: fica },
    ]},
    { label: '📈 Investing', sub: '401k / IRA / HSA', amount: totalInvesting, items: [
      { label: 'Retirement', amount: retirement },
      { label: 'HSA / FSA', amount: hsa },
    ]},
    { label: '💳 Debt Payments', sub: 'Loans', amount: debt, items: [] },
    { label: '📋 Other Deductions', sub: '', amount: other, items: [] },
  ].filter(r => r.amount > 0)

  return (
    <div className="faucet-section">
      <div className="faucet-header">
        <div className="faucet-icon">🚰</div>
        <div>
          <h3>The Faucet</h3>
          <p className="faucet-subtitle">Where your money goes before it reaches your buckets</p>
        </div>
      </div>

      {/* Gross income */}
      <div className="faucet-gross">
        <span className="faucet-gross-label">Gross Income</span>
        <span className="faucet-gross-amount">${gross.toLocaleString()}</span>
        <span className="faucet-count">{income.count} paystub{income.count !== 1 ? 's' : ''}</span>
      </div>

      <div className="faucet-flow-arrow">▼</div>

      {/* Deduction rows */}
      <div className="faucet-waterfall">
        {rows.map((row, i) => (
          <WaterfallRow key={i} row={row} gross={gross} />
        ))}
      </div>

      <div className="faucet-flow-arrow">▼</div>

      {/* Take-home */}
      <div className="faucet-takehome">
        <span className="faucet-takehome-label">💧 Take-Home Pay</span>
        <span className="faucet-takehome-amount">${net.toLocaleString()}</span>
        <span className="faucet-takehome-pct">
          {gross > 0 ? Math.round((net / gross) * 100) : 0}% of gross
        </span>
      </div>

      <div className="faucet-flow-arrow faucet-into-buckets">▼ flows into your buckets ▼</div>

      {/* Drip animation */}
      <div className="drip-container">
        <div className="drip drip-1" />
        <div className="drip drip-2" />
        <div className="drip drip-3" />
      </div>
    </div>
  )
}

function WaterfallRow({ row, gross }) {
  const pct = gross > 0 ? Math.round((row.amount / gross) * 100) : 0
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="waterfall-row">
      <div className="waterfall-row-main" onClick={() => row.items.length > 0 && setExpanded(!expanded)}>
        <span className="waterfall-label">
          {row.label}
          {row.items.length > 0 && <span className="waterfall-expand">{expanded ? '▾' : '▸'}</span>}
        </span>
        <span className="waterfall-amount">−${row.amount.toLocaleString()}</span>
        <span className="waterfall-pct">{pct}%</span>
      </div>
      <div className="waterfall-bar">
        <div className="waterfall-bar-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      {expanded && row.items.length > 0 && (
        <div className="waterfall-details">
          {row.items.filter(it => it.amount > 0).map((item, j) => (
            <div key={j} className="waterfall-detail-row">
              <span>{item.label}</span>
              <span>${item.amount.toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function BucketCard({ bucket, rank, onSetPage }) {
  const pct = bucket.target > 0
    ? Math.min(Math.round((bucket.spent / bucket.target) * 100), 150)
    : 0
  const fillHeight = bucket.target > 0 ? Math.min(pct, 100) : Math.min(bucket.spent / 10, 80)

  // Water color based on status
  const waterColor = bucket.status === 'overflowing'
    ? 'rgba(239, 83, 80, 0.35)'
    : bucket.status === 'dripping'
      ? 'rgba(255, 193, 7, 0.3)'
      : 'rgba(91, 141, 239, 0.25)'

  const waterColorSolid = bucket.status === 'overflowing'
    ? 'rgba(239, 83, 80, 0.55)'
    : bucket.status === 'dripping'
      ? 'rgba(255, 193, 7, 0.5)'
      : 'rgba(91, 141, 239, 0.4)'

  return (
    <div className={`bucket-card bucket-${bucket.status}`} style={{ '--water-height': `${fillHeight}%`, '--water-color': waterColor, '--water-color-solid': waterColorSolid, '--fill-delay': `${rank * 0.15}s` }}>
      {/* Overflow drips */}
      {bucket.status === 'overflowing' && (
        <div className="bucket-overflow-drips">
          <div className="overflow-drip overflow-drip-1" />
          <div className="overflow-drip overflow-drip-2" />
        </div>
      )}

      {/* Water fill */}
      <div className="bucket-water">
        <div className="bucket-water-surface" />
      </div>

      {/* Content on top of water */}
      <div className="bucket-content">
        <div className="bucket-header">
          <span className="bucket-emoji">{bucket.emoji}</span>
          <span className="bucket-status">{STATUS_EMOJI[bucket.status]}</span>
        </div>
        <h3 className="bucket-name">{bucket.name}</h3>
        <div className="bucket-amount">${bucket.spent.toLocaleString()}</div>
        {bucket.target > 0 ? (
          <div className="bucket-target">of ${bucket.target.toLocaleString()} ({pct}%)</div>
        ) : (
          <div
            className="bucket-no-target"
            onClick={() => onSetPage('settings')}
            title="Set a monthly target in Settings"
          >
            Set a target →
          </div>
        )}
        <div className="bucket-footer">
          <span className="bucket-status-label">{STATUS_LABEL[bucket.status]}</span>
          <span className="bucket-count">{bucket.count} txn{bucket.count !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </div>
  )
}

function getMonthLabel(monthKey) {
  const [year, month] = monthKey.split('-')
  const date = new Date(parseInt(year), parseInt(month) - 1, 1)
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

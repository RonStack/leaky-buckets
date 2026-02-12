import React, { useState, useEffect } from 'react'
import { isLoggedIn, logout, getCurrentUser } from './auth'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import UploadPage from './pages/UploadPage'
import ReviewPage from './pages/ReviewPage'
import SettingsPage from './pages/SettingsPage'
import LiveExpensePage from './pages/LiveExpensePage'
import RecurringBillsPage from './pages/RecurringBillsPage'

const PAGES = {
  dashboard: Dashboard,
  upload: UploadPage,
  review: ReviewPage,
  settings: SettingsPage,
  live: LiveExpensePage,
  recurring: RecurringBillsPage,
}

export default function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn())
  const [page, setPage] = useState('dashboard')
  const [monthKey, setMonthKey] = useState(getCurrentMonthKey())
  const [mode, setMode] = useState('statements') // 'statements' or 'live'

  if (!loggedIn) {
    return <LoginPage onLogin={() => setLoggedIn(true)} />
  }

  const Page = PAGES[page] || Dashboard

  // In Live mode, dashboard shows live data; other pages stay the same
  const isLive = mode === 'live'

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1 onClick={() => setPage('dashboard')}>🪣 Leaky Buckets</h1>
        </div>

        {/* Mode Toggle */}
        <div className="mode-toggle">
          <button
            className={mode === 'statements' ? 'active' : ''}
            onClick={() => { setMode('statements'); setPage('dashboard') }}
          >
            📊 Statements
          </button>
          <button
            className={mode === 'live' ? 'active' : ''}
            onClick={() => { setMode('live'); setPage('dashboard') }}
          >
            ⚡ Live
          </button>
        </div>

        <nav className="header-nav">
          <button
            className={page === 'dashboard' ? 'active' : ''}
            onClick={() => setPage('dashboard')}
          >
            Dashboard
          </button>
          {isLive ? (
            <>
              <button
                className={page === 'live' ? 'active' : ''}
                onClick={() => setPage('live')}
              >
                Add Expense
              </button>
              <button
                className={page === 'recurring' ? 'active' : ''}
                onClick={() => setPage('recurring')}
              >
                Recurring
              </button>
            </>
          ) : (
            <>
              <button
                className={page === 'upload' ? 'active' : ''}
                onClick={() => setPage('upload')}
              >
                Upload
              </button>
              <button
                className={page === 'review' ? 'active' : ''}
                onClick={() => setPage('review')}
              >
                Review
              </button>
            </>
          )}
          <button
            className={page === 'settings' ? 'active' : ''}
            onClick={() => setPage('settings')}
          >
            Settings
          </button>
        </nav>
        <div className="header-right">
          <select
            value={monthKey}
            onChange={(e) => setMonthKey(e.target.value)}
            className="month-picker"
          >
            {getMonthOptions().map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
          <span className="user-badge">{getCurrentUser()}</span>
          <button className="logout-btn" onClick={() => { logout(); setLoggedIn(false) }}>
            Sign out
          </button>
        </div>
      </header>

      <main className="app-main">
        <Page monthKey={monthKey} setPage={setPage} mode={mode} />
      </main>
    </div>
  )
}

function getCurrentMonthKey() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function getMonthOptions() {
  const options = []
  const now = new Date()
  // 3 future months + current + 11 past months
  for (let i = -3; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    options.push({ value, label })
  }
  return options
}

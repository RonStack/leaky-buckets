import React, { useState, useEffect } from 'react'
import { isLoggedIn, logout, getCurrentUser } from './auth'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import UploadPage from './pages/UploadPage'
import ReviewPage from './pages/ReviewPage'

const PAGES = {
  dashboard: Dashboard,
  upload: UploadPage,
  review: ReviewPage,
}

export default function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn())
  const [page, setPage] = useState('dashboard')
  const [monthKey, setMonthKey] = useState(getCurrentMonthKey())

  if (!loggedIn) {
    return <LoginPage onLogin={() => setLoggedIn(true)} />
  }

  const Page = PAGES[page] || Dashboard

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1 onClick={() => setPage('dashboard')}>🪣 Leaky Buckets</h1>
        </div>
        <nav className="header-nav">
          <button
            className={page === 'dashboard' ? 'active' : ''}
            onClick={() => setPage('dashboard')}
          >
            Dashboard
          </button>
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
        <Page monthKey={monthKey} setPage={setPage} />
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
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    options.push({ value, label })
  }
  return options
}

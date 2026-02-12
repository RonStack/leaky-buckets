import React, { useState } from 'react'
import { isLoggedIn, logout, getCurrentUser } from './auth'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import LogSpend from './pages/LogSpend'
import MonthSummary from './pages/MonthSummary'
import Settings from './pages/Settings'

function getCurrentMonthKey() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const PAGES = {
  dashboard: Dashboard,
  logspend: LogSpend,
  summary: MonthSummary,
  settings: Settings,
}

export default function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn())
  const [page, setPage] = useState('dashboard')
  const [refreshKey, setRefreshKey] = useState(0)

  if (!loggedIn) {
    return <LoginPage onLogin={() => setLoggedIn(true)} />
  }

  const Page = PAGES[page] || Dashboard

  const navigate = (p) => setPage(p)
  const refresh = () => setRefreshKey((k) => k + 1)

  return (
    <div className="app">
      <header className="app-header">
        <h1 onClick={() => navigate('dashboard')}>🧰 ChestCheck</h1>
        <nav className="header-nav">
          <button className={page === 'dashboard' ? 'active' : ''} onClick={() => navigate('dashboard')}>
            Home
          </button>
          <button className={page === 'summary' ? 'active' : ''} onClick={() => navigate('summary')}>
            Summary
          </button>
          <button className={page === 'settings' ? 'active' : ''} onClick={() => navigate('settings')}>
            Settings
          </button>
        </nav>
        <div className="header-right">
          <span className="user-badge">{getCurrentUser()}</span>
          <button className="logout-btn" onClick={() => { logout(); setLoggedIn(false) }}>
            Sign out
          </button>
        </div>
      </header>

      <main className="app-main">
        <Page
          navigate={navigate}
          refresh={refresh}
          refreshKey={refreshKey}
        />
      </main>
    </div>
  )
}

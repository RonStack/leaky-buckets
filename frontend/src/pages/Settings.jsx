import React, { useState, useEffect } from 'react'
import { api } from '../api'

function formatDollars(cents) {
  return `$${(cents / 100).toFixed(2)}`
}

export default function Settings() {
  const [categories, setCategories] = useState([])
  const [household, setHousehold] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  // New category form
  const [newName, setNewName] = useState('')
  const [newEmoji, setNewEmoji] = useState('📦')
  const [newLimit, setNewLimit] = useState('')

  // Join household
  const [joinCode, setJoinCode] = useState('')

  // Edit state
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editEmoji, setEditEmoji] = useState('')
  const [editLimit, setEditLimit] = useState('')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [me, catData] = await Promise.all([
        api.getMe(),
        api.getCategories(),
      ])
      setHousehold(me.household || null)
      setCategories(catData.categories || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleAddCategory(e) {
    e.preventDefault()
    setError('')
    setMsg('')
    const limitCents = Math.round(parseFloat(newLimit) * 100)
    if (!newName.trim()) return setError('Name required')
    if (!limitCents || limitCents <= 0) return setError('Valid limit required')

    try {
      await api.createCategory({
        name: newName.trim(),
        emoji: newEmoji,
        monthlyLimitCents: limitCents,
      })
      setNewName('')
      setNewEmoji('📦')
      setNewLimit('')
      setMsg('Category added!')
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleUpdateCategory(catId) {
    setError('')
    setMsg('')
    const updates = {}
    if (editName.trim()) updates.name = editName.trim()
    if (editEmoji) updates.emoji = editEmoji
    if (editLimit) {
      const cents = Math.round(parseFloat(editLimit) * 100)
      if (cents > 0) updates.monthlyLimitCents = cents
    }

    try {
      await api.updateCategory(catId, updates)
      setEditingId(null)
      setMsg('Updated!')
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleToggleActive(cat) {
    try {
      await api.updateCategory(cat.categoryId, { isActive: !cat.isActive })
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleJoinHousehold(e) {
    e.preventDefault()
    setError('')
    setMsg('')
    if (!joinCode.trim()) return setError('Enter a household code')
    try {
      await api.joinHousehold(joinCode.trim())
      setJoinCode('')
      setMsg('Joined household!')
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleDeleteAll() {
    if (!window.confirm('Delete ALL categories and transactions? This cannot be undone.')) return
    try {
      await api.deleteAllData()
      setMsg('All data deleted.')
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <div className="loading">Loading…</div>

  return (
    <div className="settings">
      <h2>Settings</h2>

      {error && <div className="error-msg">{error}</div>}
      {msg && <div className="toast">{msg}</div>}

      {/* Household info */}
      <section className="settings-section">
        <h3>🏠 Household</h3>
        {household ? (
          <div className="household-info">
            <p><strong>Household ID:</strong> <code>{household.householdId}</code></p>
            <p className="hint">Share this code with your partner to join the same household.</p>
            <p><strong>Members:</strong> {(household.members || []).length}</p>
          </div>
        ) : (
          <p>No household found.</p>
        )}

        <form onSubmit={handleJoinHousehold} className="join-form">
          <input
            type="text"
            placeholder="Household code"
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value)}
            maxLength={8}
          />
          <button type="submit">Join</button>
        </form>
      </section>

      {/* Manage categories */}
      <section className="settings-section">
        <h3>🧰 Treasure Chests</h3>
        <div className="category-list">
          {categories.map((cat) => (
            <div key={cat.categoryId} className={`cat-row ${cat.isActive === false ? 'inactive' : ''}`}>
              {editingId === cat.categoryId ? (
                <div className="cat-edit">
                  <input value={editEmoji} onChange={(e) => setEditEmoji(e.target.value)} className="emoji-input" />
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Name" />
                  <input
                    type="number"
                    value={editLimit}
                    onChange={(e) => setEditLimit(e.target.value)}
                    placeholder="Limit ($)"
                    step="1"
                    min="1"
                  />
                  <button onClick={() => handleUpdateCategory(cat.categoryId)}>Save</button>
                  <button onClick={() => setEditingId(null)}>✕</button>
                </div>
              ) : (
                <>
                  <span className="cat-emoji">{cat.emoji}</span>
                  <span className="cat-name">{cat.name}</span>
                  <span className="cat-limit">{formatDollars(cat.monthlyLimitCents)}/mo</span>
                  <button
                    className="edit-btn"
                    onClick={() => {
                      setEditingId(cat.categoryId)
                      setEditName(cat.name)
                      setEditEmoji(cat.emoji)
                      setEditLimit((cat.monthlyLimitCents / 100).toFixed(0))
                    }}
                  >
                    ✏️
                  </button>
                  <button className="toggle-btn" onClick={() => handleToggleActive(cat)}>
                    {cat.isActive !== false ? '🟢' : '⚪'}
                  </button>
                </>
              )}
            </div>
          ))}
        </div>

        {/* Add new category */}
        <form onSubmit={handleAddCategory} className="add-cat-form">
          <input
            className="emoji-input"
            value={newEmoji}
            onChange={(e) => setNewEmoji(e.target.value)}
            maxLength={4}
          />
          <input
            placeholder="Category name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            required
          />
          <input
            type="number"
            placeholder="Limit ($)"
            value={newLimit}
            onChange={(e) => setNewLimit(e.target.value)}
            step="1"
            min="1"
            required
          />
          <button type="submit">+ Add</button>
        </form>
      </section>

      {/* PWA Install hint */}
      <section className="settings-section">
        <h3>📱 Install App</h3>
        <p className="hint">
          On iPhone: tap Share → "Add to Home Screen" to install ChestCheck as an app.
        </p>
      </section>

      {/* Danger zone */}
      <section className="settings-section danger-zone">
        <h3>⚠️ Danger Zone</h3>
        <button className="delete-btn" onClick={handleDeleteAll}>
          Delete All Data
        </button>
      </section>
    </div>
  )
}

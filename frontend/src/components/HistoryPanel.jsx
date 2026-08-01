import { useState, useEffect } from 'react'
import axios from 'axios'
import { Clock, X, FileSpreadsheet } from 'lucide-react'

const API = 'https://sage-v3-production.up.railway.app'

function fmtWhen(unixSeconds) {
  if (!unixSeconds) return ''
  const d = new Date(unixSeconds * 1000)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  return sameDay
    ? `Today · ${d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`
    : d.toLocaleDateString([], { month: 'short', day: 'numeric', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined })
}

export default function HistoryPanel({ onClose, onSelect, error }) {
  const [sessions, setSessions] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [openingId, setOpeningId] = useState(null)

  useEffect(() => {
    axios.get(`${API}/sessions`)
      .then(r => setSessions(r.data.sessions || []))
      .catch(() => setLoadError('Could not load past reports.'))
  }, [])

  async function handleSelect(id) {
    setOpeningId(id)
    await onSelect(id)
    setOpeningId(null)
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-sage-700/20 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-md h-full bg-white/95 backdrop-blur-xl border-l border-sage-200/50 shadow-2xl flex flex-col animate-fade-up"
        style={{ animationDuration: '0.25s' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-5 border-b border-sage-200/40">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sage-200 to-sage-100 flex items-center justify-center">
              <Clock size={16} className="text-sage-600" />
            </div>
            <div>
              <div className="text-sm font-medium text-sage-700">Past reports</div>
              <div className="text-xs text-sage-400">Reopen a dataset you analyzed before</div>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" className="w-8 h-8 rounded-full flex items-center justify-center text-sage-400 hover:bg-sage-100 hover:text-sage-600 transition">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {error && (
            <div className="mb-3 text-xs text-[color:#c0392b] bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</div>
          )}

          {sessions === null && !loadError && (
            <div className="text-sm text-sage-300 animate-pulse py-12 text-center">Loading past reports…</div>
          )}
          {loadError && <div className="text-sm text-sage-400 py-12 text-center">{loadError}</div>}
          {sessions?.length === 0 && (
            <div className="text-sm text-sage-400 py-16 text-center leading-relaxed">
              No past reports yet.<br />Upload a dataset to get started.
            </div>
          )}

          <div className="flex flex-col gap-2">
            {sessions?.map(s => (
              <button
                key={s.id}
                onClick={() => handleSelect(s.id)}
                disabled={openingId !== null}
                className="text-left px-4 py-3 rounded-xl border border-sage-200/50 bg-white/60 hover:bg-sage-50 hover:border-sage-300 transition disabled:opacity-50 flex items-start gap-3"
              >
                <div className="w-8 h-8 rounded-lg bg-sage-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <FileSpreadsheet size={14} className="text-sage-500" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-sage-700 truncate">{s.filename}</div>
                  <div className="text-xs text-sage-400 mt-0.5">
                    {s.rows?.toLocaleString()} rows · {s.cols} cols · {fmtWhen(s.uploaded_at)}
                  </div>
                </div>
                {openingId === s.id && <span className="ml-auto text-xs text-sage-400">Opening…</span>}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

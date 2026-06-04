import { useState, useRef } from 'react'
import axios from 'axios'

const API = 'http://localhost:8000'

export default function Landing({ onSessionStart }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef()

  async function handleFile(file) {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await axios.post(`${API}/upload`, form)
      onSessionStart(data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-4 bg-white/60 backdrop-blur border-b border-sage-200/30">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sage-200 to-rose-sage flex items-center justify-center text-lg">🌿</div>
          <div>
            <div className="text-sm font-medium text-sage-700">Sage</div>
            <div className="text-xs text-sage-400">Every dataset has a story. Sage tells it.</div>
          </div>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          className="text-xs px-4 py-2 rounded-full border border-sage-200 text-sage-500 hover:bg-sage-100 transition"
        >
          Try Sage free
        </button>
      </nav>

      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 text-center py-20">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sage-100 border border-sage-200 text-sage-500 text-xs mb-6">
          ✦ Voice-first analytics agent
        </div>
        <h1 className="text-5xl font-medium text-sage-700 leading-tight mb-4 max-w-2xl">
          Every dataset has a story.<br />
          <span className="bg-gradient-to-r from-sage-400 to-rose-deep bg-clip-text text-transparent">
            Sage tells it.
          </span>
        </h1>
        <p className="text-sage-400 text-lg mb-10 max-w-xl">
          Upload any dataset. Ask questions out loud. Hear the answers spoken back with the reasoning behind them.
        </p>

        {/* Upload zone */}
        <div
          onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); handleFile(e.dataTransfer.files[0]) }}
          onClick={() => inputRef.current?.click()}
          className="w-full max-w-md border-2 border-dashed border-sage-200 rounded-2xl p-10 cursor-pointer hover:border-sage-300 hover:bg-sage-50 transition text-center"
        >
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sage-200 to-rose-sage flex items-center justify-center text-2xl mx-auto mb-3">📊</div>
          <div className="text-sage-700 font-medium mb-1">
            {uploading ? 'Uploading...' : 'Drop your dataset here'}
          </div>
          <div className="text-sage-300 text-sm">CSV or Excel · up to 200MB</div>
          {error && <div className="text-red-400 text-sm mt-2">{error}</div>}
        </div>
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={e => handleFile(e.target.files[0])} />

        {/* Features */}
        <div className="grid grid-cols-3 gap-4 mt-16 max-w-2xl w-full">
          {[
            { icon: '🎤', title: 'Voice-first', desc: 'Speak your question, hear the answer' },
            { icon: '🧠', title: 'Reasons deeply', desc: '8 tools — SQL, trends, anomalies' },
            { icon: '📁', title: 'Any dataset', desc: 'CSV, Excel — no setup needed' },
          ].map(f => (
            <div key={f.title} className="bg-white/60 backdrop-blur border border-sage-200/50 rounded-xl p-4 text-left">
              <div className="text-2xl mb-2">{f.icon}</div>
              <div className="text-sm font-medium text-sage-700 mb-1">{f.title}</div>
              <div className="text-xs text-sage-400">{f.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'

const API = 'https://sage-v3-production.up.railway.app'
const COLORS = ['#7F77DD','#C8A8E9','#F9C4D2','#D4537E','#AFA9EC','#534AB7']

function fmt(v) {
  if (typeof v !== 'number') return v
  if (v >= 1000000) return `$${(v/1000000).toFixed(1)}M`
  if (v >= 1000) return `$${(v/1000).toFixed(0)}K`
  return v.toLocaleString()
}

function ChartCard({ title, children, onExplain }) {
  return (
    <div className="bg-white/70 backdrop-blur border border-sage-200/40 rounded-xl p-5 group">
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm font-medium text-sage-700">{title}</div>
        {onExplain && (
          <button onClick={onExplain} className="opacity-0 group-hover:opacity-100 transition text-xs px-3 py-1 rounded-full bg-gradient-to-r from-sage-200 to-rose-sage text-sage-600">
            🔊 Explain
          </button>
        )}
      </div>
      {children}
    </div>
  )
}

function Briefing({ session, mode }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get(`${API}/briefing/${session.session_id}`)
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [session.session_id])

  if (loading) return <div className="animate-pulse text-sage-300 text-sm p-4">Analyzing your dataset...</div>
  if (!data) return null

  if (mode === 'analyst') {
    return (
      <div className="bg-white/70 backdrop-blur border border-sage-200/40 rounded-xl p-5 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-medium px-2 py-1 rounded-full bg-sage-100 text-sage-500 border border-sage-200">Confidence: {data.confidence}%</span>
          <span className="text-xs text-sage-400">{data.rows?.toLocaleString()} rows reviewed · {data.cols} columns</span>
        </div>
        <div className="text-xs text-sage-400 font-medium uppercase tracking-wide mb-2">Tool readiness</div>
        <div className="flex flex-wrap gap-2">
          {['profile_data', 'anomaly_detect', 'top_n', 'time_series', 'run_sql', 'correlations'].map(t => (
            <span key={t} className="text-xs px-2 py-1 rounded bg-sage-50 text-sage-500 border border-sage-200">{t} ready</span>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 mb-6">
      {/* Confidence + summary */}
      <div className="bg-white/70 backdrop-blur border border-sage-200/40 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium text-sage-700">Sage Briefing</div>
          <span className="text-xs font-medium px-3 py-1 rounded-full bg-gradient-to-r from-sage-100 to-rose-sage/30 text-sage-600 border border-sage-200">
            Confidence: {data.confidence}%
          </span>
        </div>
        <p className="text-sm text-sage-600 leading-relaxed mb-4">{data.executive_summary}</p>
        <div className="grid grid-cols-2 gap-3">
          {/* Top 3 findings */}
          <div>
            <div className="text-xs font-medium text-sage-400 uppercase tracking-wide mb-2">Top findings</div>
            <div className="space-y-2">
              {data.findings?.map((f, i) => (
                <div key={i} className="flex gap-2 text-xs">
                  <span className="text-sage-300 mt-0.5">
                    {f.type === 'anomaly' ? '⚠️' : f.type === 'trend' ? '📈' : '🎯'}
                  </span>
                  <div>
                    <div className="font-medium text-sage-700">{f.title}</div>
                    <div className="text-sage-400 mt-0.5 leading-relaxed">{f.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          {/* Risk / Opportunity / Action */}
          <div className="space-y-2">
            {data.risk && (
              <div className="bg-rose-50 border border-rose-100 rounded-lg p-3">
                <div className="text-xs font-medium text-rose-600 mb-1">⚠ Risk</div>
                <div className="text-xs text-rose-500 leading-relaxed">{data.risk}</div>
              </div>
            )}
            {data.opportunity && (
              <div className="bg-green-50 border border-green-100 rounded-lg p-3">
                <div className="text-xs font-medium text-green-600 mb-1">✦ Opportunity</div>
                <div className="text-xs text-green-600 leading-relaxed">{data.opportunity}</div>
              </div>
            )}
            {data.action && (
              <div className="bg-sage-50 border border-sage-200 rounded-lg p-3">
                <div className="text-xs font-medium text-sage-600 mb-1">→ Recommended action</div>
                <div className="text-xs text-sage-500 leading-relaxed">{data.action}</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* What Sage noticed */}
      <div className="bg-white/70 backdrop-blur border border-sage-200/40 rounded-xl p-5">
        <div className="text-sm font-medium text-sage-700 mb-3">✦ What Sage noticed</div>
        <div className="space-y-2">
          {data.noticed?.map((n, i) => (
            <div key={i} className="flex gap-2 text-xs text-sage-600 leading-relaxed">
              <span className="text-sage-300 mt-0.5 flex-shrink-0">•</span>
              <span>{n}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Dashboard({ session, mode }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get(`${API}/dashboard-data/${session.session_id}`)
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [session.session_id])

  async function explainChart(title, chartData) {
    const summary = chartData.slice(0,5).map(d => `${d.name||d.bin}: ${d.value||d.count}`).join(', ')
    const { data: r } = await axios.post(`${API}/ask`, {
      question: `In 2 sentences explain this chart "${title}": ${summary}. Be specific with numbers.`,
      session_id: session.session_id
    })
    const { data: audio } = await axios.post(`${API}/speak`, { text: r.answer })
    if (audio.audio) new Audio(`data:audio/mp3;base64,${audio.audio}`).play()
  }

  if (loading) return <div className="p-8 text-center text-sage-300 animate-pulse">Loading dashboard...</div>
  if (!data) return null

  return (
    <div className="flex flex-col gap-5">
      <Briefing session={session} mode={mode} />

      {/* KPI strip */}
      <div className="grid grid-cols-5 gap-3">
        {data.kpis?.map((k,i) => (
          <div key={i} className="bg-white/70 backdrop-blur border border-sage-200/40 rounded-xl p-4">
            <div className="text-xs text-sage-300 uppercase tracking-wide mb-1">{k.label}</div>
            <div className="text-xl font-medium text-sage-700">{k.value}</div>
            <div className="text-xs text-sage-400 mt-1">{k.sub}</div>
          </div>
        ))}
      </div>

      {data.timeseries && (
        <ChartCard title={data.timeseries.title} onExplain={() => explainChart(data.timeseries.title, data.timeseries.data)}>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.timeseries.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(200,168,233,0.2)" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#afa9ec' }} interval="preserveStartEnd" />
              <YAxis tickFormatter={fmt} tick={{ fontSize: 10, fill: '#afa9ec' }} width={60} />
              <Tooltip formatter={fmt} contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '0.5px solid rgba(200,168,233,0.4)', borderRadius: '8px', fontSize: '12px' }} />
              <Line type="monotone" dataKey="value" stroke="#7F77DD" strokeWidth={2.5} dot={{ fill: 'white', stroke: '#7F77DD', strokeWidth: 2, r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {data.bars?.map((chart, i) => (
        <ChartCard key={i} title={chart.title} onExplain={() => explainChart(chart.title, chart.data)}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chart.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(200,168,233,0.2)" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#7f77dd' }} />
              <YAxis tickFormatter={fmt} tick={{ fontSize: 10, fill: '#afa9ec' }} width={60} />
              <Tooltip formatter={fmt} contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '0.5px solid rgba(200,168,233,0.4)', borderRadius: '8px', fontSize: '12px' }} />
              <defs>
                <linearGradient id={`grad${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#7f77dd" />
                  <stop offset="100%" stopColor="#f9c4d2" />
                </linearGradient>
              </defs>
              <Bar dataKey="value" fill={`url(#grad${i})`} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      ))}

      {data.donuts?.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {data.donuts.map((chart, i) => (
            <ChartCard key={i} title={chart.title} onExplain={() => explainChart(chart.title, chart.data)}>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={chart.data} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={2}>
                    {chart.data.map((_, idx) => <Cell key={idx} fill={COLORS[idx % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '0.5px solid rgba(200,168,233,0.4)', borderRadius: '8px', fontSize: '12px' }} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '11px' }} />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>
          ))}
        </div>
      )}

      {data.histograms?.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {data.histograms.map((chart, i) => (
            <ChartCard key={i} title={chart.title}>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={chart.data} barCategoryGap="2%">
                  <XAxis dataKey="bin" tick={{ fontSize: 9, fill: '#afa9ec' }} interval={4} />
                  <YAxis tick={{ fontSize: 9, fill: '#afa9ec' }} width={30} />
                  <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '0.5px solid rgba(200,168,233,0.4)', borderRadius: '8px', fontSize: '11px' }} />
                  <Bar dataKey="count" fill="#c8a8e9" radius={[2,2,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          ))}
        </div>
      )}

      <div className="bg-white/70 backdrop-blur border border-sage-200/40 rounded-xl p-4">
        <div className="text-sm font-medium text-sage-700 mb-3">Detected columns</div>
        <div className="flex flex-wrap gap-2">
          {session.columns?.map(col => (
            <span key={col} className="px-3 py-1 rounded-full bg-sage-100 text-sage-500 text-xs border border-sage-200">{col}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

function Investigations({ session }) {
  const [investigations, setInvestigations] = useState({
    'Executive Briefing': [],
    'Anomalies': [],
    'Trends': [],
  })
  const [active, setActive] = useState('Executive Briefing')
  const [newName, setNewName] = useState('')
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)

  async function investigate(q) {
    if (!q.trim()) return
    setLoading(true)
    try {
      const { data } = await axios.post(`${API}/ask`, {
        question: q,
        session_id: session.session_id
      })
      setInvestigations(prev => ({
        ...prev,
        [active]: [...(prev[active] || []), { question: q, answer: data.answer, tools: data.tools_called }]
      }))
      setQuestion('')
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  function createInvestigation() {
    if (!newName.trim()) return
    setInvestigations(prev => ({ ...prev, [newName]: [] }))
    setActive(newName)
    setNewName('')
  }

  return (
    <div className="flex gap-4 h-full">
      {/* Sidebar */}
      <div className="w-48 flex-shrink-0 flex flex-col gap-2">
        <div className="text-xs font-medium text-sage-400 uppercase tracking-wide mb-1">Investigations</div>
        {Object.keys(investigations).map(name => (
          <button key={name} onClick={() => setActive(name)}
            className={`text-left px-3 py-2 rounded-lg text-sm transition ${active === name ? 'bg-white border border-sage-200 text-sage-700 font-medium shadow-sm' : 'text-sage-400 hover:text-sage-600 hover:bg-white/50'}`}>
            {name}
            <span className="ml-1 text-xs text-sage-300">({investigations[name].length})</span>
          </button>
        ))}
        <div className="mt-3 flex flex-col gap-2">
          <input value={newName} onChange={e => setNewName(e.target.value)} onKeyDown={e => e.key === 'Enter' && createInvestigation()}
            placeholder="New investigation..."
            className="text-xs px-3 py-2 rounded-lg border border-sage-200 bg-white/70 text-sage-700 placeholder-sage-300 outline-none" />
          <button onClick={createInvestigation} className="text-xs px-3 py-2 rounded-lg bg-gradient-to-r from-sage-200 to-rose-sage text-sage-600 font-medium">
            + Create
          </button>
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col gap-4">
        <div className="text-base font-medium text-sage-700">{active}</div>

        {investigations[active]?.length === 0 && (
          <div className="text-sm text-sage-400 text-center py-12">
            No questions yet. Ask anything about your data below.
          </div>
        )}

        <div className="flex flex-col gap-4">
          {investigations[active]?.map((qa, i) => (
            <div key={i} className="flex flex-col gap-2">
              <div className="self-end bg-gradient-to-br from-sage-400 to-rose-deep text-white px-4 py-2 rounded-2xl rounded-tr-sm text-sm max-w-[70%]">
                {qa.question}
              </div>
              <div className="bg-white/80 border border-sage-200/40 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-sage-700 leading-relaxed">
                {qa.answer}
                {qa.tools?.length > 0 && (
                  <div className="mt-2 text-xs text-sage-300 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block"></span>
                    {qa.tools.join(', ')}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {loading && (
          <div className="bg-white/80 border border-sage-200/40 rounded-xl px-4 py-3 text-sm text-sage-400 animate-pulse">
            Investigating...
          </div>
        )}

        <div className="flex items-center gap-2 bg-white/80 border border-sage-200/50 rounded-2xl px-4 py-3 mt-auto">
          <input value={question} onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && investigate(question)}
            placeholder={`Investigate ${active.toLowerCase()}...`}
            className="flex-1 bg-transparent text-sm text-sage-700 placeholder-sage-300 outline-none" />
          <button onClick={() => investigate(question)} disabled={loading || !question.trim()}
            className="px-4 py-1.5 rounded-full bg-gradient-to-r from-sage-400 to-rose-deep text-white text-xs disabled:opacity-40">
            Investigate →
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Product({ session, onReset }) {
  const [tab, setTab] = useState('dashboard')
  const [mode, setMode] = useState('executive')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [voiceState, setVoiceState] = useState('idle')
  const [pendingAudio, setPendingAudio] = useState(null)
  const [transcript, setTranscript] = useState('')
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const bottomRef = useRef()

  useEffect(() => { window._sessionId = session.session_id }, [session])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function ask(question) {
    if (!question.trim()) return
    setMessages(m => [...m, { role: 'user', content: question }])
    setInput('')
    setLoading(true)
    try {
      const { data } = await axios.post(`${API}/ask`, { question, session_id: session.session_id })
      setMessages(m => [...m, { role: 'assistant', content: data.answer, tools: data.tools_called, trace: data.trace }])
    } catch(e) {
      setMessages(m => [...m, { role: 'assistant', content: 'Something went wrong. Please try again.' }])
    } finally { setLoading(false) }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []
      mediaRecorder.ondataavailable = e => audioChunksRef.current.push(e.data)
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        await processVoice(new Blob(audioChunksRef.current, { type: 'audio/wav' }))
      }
      mediaRecorder.start()
      setVoiceState('listening')
    } catch(e) { setVoiceState('idle') }
  }

  function stopRecording() {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
      setVoiceState('thinking')
    }
  }

  async function processVoice(blob) {
    try {
      setVoiceState('thinking')
      const form = new FormData()
      form.append('file', blob, 'audio.wav')
      const { data: t } = await axios.post(`${API}/transcribe`, form)
      const text = t.transcript
      if (!text || text === 'Could not understand audio') { setVoiceState('idle'); return }
      setTranscript(text)
      setMessages(m => [...m, { role: 'user', content: text, isVoice: true }])
      const { data: r } = await axios.post(`${API}/ask`, { question: text, session_id: session.session_id })
      setMessages(m => [...m, { role: 'assistant', content: r.answer, tools: r.tools_called }])
      setVoiceState('speaking')
      const { data: audio } = await axios.post(`${API}/speak`, { text: r.answer.slice(0, 500) })
      if (audio.audio) {
        setPendingAudio(audio.audio)
        setVoiceState('idle')
      } else { setVoiceState('idle') }
      setTranscript('')
    } catch(e) { setVoiceState('idle') }
  }

  const tabs = [
    { id: 'dashboard', label: '📊 Dashboard' },
    { id: 'chat', label: '💬 Chat with Sage' },
    { id: 'investigations', label: '🔍 Investigations' },
  ]

  return (
    <div className="min-h-screen flex flex-col">
      {/* Topbar */}
      <div className="flex items-center justify-between px-6 py-3 bg-white/70 backdrop-blur border-b border-sage-200/30 sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sage-200 to-rose-sage flex items-center justify-center">🌿</div>
          <div>
            <div className="text-sm font-medium text-sage-700">Sage</div>
            <div className="text-xs text-sage-400">Every dataset has a story. Sage tells it.</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Mode toggle */}
          <div className="flex items-center gap-1 bg-sage-100/60 rounded-lg p-1">
            {['executive', 'analyst'].map(m => (
              <button key={m} onClick={() => setMode(m)}
                className={`px-3 py-1 rounded-md text-xs transition capitalize ${mode === m ? 'bg-white text-sage-700 font-medium shadow-sm' : 'text-sage-400'}`}>
                {m === 'executive' ? '👔 Executive' : '🔬 Analyst'}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/70 border border-sage-200 text-xs text-sage-500">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block"></span>
            {session.rows?.toLocaleString()} rows · {session.filename}
          </div>
          <button onClick={onReset} className="text-xs text-sage-400 hover:text-sage-600 transition">← New dataset</button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 px-6 py-2 bg-white/50 border-b border-sage-200/20">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-1.5 rounded-lg text-sm transition ${tab === t.id ? 'bg-white text-sage-700 font-medium shadow-sm' : 'text-sage-400 hover:text-sage-600'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 p-6 max-w-6xl mx-auto w-full">

        {tab === 'dashboard' && <Dashboard session={session} mode={mode} />}

        {tab === 'chat' && (
          <div className="flex flex-col gap-4 max-w-3xl mx-auto">
            {messages.length === 0 && (
              <div className="text-center py-16">
                <div className="text-3xl mb-3">✦</div>
                <div className="text-xl font-medium text-sage-700 mb-2">What do you want to know?</div>
                <div className="text-sage-400 text-sm">Ask anything about your data — speak or type</div>
              </div>
            )}
            <div className="flex flex-col gap-4">
              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.role === 'user' ? (
                    <div className="flex justify-end">
                      <div className={`bg-gradient-to-br from-sage-400 to-rose-deep text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm max-w-[70%] ${msg.isVoice ? 'ring-2 ring-sage-300' : ''}`}>
                        {msg.isVoice && <span className="text-xs opacity-70 mr-1">🎤</span>}
                        {msg.content}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-1">
                      <div className="text-xs text-sage-300 flex items-center gap-1">🌿 Sage · {mode === 'executive' ? 'Executive' : 'Analyst'}</div>
                      <div className="bg-white/80 backdrop-blur border border-sage-200/40 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-sage-700 leading-relaxed">
                        {msg.content}
                        {mode === 'analyst' && msg.tools?.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-sage-100 text-xs text-sage-300 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block"></span>
                            {msg.tools.length} tool calls · {msg.tools.join(', ')}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="flex flex-col gap-1">
                  <div className="text-xs text-sage-300">🌿 Sage · Analyst</div>
                  <div className="bg-white/80 border border-sage-200/40 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-sage-400 animate-pulse">Thinking...</div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
            {pendingAudio && (
              <button
                onClick={() => {
                  const sound = new Audio(`data:audio/mp3;base64,${pendingAudio}`)
                  sound.play()
                  setPendingAudio(null)
                }}
                className="self-start flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-sage-200 to-rose-sage text-sage-600 text-sm animate-pulse"
              >
                🔊 Tap to hear Sage's answer
              </button>
            )}
            {transcript && (
              <div className="text-xs text-sage-400 px-2 flex items-center gap-1">
                <span>🎤</span><span>"{transcript}"</span>
              </div>
            )}
            <div className="flex items-center gap-2 bg-white/80 backdrop-blur border border-sage-200/50 rounded-2xl px-4 py-3">
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !loading && ask(input)}
                placeholder={voiceState === 'listening' ? 'Listening...' : voiceState === 'thinking' ? 'Sage is thinking...' : voiceState === 'speaking' ? 'Sage is speaking...' : 'Ask Sage about your data…'}
                disabled={voiceState !== 'idle'}
                className="flex-1 bg-transparent text-sm text-sage-700 placeholder-sage-300 outline-none disabled:opacity-50" />
              <button onClick={voiceState === 'idle' ? startRecording : voiceState === 'listening' ? stopRecording : undefined}
                disabled={voiceState === 'thinking' || voiceState === 'speaking'}
                className={`w-9 h-9 rounded-full flex items-center justify-center transition-all text-base ${voiceState === 'listening' ? 'bg-red-400 animate-pulse text-white' : voiceState === 'thinking' || voiceState === 'speaking' ? 'bg-sage-200 text-sage-400 cursor-not-allowed' : 'bg-gradient-to-br from-sage-200 to-rose-sage text-sage-600 hover:from-sage-300'}`}>
                {voiceState === 'listening' ? '⏹' : voiceState === 'thinking' ? '⏳' : voiceState === 'speaking' ? '🔊' : '🎤'}
              </button>
              <button onClick={() => ask(input)} disabled={loading || !input.trim() || voiceState !== 'idle'}
                className="w-9 h-9 rounded-full bg-gradient-to-br from-sage-400 to-rose-deep flex items-center justify-center text-white text-sm disabled:opacity-40 transition">↑</button>
            </div>
          </div>
        )}

        {tab === 'investigations' && <Investigations session={session} />}
      </div>
    </div>
  )
}

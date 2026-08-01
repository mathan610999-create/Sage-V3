import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import {
  Mic, Brain, MessageSquareText, LineChart as LineChartIcon, FileSpreadsheet,
  Sparkles, UploadCloud, ArrowRight, Volume2, Database, Waves, ChevronLeft, ChevronRight, Clock,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell,
} from 'recharts'

const API = 'https://sage-v3-production.up.railway.app'
const LEAF = '#1f9d55'
const CHART_COLORS = ['#C8A8E9', '#AFA9EC', '#7F77DD', '#534AB7', '#7F77DD', '#AFA9EC']
const MOCK_CHART_DATA = [
  { name: 'Jan', v: 42 }, { name: 'Feb', v: 55 }, { name: 'Mar', v: 48 },
  { name: 'Apr', v: 70 }, { name: 'May', v: 61 }, { name: 'Jun', v: 88 },
]

function Reveal({ children, delay = 0, className = '' }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); io.disconnect() } },
      { threshold: 0.15 }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(18px)',
        transition: `opacity 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}ms, transform 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  )
}

// Mouse-reactive parallax wrapper for the hero's ambient orbs
function Parallax({ children, strength = 1 }) {
  const ref = useRef(null)
  const [offset, setOffset] = useState({ x: 0, y: 0 })

  function handleMove(e) {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const px = (e.clientX - rect.left) / rect.width - 0.5
    const py = (e.clientY - rect.top) / rect.height - 0.5
    setOffset({ x: px * 24 * strength, y: py * 24 * strength })
  }

  return (
    <div ref={ref} onMouseMove={handleMove} onMouseLeave={() => setOffset({ x: 0, y: 0 })}>
      {typeof children === 'function' ? children(offset) : children}
    </div>
  )
}

const FEATURES = [
  { icon: Mic, title: 'Voice in, voice out', desc: 'Ask a question out loud and hear Sage answer back — with the reasoning behind the number, not just the number.' },
  { icon: Brain, title: '8 reasoning tools', desc: 'SQL, trends, anomalies, correlations, top-N, and more — chained together automatically.' },
  { icon: FileSpreadsheet, title: 'Any dataset, instantly', desc: 'Drop a CSV or Excel file. No schema, no setup, no modeling required.' },
  { icon: LineChartIcon, title: 'Charts on demand', desc: 'Sage decides which chart tells the story best, and builds it live.' },
  { icon: MessageSquareText, title: 'Remembers the thread', desc: 'Follow-up questions build on what you already asked — like a real analyst would.' },
  { icon: Sparkles, title: 'Plain English, always', desc: 'Findings are written for the person who owns the decision, not the person who owns the pipeline.' },
]

const STEPS = [
  { icon: UploadCloud, title: 'Upload your data', desc: 'CSV or Excel — Sage profiles every column and understands what it means.' },
  { icon: Brain, title: 'Sage reasons through it', desc: 'It runs EDA, checks anomalies, finds trends, and drafts a plain-English briefing.' },
  { icon: Volume2, title: 'Ask, and listen', desc: 'Type or speak a follow-up. Sage answers out loud, with the "why" included.' },
]

export default function Landing({ onSessionStart, onOpenHistory }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef()
  const carouselRef = useRef()

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

  function scrollTo(id) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function scrollCarousel(dir) {
    carouselRef.current?.scrollBy({ left: dir * 340, behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      {/* Nav */}
      <nav className="sticky top-0 z-30 flex items-center justify-between px-6 md:px-10 py-4 bg-white/70 backdrop-blur-md border-b border-sage-200/30">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sage-200 to-sage-100 flex items-center justify-center text-lg shadow-sm">🌿</div>
          <div>
            <div className="text-sm font-semibold text-sage-700 leading-none">Sage</div>
            <div className="text-[11px] text-sage-500 mt-0.5 hidden sm:block">Every dataset has a story. Sage tells it.</div>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-7 text-sm text-sage-500">
          <button onClick={() => scrollTo('how-it-works')} className="hover:text-sage-700 transition">How it works</button>
          <button onClick={() => scrollTo('features')} className="hover:text-sage-700 transition">Features</button>
          <button onClick={() => scrollTo('philosophy')} className="hover:text-sage-700 transition">Philosophy</button>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={onOpenHistory}
            className="inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-2 rounded-full border border-sage-200 text-sage-500 hover:bg-sage-50 hover:text-sage-700 transition"
          >
            <Clock size={13} /> <span className="hidden sm:inline">Past reports</span>
          </button>
          <button
            onClick={() => inputRef.current?.click()}
            className="btn-shine text-xs font-medium px-4 py-2 rounded-full bg-sage-700 text-white hover:bg-sage-600 transition shadow-sm"
          >
            Try Sage free
          </button>
        </div>
      </nav>

      {/* Hero */}
      <Parallax strength={1}>
        {(offset) => (
          <section className="relative px-6 pt-20 pb-24 md:pt-28 md:pb-32 flex flex-col items-center text-center">
            {/* ambient orbs — drift toward the cursor */}
            <div className="pointer-events-none absolute inset-0 overflow-hidden -z-10">
              <div
                className="orb-float-a absolute -top-10 left-[8%] w-72 h-72 rounded-full bg-sage-200/40 blur-3xl transition-transform duration-300 ease-out"
                style={{ transform: `translate(${offset.x}px, ${offset.y}px)` }}
              />
              <div
                className="orb-float-b absolute top-40 right-[6%] w-80 h-80 rounded-full blur-3xl transition-transform duration-300 ease-out"
                style={{ background: 'rgba(31,157,85,0.16)', transform: `translate(${-offset.x}px, ${-offset.y}px)` }}
              />
              <div
                className="orb-float-a absolute bottom-0 left-[35%] w-64 h-64 rounded-full bg-sage-400/10 blur-3xl transition-transform duration-300 ease-out"
                style={{ transform: `translate(${offset.x * 0.5}px, ${offset.y * 0.5}px)` }}
              />
            </div>

            <div className="animate-fade-up inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-sage-100 border border-sage-200 text-sage-500 text-xs font-medium mb-7">
              <Sparkles size={13} className="pulse-soft" /> Voice-first analytics agent
            </div>

            <h1 className="animate-fade-up font-serif-display text-[2.6rem] leading-[1.08] sm:text-5xl md:text-6xl font-medium text-sage-700 max-w-3xl" style={{ animationDelay: '80ms' }}>
              Every dataset has a story.<br />
              <span className="gradient-text-anim bg-clip-text text-transparent italic">
                Sage tells it.
              </span>
            </h1>

            <p className="animate-fade-up text-sage-500 text-base md:text-lg mt-6 mb-10 max-w-xl leading-relaxed" style={{ animationDelay: '160ms' }}>
              Upload any dataset. Ask questions out loud. Hear the answers spoken back — with the reasoning behind them. No SQL, no dashboards, no training required.
            </p>

            <div className="animate-fade-up flex flex-col items-center gap-4 w-full" style={{ animationDelay: '220ms' }}>
              {/* CTA row */}
              <div className="flex flex-wrap items-center justify-center gap-3">
                <button
                  onClick={() => inputRef.current?.click()}
                  className="btn-shine inline-flex items-center gap-2 text-sm font-medium px-6 py-3 rounded-full bg-sage-700 text-white hover:bg-sage-600 transition shadow-lg shadow-sage-700/20"
                >
                  <UploadCloud size={16} /> Upload your data
                </button>
                <button
                  onClick={() => scrollTo('how-it-works')}
                  className="inline-flex items-center gap-2 text-sm font-medium px-6 py-3 rounded-full border border-sage-200 text-sage-600 hover:bg-sage-50 transition"
                >
                  See how it works <ArrowRight size={15} />
                </button>
              </div>

              {/* Upload zone */}
              <div
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); handleFile(e.dataTransfer.files[0]) }}
                onClick={() => inputRef.current?.click()}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click() } }}
                role="button"
                tabIndex={0}
                aria-label="Upload your dataset"
                className="mt-4 w-full max-w-md border-2 border-dashed border-sage-200 rounded-2xl p-8 cursor-pointer hover:border-sage-300 hover:bg-sage-50/60 transition text-center bg-white/40 backdrop-blur focus:outline-none focus-visible:ring-2 focus-visible:ring-sage-400 focus-visible:ring-offset-2"
              >
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sage-200 to-sage-100 flex items-center justify-center text-2xl mx-auto mb-3">
                  {uploading ? '⏳' : '📊'}
                </div>
                <div className="text-sage-700 font-medium mb-1 text-sm">
                  {uploading ? 'Uploading & analyzing…' : 'Drop your dataset here, or click to browse'}
                </div>
                <div className="text-sage-500 text-xs">CSV or Excel · up to 200MB</div>
                {error && <div className="text-[color:#c0392b] text-xs mt-2">{error}</div>}
              </div>
              <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={e => handleFile(e.target.files[0])} />

              {/* Stat strip */}
              <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 mt-8 text-xs text-sage-500">
                {['8 reasoning tools', 'Any CSV or Excel', 'Seconds to first insight', 'Voice in & out'].map(s => (
                  <span key={s} className="inline-flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: LEAF }} /> {s}
                  </span>
                ))}
              </div>
            </div>
          </section>
        )}
      </Parallax>

      {/* How it works */}
      <section id="how-it-works" className="px-6 py-20 md:py-28 bg-white/40 border-y border-sage-200/30">
        <div className="max-w-5xl mx-auto">
          <Reveal className="text-center mb-14">
            <div className="text-xs font-semibold tracking-widest uppercase mb-3" style={{ color: LEAF }}>How it works</div>
            <h2 className="font-serif-display text-3xl md:text-4xl text-sage-700">From raw file to spoken insight</h2>
          </Reveal>
          <div className="grid md:grid-cols-3 gap-8 relative">
            <div className="hidden md:block absolute top-8 left-[16.5%] right-[16.5%] h-px bg-gradient-to-r from-sage-200 via-[#1f9d55]/30 to-sage-200" />
            {STEPS.map((s, i) => (
              <Reveal key={s.title} delay={i * 120}>
                <div className="relative text-center flex flex-col items-center group">
                  <div className="w-16 h-16 rounded-2xl bg-white border border-sage-200/60 shadow-sm flex items-center justify-center mb-5 relative z-10 transition-transform duration-300 group-hover:-translate-y-1 group-hover:shadow-md">
                    <s.icon size={24} className="text-sage-500" strokeWidth={1.75} />
                  </div>
                  <div className="text-xs font-semibold mb-1" style={{ color: LEAF }}>Step {i + 1}</div>
                  <div className="text-base font-medium text-sage-700 mb-2">{s.title}</div>
                  <div className="text-sm text-sage-500 leading-relaxed max-w-xs">{s.desc}</div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Features carousel + product preview */}
      <section id="features" className="px-6 py-20 md:py-28">
        <div className="max-w-6xl mx-auto">
          <Reveal className="mb-10 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 text-center sm:text-left">
            <div>
              <div className="text-xs font-semibold tracking-widest uppercase mb-3" style={{ color: LEAF }}>Features</div>
              <h2 className="font-serif-display text-3xl md:text-4xl text-sage-700 mb-3">Built like an analyst, not a dashboard</h2>
              <p className="text-sage-500 max-w-lg">Everything Sage does is in service of one thing: making sure you have what you need to decide well.</p>
            </div>
            <div className="hidden sm:flex items-center gap-2 shrink-0">
              <button onClick={() => scrollCarousel(-1)} aria-label="Scroll features left" className="w-9 h-9 rounded-full border border-sage-200 flex items-center justify-center text-sage-500 hover:bg-sage-50 transition">
                <ChevronLeft size={16} />
              </button>
              <button onClick={() => scrollCarousel(1)} aria-label="Scroll features right" className="w-9 h-9 rounded-full border border-sage-200 flex items-center justify-center text-sage-500 hover:bg-sage-50 transition">
                <ChevronRight size={16} />
              </button>
            </div>
          </Reveal>

          {/* Horizontal scroll-snap carousel */}
          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-[#faf8ff] to-transparent z-10" />
            <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-[#faf8ff] to-transparent z-10" />
            <div
              ref={carouselRef}
              className="no-scrollbar flex gap-5 overflow-x-auto snap-x snap-mandatory pb-4 scroll-px-6"
            >
              {FEATURES.map((f, i) => (
                <Reveal key={f.title} delay={(i % 3) * 90} className="snap-center shrink-0 w-[78vw] xs:w-[300px] sm:w-[300px]">
                  <div className="h-full bg-white/70 backdrop-blur border border-sage-200/40 rounded-2xl p-6 hover:shadow-lg hover:shadow-sage-200/30 hover:-translate-y-1 transition-all duration-300">
                    <div
                      className="w-11 h-11 rounded-xl flex items-center justify-center mb-4"
                      style={{ background: i % 2 === 0 ? 'rgba(84,74,183,0.1)' : 'rgba(31,157,85,0.12)' }}
                    >
                      <f.icon size={20} strokeWidth={1.75} style={{ color: i % 2 === 0 ? '#534AB7' : LEAF }} />
                    </div>
                    <div className="text-sm font-semibold text-sage-700 mb-1.5">{f.title}</div>
                    <div className="text-sm text-sage-500 leading-relaxed">{f.desc}</div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>

          {/* Product preview mockup */}
          <Reveal delay={120} className="mt-8">
            <div className="bg-white/70 backdrop-blur border border-sage-200/40 rounded-2xl p-6 md:p-8 grid md:grid-cols-5 gap-6 items-center">
              <div className="md:col-span-2">
                <div className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-sage-100 text-sage-500 border border-sage-200 mb-4">
                  <Waves size={12} /> Live inside Sage
                </div>
                <div className="space-y-3">
                  <div className="ml-auto max-w-[85%] bg-sage-700 text-white text-sm rounded-2xl rounded-tr-sm px-4 py-2.5">
                    What's driving the jump in June?
                  </div>
                  <div className="max-w-[90%] bg-sage-50 border border-sage-200/60 text-sage-700 text-sm rounded-2xl rounded-tl-sm px-4 py-2.5 leading-relaxed">
                    June revenue is up 44% over May — almost entirely from a spike in repeat orders in your top region. Here's the trend:
                  </div>
                  <button className="inline-flex items-center gap-1.5 text-xs text-sage-500 pl-1">
                    <Volume2 size={13} /> Played back automatically
                  </button>
                </div>
              </div>
              <div className="md:col-span-3 bg-white rounded-xl border border-sage-200/40 p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="text-sm font-medium text-sage-700">Monthly revenue</div>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-600 border border-green-100">+44% MoM</span>
                </div>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={MOCK_CHART_DATA}>
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#afa9ec' }} axisLine={false} tickLine={false} />
                    <YAxis hide />
                    <Bar dataKey="v" radius={[6, 6, 0, 0]}>
                      {MOCK_CHART_DATA.map((_, idx) => (
                        <Cell key={idx} fill={idx === MOCK_CHART_DATA.length - 1 ? LEAF : CHART_COLORS[idx % CHART_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Philosophy */}
      <section id="philosophy" className="px-6 py-20 md:py-28 bg-sage-700 text-white relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-0">
          <div className="orb-float-a absolute -top-16 -left-16 w-72 h-72 rounded-full bg-sage-400/20 blur-3xl" />
          <div className="orb-float-b absolute bottom-0 right-0 w-80 h-80 rounded-full blur-3xl" style={{ background: 'rgba(31,157,85,0.25)' }} />
        </div>
        <Reveal className="relative max-w-2xl mx-auto text-center">
          <Database size={22} className="mx-auto mb-6 text-sage-200" strokeWidth={1.5} />
          <blockquote className="font-serif-display italic text-2xl md:text-3xl leading-relaxed">
            "I don't tell you what to decide. I make sure you have everything you need to decide well."
          </blockquote>
          <div className="mt-6 text-sage-200 text-sm tracking-wide">— The Sage philosophy</div>
        </Reveal>
      </section>

      {/* Final CTA */}
      <section className="px-6 py-20 md:py-28 text-center">
        <Reveal>
          <h2 className="font-serif-display text-3xl md:text-4xl text-sage-700 mb-4">Bring your data. Ask anything.</h2>
          <p className="text-sage-500 mb-8 max-w-md mx-auto">No signup friction, no sample-data theater. Drop a real file and see what Sage finds in seconds.</p>
          <button
            onClick={() => inputRef.current?.click()}
            className="btn-shine inline-flex items-center gap-2 text-sm font-medium px-7 py-3.5 rounded-full bg-sage-700 text-white hover:bg-sage-600 transition shadow-lg shadow-sage-700/20"
          >
            <UploadCloud size={16} /> Upload your dataset
          </button>
        </Reveal>
      </section>

      {/* Footer */}
      <footer className="px-6 py-8 border-t border-sage-200/40 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-sage-500">
        <div className="flex items-center gap-2">
          <span className="text-base">🌿</span>
          <span className="font-medium text-sage-600">Sage</span>
          <span className="hidden sm:inline">· Every dataset has a story. Sage tells it.</span>
        </div>
        <div>© {new Date().getFullYear()} Sage. Not a decision maker. A decision helper.</div>
      </footer>
    </div>
  )
}

import { useState } from 'react'
import axios from 'axios'
import Landing from './pages/Landing'
import Product from './pages/Product'
import HistoryPanel from './components/HistoryPanel'

const API = 'https://sage-v3-production.up.railway.app'

export default function App() {
  const [session, setSession] = useState(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [resumeError, setResumeError] = useState(null)

  async function resumeSession(sessionId) {
    setResumeError(null)
    try {
      const { data } = await axios.get(`${API}/sessions/${sessionId}`)
      setSession(data)
      setHistoryOpen(false)
    } catch (e) {
      setResumeError('Could not reopen that report — it may no longer be available.')
    }
  }

  return (
    <>
      {session
        ? <Product session={session} onReset={() => setSession(null)} onOpenHistory={() => setHistoryOpen(true)} />
        : <Landing onSessionStart={setSession} onOpenHistory={() => setHistoryOpen(true)} />}

      {historyOpen && (
        <HistoryPanel
          onClose={() => setHistoryOpen(false)}
          onSelect={resumeSession}
          error={resumeError}
        />
      )}
    </>
  )
}

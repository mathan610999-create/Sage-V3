import { useState } from 'react'
import Landing from './pages/Landing'
import Product from './pages/Product'

export default function App() {
  const [session, setSession] = useState(null)

  return session
    ? <Product session={session} onReset={() => setSession(null)} />
    : <Landing onSessionStart={setSession} />
}

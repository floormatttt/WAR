import { useState } from 'react'
import Leaderboard from './components/Leaderboard'
import Methodology from './components/Methodology'
import './App.css'

export default function App() {
  const [tab, setTab] = useState('leaderboard')

  return (
    <>
      <header className="site-header">
        <div className="header-inner">
          <div className="site-brand">
            <span className="brand-acronym">OL</span>
            <span className="brand-title">WAR</span>
            <span className="brand-sub">Offensive Line Wins Above Replacement</span>
          </div>
          <nav className="site-nav">
            <button
              className={`nav-tab ${tab === 'leaderboard' ? 'nav-active' : ''}`}
              onClick={() => setTab('leaderboard')}
            >
              Leaderboard
            </button>
            <button
              className={`nav-tab ${tab === 'methodology' ? 'nav-active' : ''}`}
              onClick={() => setTab('methodology')}
            >
              Methodology
            </button>
          </nav>
        </div>
      </header>

      <main className="site-main">
        {tab === 'leaderboard' ? <Leaderboard /> : <Methodology />}
      </main>

      <footer className="site-footer">
        <p>Data: PFF pass blocking grades 2013–2025. EPA: nflfastR play-by-play.</p>
      </footer>
    </>
  )
}

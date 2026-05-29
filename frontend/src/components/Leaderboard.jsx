import { useState, useMemo } from 'react'
import Papa from 'papaparse'

const yearModules = import.meta.glob(
  '../../../Pass Blocking PFF/O-Line Data * WAR.csv',
  { query: '?raw', import: 'default', eager: true }
)

import careerRaw from '../../../Pass Blocking PFF/O-Line WAR Career.csv?raw'

function parseCareer() {
  const result = Papa.parse(careerRaw, { header: true, skipEmptyLines: true })
  return result.data.map(r => ({
    player: r.player,
    position: r.position,
    seasons: Number(r.seasons),
    career_snaps: Number(r.career_snaps),
    career_pressures: Number(r.career_pressures),
    career_war: Number(r.career_war),
  }))
}

function parseYearFiles() {
  const byYear = {}
  for (const [path, raw] of Object.entries(yearModules)) {
    const match = path.match(/O-Line Data (\d{4}) WAR\.csv/)
    if (!match) continue
    const year = match[1]
    const result = Papa.parse(raw, { header: true, skipEmptyLines: true })
    byYear[year] = result.data.map(r => ({
      player: r.player,
      position: r.position,
      team_name: r.team_name,
      snap_counts_pass_block: Number(r.snap_counts_pass_block),
      pressures_allowed: Number(r.pressures_allowed),
      all_pass_pbwr: Number(r.all_pass_pbwr),
      pass_blocking_war: Number(r.pass_blocking_war),
    }))
  }
  return byYear
}

const careerData = parseCareer()
const yearData = parseYearFiles()
const availableYears = Object.keys(yearData).sort((a, b) => b - a)

const CAREER_COLS = [
  { key: 'player', label: 'Player', numeric: false },
  { key: 'position', label: 'Pos', numeric: false },
  { key: 'seasons', label: 'Seasons', numeric: true },
  { key: 'career_snaps', label: 'Snaps', numeric: true },
  { key: 'career_pressures', label: 'Pressures', numeric: true },
  { key: 'career_war', label: 'Career WAR', numeric: true, war: true },
]

const YEAR_COLS = [
  { key: 'player', label: 'Player', numeric: false },
  { key: 'position', label: 'Pos', numeric: false },
  { key: 'team_name', label: 'Team', numeric: false },
  { key: 'snap_counts_pass_block', label: 'Snaps', numeric: true },
  { key: 'pressures_allowed', label: 'Pressures', numeric: true },
  { key: 'all_pass_pbwr', label: 'PBWR %', numeric: true },
  { key: 'pass_blocking_war', label: 'WAR', numeric: true, war: true },
]

const POSITIONS = ['All', 'T', 'G', 'C']

export default function Leaderboard() {
  const [mode, setMode] = useState('career')
  const [year, setYear] = useState(availableYears[0])
  const [position, setPosition] = useState('All')
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState(mode === 'career' ? 'career_war' : 'pass_blocking_war')
  const [sortDir, setSortDir] = useState('desc')

  function handleModeChange(newMode) {
    setMode(newMode)
    setSortCol(newMode === 'career' ? 'career_war' : 'pass_blocking_war')
    setSortDir('desc')
  }

  function handleSort(key) {
    if (sortCol === key) {
      setSortDir(d => (d === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortCol(key)
      setSortDir('desc')
    }
  }

  const cols = mode === 'career' ? CAREER_COLS : YEAR_COLS
  const source = mode === 'career' ? careerData : (yearData[year] || [])

  const rows = useMemo(() => {
    let data = source
    if (position !== 'All') {
      data = data.filter(r => r.position === position)
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      data = data.filter(r => r.player.toLowerCase().includes(q))
    }
    data = [...data].sort((a, b) => {
      const av = a[sortCol]
      const bv = b[sortCol]
      if (typeof av === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      return sortDir === 'asc' ? av - bv : bv - av
    })
    return data
  }, [source, position, search, sortCol, sortDir])

  return (
    <div className="leaderboard">
      <div className="controls">
        <div className="control-group">
          <PillGroup
            options={['career', 'year']}
            labels={{ career: 'Career', year: 'By Year' }}
            value={mode}
            onChange={handleModeChange}
          />
          {mode === 'year' && (
            <select
              className="year-select"
              value={year}
              onChange={e => setYear(e.target.value)}
            >
              {availableYears.map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          )}
        </div>
        <div className="control-group">
          <PillGroup
            options={POSITIONS}
            value={position}
            onChange={setPosition}
          />
        </div>
        <div className="control-group">
          <input
            className="search-input"
            type="text"
            placeholder="Search player..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="row-count">{rows.length} players</div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th className="rank-col">#</th>
              {cols.map(col => (
                <th
                  key={col.key}
                  className={`${col.numeric ? 'numeric' : ''} ${sortCol === col.key ? 'sorted' : ''}`}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}
                  {sortCol === col.key && (
                    <span className="sort-arrow">{sortDir === 'desc' ? ' ↓' : ' ↑'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={`${row.player}-${row.position}-${i}`}>
                <td className="rank-col">{i + 1}</td>
                {cols.map(col => (
                  <td
                    key={col.key}
                    className={col.numeric ? 'numeric' : ''}
                  >
                    {col.war
                      ? Number(row[col.key]).toFixed(6)
                      : col.key === 'all_pass_pbwr'
                      ? Number(row[col.key]).toFixed(2)
                      : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function PillGroup({ options, labels, value, onChange }) {
  return (
    <div className="pill-group">
      {options.map(opt => (
        <button
          key={opt}
          className={`pill ${value === opt ? 'pill-active' : ''}`}
          onClick={() => onChange(opt)}
        >
          {labels ? labels[opt] : opt}
        </button>
      ))}
    </div>
  )
}

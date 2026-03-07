/**
 * GlobalSearch — Press '/' anywhere to open.
 * Esc or click outside to close.
 * Results show inline, click to open in source.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, X, ExternalLink, ArrowRight } from 'lucide-react'
import { searchDocs } from '../api'
import { SourceBadge } from './UI'

const SOURCE_ICON = {
  jira:       '🎫',
  confluence: '📖',
  github:     '💻',
  sharepoint: '📋',
}

export default function GlobalSearch() {
  const [open, setOpen]       = useState(false)
  const [query, setQuery]     = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(0)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  // Open on '/' keypress (when not in an input)
  useEffect(() => {
    const onKey = (e) => {
      // Open
      if (e.key === '/' && !['INPUT','TEXTAREA'].includes(document.activeElement?.tagName)) {
        e.preventDefault()
        setOpen(true)
      }
      // Close
      if (e.key === 'Escape') {
        setOpen(false)
        setQuery('')
        setResults(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setSelected(0)
    }
  }, [open])

  // Debounced search
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setResults(null)
      return
    }
    const t = setTimeout(async () => {
      setLoading(true)
      try {
        const r = await searchDocs(query, null, 1)
        setResults(r.data)
        setSelected(0)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [query])

  const allResults = results?.results || []

  // Keyboard navigation
  useEffect(() => {
    if (!open) return
    const onKey = (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelected(s => Math.min(s + 1, allResults.length - 1 + 1)) // +1 for "see all"
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelected(s => Math.max(s - 1, 0))
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        if (selected === allResults.length) {
          // "See all results"
          navigate(`/search?q=${encodeURIComponent(query)}`)
          close()
        } else if (allResults[selected]?.url) {
          window.open(allResults[selected].url, '_blank')
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, selected, allResults, query])

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
    setResults(null)
  }, [])

  const handleSeeAll = () => {
    navigate(`/search?q=${encodeURIComponent(query)}`)
    close()
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={close}
    >
      <div
        className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <Search size={18} className="text-gray-400 shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search everything — docs, tickets, code, people..."
            className="flex-1 text-sm text-gray-900 placeholder-gray-400 outline-none bg-transparent"
          />
          {query && (
            <button onClick={() => { setQuery(''); setResults(null) }} className="text-gray-400 hover:text-gray-600">
              <X size={16} />
            </button>
          )}
          <kbd className="hidden md:block text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded border border-gray-200">Esc</kbd>
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto">
          {/* Loading */}
          {loading && (
            <div className="px-4 py-6 text-center text-sm text-gray-400">Searching…</div>
          )}

          {/* No results */}
          {!loading && results && allResults.length === 0 && (
            <div className="px-4 py-6 text-center">
              <p className="text-sm text-gray-500">No results for <strong>"{query}"</strong></p>
              {results.fuzzy !== undefined && !results.fuzzy && (
                <p className="text-xs text-gray-400 mt-1">Try a different keyword</p>
              )}
            </div>
          )}

          {/* Results list */}
          {!loading && allResults.length > 0 && (
            <ul className="py-2">
              {allResults.slice(0, 7).map((doc, i) => (
                <li key={i}>
                  <a
                    href={doc.url || '#'}
                    target={doc.url ? '_blank' : undefined}
                    rel="noreferrer"
                    onClick={close}
                    className={`flex items-start gap-3 px-4 py-2.5 hover:bg-gray-50 transition-colors ${
                      selected === i ? 'bg-teal-50' : ''
                    }`}
                    onMouseEnter={() => setSelected(i)}
                  >
                    <span className="text-base mt-0.5 shrink-0">{SOURCE_ICON[doc.source_type] || '📄'}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900 truncate">{doc.title}</span>
                        {doc.url && <ExternalLink size={11} className="shrink-0 text-gray-400" />}
                      </div>
                      {doc.best_answer || doc.content ? (
                        <p className="text-xs text-gray-400 truncate mt-0.5">
                          {(doc.best_answer || doc.content || '').slice(0, 100)}
                        </p>
                      ) : null}
                    </div>
                    <SourceBadge type={doc.source_type} />
                  </a>
                </li>
              ))}

              {/* See all results */}
              {results.total > 0 && (
                <li>
                  <button
                    onClick={handleSeeAll}
                    className={`w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium transition-colors ${
                      selected === allResults.slice(0,7).length
                        ? 'bg-teal-50 text-teal-700'
                        : 'text-teal-600 hover:bg-teal-50'
                    }`}
                    onMouseEnter={() => setSelected(allResults.slice(0,7).length)}
                  >
                    <span>See all {results.total} results for "{query}"</span>
                    <ArrowRight size={14} />
                  </button>
                </li>
              )}
            </ul>
          )}

          {/* Empty state — no query */}
          {!query && (
            <div className="px-4 py-6 text-center">
              <p className="text-sm text-gray-400">Start typing to search across all knowledge sources</p>
              <div className="flex justify-center gap-3 mt-3 flex-wrap">
                {['payments', 'BIC ETL', 'CGME', 'onboarding'].map(s => (
                  <button
                    key={s}
                    onClick={() => setQuery(s)}
                    className="text-xs bg-gray-100 text-gray-600 px-3 py-1.5 rounded-full hover:bg-gray-200 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-400">
          <span><kbd className="bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">↑↓</kbd> navigate</span>
          <span><kbd className="bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">↵</kbd> open</span>
          <span><kbd className="bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">Esc</kbd> close</span>
          <span className="ml-auto">Press <kbd className="bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">/</kbd> to open anytime</span>
        </div>
      </div>
    </div>
  )
}

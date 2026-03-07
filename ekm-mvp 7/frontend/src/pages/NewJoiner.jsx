/**
 * NewJoiner — Public shareable learning path page
 * Route: /join/:topic
 * Anyone with the link can view — no login needed.
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Brain, Share2, CheckCircle, Circle, ExternalLink } from 'lucide-react'
import { getOnboardingPath } from '../api'
import { Spinner, SourceBadge } from '../components/UI'

const SECTION_STYLE = {
  confluence: { bg: 'bg-purple-50 border-purple-200', dot: 'bg-purple-500' },
  sharepoint: { bg: 'bg-blue-50 border-blue-200',   dot: 'bg-blue-500'   },
  github:     { bg: 'bg-gray-50 border-gray-200',    dot: 'bg-gray-500'   },
  jira:       { bg: 'bg-orange-50 border-orange-200', dot: 'bg-orange-400' },
}

export default function NewJoiner() {
  const { topic }       = useParams()
  const navigate        = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [checked, setChecked] = useState({})
  const [copied, setCopied]   = useState(false)

  useEffect(() => {
    if (!topic) return
    getOnboardingPath(decodeURIComponent(topic))
      .then(r => { setData(r.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [topic])

  const decodedTopic = decodeURIComponent(topic || '')
  const totalDocs    = data?.sections?.reduce((sum, s) => sum + s.docs.length, 0) || 0
  const checkedCount = Object.values(checked).filter(Boolean).length

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const toggleCheck = (key) =>
    setChecked(prev => ({ ...prev, [key]: !prev[key] }))

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#0d9488' }}>
              <Brain size={16} className="text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-gray-900 leading-tight">EKM</p>
              <p className="text-xs text-gray-400">Knowledge Hub</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {totalDocs > 0 && (
              <span className="text-xs text-gray-500">
                {checkedCount}/{totalDocs} completed
              </span>
            )}
            <button
              onClick={handleShare}
              className="flex items-center gap-1.5 text-xs bg-teal-50 text-teal-700 border border-teal-200 hover:bg-teal-100 px-3 py-1.5 rounded-lg transition-colors"
            >
              <Share2 size={13} />
              {copied ? '✓ Copied!' : 'Share Link'}
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 bg-teal-50 text-teal-700 border border-teal-200 text-xs px-3 py-1 rounded-full mb-3">
            🎓 New Joiner Learning Path
          </div>
          <h1 className="text-3xl font-bold text-gray-900 capitalize mb-2">{decodedTopic}</h1>
          {!loading && data && (
            <p className="text-gray-500">
              {totalDocs} documents across {data.sections?.length} source{data.sections?.length !== 1 ? 's' : ''} —
              read in order for the fastest way to get up to speed.
            </p>
          )}
        </div>

        {/* Progress bar */}
        {totalDocs > 0 && (
          <div className="mb-6">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Your progress</span>
              <span>{Math.round(checkedCount / totalDocs * 100)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-teal-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${checkedCount / totalDocs * 100}%` }}
              />
            </div>
          </div>
        )}

        {loading && (
          <div className="flex justify-center py-16"><Spinner /></div>
        )}

        {!loading && (!data || totalDocs === 0) && (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">🔍</div>
            <h2 className="text-lg font-semibold text-gray-700 mb-2">No documents found</h2>
            <p className="text-gray-500 text-sm">No learning materials found for "{decodedTopic}".</p>
            <button onClick={() => navigate('/')} className="mt-4 text-sm text-teal-600 hover:underline">
              ← Go to EKM
            </button>
          </div>
        )}

        {/* Sections */}
        {data?.sections?.map(section => {
          const style = SECTION_STYLE[section.source_type] || SECTION_STYLE.github
          return (
            <div key={section.source_type} className={`rounded-xl border p-5 mb-4 ${style.bg}`}>
              <div className="flex items-center gap-2 mb-4">
                <div className={`w-2.5 h-2.5 rounded-full ${style.dot}`} />
                <span className="font-semibold text-gray-800">{section.label}</span>
                <span className="text-xs text-gray-500 ml-1">
                  {section.docs.length} item{section.docs.length !== 1 ? 's' : ''}
                </span>
                {section.is_reference && (
                  <span className="text-xs bg-orange-100 text-orange-600 border border-orange-200 px-2 py-0.5 rounded-full ml-auto">
                    Reference only
                  </span>
                )}
              </div>

              <div className="space-y-3">
                {section.docs.map((doc, i) => {
                  const key      = `${section.source_type}-${i}`
                  const isDone   = checked[key]
                  return (
                    <div
                      key={key}
                      className={`flex items-start gap-3 bg-white rounded-lg p-3 shadow-sm transition-opacity ${isDone ? 'opacity-60' : ''}`}
                    >
                      {/* Checkbox */}
                      <button
                        onClick={() => toggleCheck(key)}
                        className="shrink-0 mt-0.5 text-gray-300 hover:text-teal-500 transition-colors"
                      >
                        {isDone
                          ? <CheckCircle size={18} className="text-teal-500" />
                          : <Circle size={18} />
                        }
                      </button>

                      {/* Step number */}
                      <div className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        isDone ? 'bg-teal-100 text-teal-600' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {doc.read_order}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        {doc.url ? (
                          <a
                            href={doc.url}
                            target="_blank"
                            rel="noreferrer"
                            className={`text-sm font-medium hover:underline flex items-center gap-1 ${
                              isDone ? 'text-gray-400 line-through' : 'text-blue-600'
                            }`}
                          >
                            <span className="truncate">{doc.title}</span>
                            <ExternalLink size={11} className="shrink-0" />
                          </a>
                        ) : (
                          <span className={`text-sm font-medium ${isDone ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                            {doc.title}
                          </span>
                        )}
                        <div className="flex items-center gap-2 mt-0.5">
                          {doc.author && <span className="text-xs text-gray-400">by {doc.author}</span>}
                          {doc.stale && <span className="text-xs text-amber-500">⚠️ May be outdated</span>}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}

        {/* Completion banner */}
        {totalDocs > 0 && checkedCount === totalDocs && (
          <div className="mt-6 bg-teal-50 border border-teal-300 rounded-xl p-6 text-center">
            <div className="text-4xl mb-2">🎉</div>
            <h2 className="text-lg font-bold text-teal-800 mb-1">You're all caught up!</h2>
            <p className="text-sm text-teal-700">
              You've completed the "{decodedTopic}" learning path.
            </p>
            <button
              onClick={() => navigate('/search')}
              className="mt-4 text-sm bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 transition-colors"
            >
              Start searching EKM →
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="mt-10 text-center text-xs text-gray-400">
          Generated by EKM · Knowledge Hub · <button onClick={() => navigate('/')} className="hover:underline">Open full app</button>
        </div>
      </div>
    </div>
  )
}

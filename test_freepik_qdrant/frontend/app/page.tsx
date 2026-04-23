'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Sparkles, Search, Image, FileText, CheckCircle, Loader2, Wand2, Zap, Code2, Clock, ChevronRight } from 'lucide-react'

interface Message {
  author: string
  text: string
  type?: string
  products?: Array<{
    product_id: string
    image_url: string
    score: number
    match_percentage?: string
  }>
  searchQuery?: string
  timestamp?: number
  latency?: number
  prompt?: string
}

interface FinalAd {
  query: string
  agent_reasoning?: {
    intent: string
    categories: string[]
    features: string[]
    search_strategy: string
    reasoning: string
    search_queries?: string[]
  }
  ad_copy: {
    headline: string
    body: string
    call_to_action: string
  }
  products: Array<{
    product_id: string
    image_url: string
    score: number
  }>
  generated_images: Array<{
    prompt: string
    image_urls: string[]
  }>
  search_results?: {
    count: number
    products: Array<{
      product_id: string
      image_url: string
      score: number
      match_percentage: string
    }>
    top_match: any
  }
}

export default function Home() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [finalAd, setFinalAd] = useState<FinalAd | null>(null)
  const [currentStep, setCurrentStep] = useState<string>('')
  const [activeStepIndex, setActiveStepIndex] = useState<number>(-1)
  const [expandedPrompts, setExpandedPrompts] = useState<Set<number>>(new Set())
  const [liveAd, setLiveAd] = useState<Partial<FinalAd>>({})

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || loading) return

    setLoading(true)
    setMessages([])
    setFinalAd(null)
    setLiveAd({ query })
    setCurrentStep('Initializing...')
    setActiveStepIndex(-1)
    setExpandedPrompts(new Set())

    const startTime = Date.now()

    try {
      const response = await fetch('http://localhost:8001/api/create-ad', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query, num_products: 5, num_images: 1 }),
      })

      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || 'Failed to create ad')
      }

      // Handle streaming response (Server-Sent Events)
      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      if (!reader) {
        throw new Error('No response body')
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              const stepStartTime = Date.now()

              // Update UI based on step
              switch (data.step) {
                case 'reasoning':
                  const reasoningDetails = data.details || {}
                  setCurrentStep('Analyzing query...')
                  setActiveStepIndex(messages.length)
                  setMessages(prev => {
                    const newMsg: Message = {
                      author: 'system',
                      text: data.message,
                      type: 'response',
                      timestamp: stepStartTime,
                      latency: 0
                    }
                    return [...prev, newMsg]
                  })
                  setLiveAd(prev => ({ ...prev, agent_reasoning: reasoningDetails }))
                  break

                case 'searching':
                  const searchDetails = data.details || {}
                  setCurrentStep(`Searching ${searchDetails.search_index}/${searchDetails.total_searches}...`)
                  setActiveStepIndex(messages.length)
                  setMessages(prev => {
                    const newMsg: Message = {
                      author: 'system',
                      text: data.message,
                      type: 'response',
                      timestamp: stepStartTime,
                      latency: 0
                    }
                    return [...prev, newMsg]
                  })
                  break

                case 'search_results':
                  const resultsDetails = data.details || {}
                  setCurrentStep(`Found ${resultsDetails.count || 0} products`)
                  setActiveStepIndex(messages.length)
                  const latency = Date.now() - stepStartTime
                  setMessages(prev => {
                    const newMsg: Message = {
                      author: 'system',
                      text: `${data.message}\n\n📦 Products Found:\n${resultsDetails.results?.map((p: any, i: number) => `  ${i + 1}. ${p.product_id} (${p.match_percentage || 'N/A'})`).join('\n') || 'No products'}`,
                      type: 'response',
                      searchQuery: resultsDetails.search_query,
                      products: resultsDetails.results || [],
                      timestamp: stepStartTime,
                      latency
                    }
                    return [...prev, newMsg]
                  })
                  // Live update: Add products to right pane
                  if (resultsDetails.results) {
                    setLiveAd(prev => ({
                      ...prev,
                      products: [...(prev.products || []), ...resultsDetails.results.map((p: any) => ({
                        product_id: p.product_id,
                        image_url: p.image_url,
                        score: p.score || 0
                      }))]
                    }))
                  }
                  break

                case 'copy_generated':
                  const copyDetails = data.details || {}
                  setCurrentStep('Ad copy created')
                  setActiveStepIndex(messages.length)
                  setMessages(prev => {
                    const newMsg: Message = {
                      author: 'system',
                      text: `${data.message}\n\n✍️ Generated Copy:\n\n📰 Headline: "${copyDetails.headline || 'N/A'}"\n\n📝 Body: "${copyDetails.body || 'N/A'}"\n\n🎯 Call to Action: "${copyDetails.call_to_action || 'N/A'}"`,
                      type: 'response',
                      timestamp: stepStartTime,
                      latency: Date.now() - stepStartTime
                    }
                    return [...prev, newMsg]
                  })
                  // Live update: Add copy to right pane
                  setLiveAd(prev => ({
                    ...prev,
                    ad_copy: {
                      headline: copyDetails.headline || '',
                      body: copyDetails.body || '',
                      call_to_action: copyDetails.call_to_action || ''
                    }
                  }))
                  break

                case 'prompts_generated':
                  const promptDetails = data.details || {}
                  setCurrentStep('Prompts ready')
                  setActiveStepIndex(messages.length)
                  setMessages(prev => {
                    const newMsg: Message = {
                      author: 'system',
                      text: `${data.message}\n\n🎨 Generated ${promptDetails.count || 1} prompt(s)`,
                      type: 'response',
                      prompt: promptDetails.prompt_preview,
                      timestamp: stepStartTime,
                      latency: Date.now() - stepStartTime
                    }
                    return [...prev, newMsg]
                  })
                  break

                case 'generating_image':
                  const imgDetails = data.details || {}
                  setCurrentStep(data.message)
                  setActiveStepIndex(messages.length)
                  setMessages(prev => {
                    const newMsg: Message = {
                      author: 'system',
                      text: `${data.message}\n  Products: ${imgDetails.products?.join(', ') || 'N/A'}`,
                      type: 'response',
                      timestamp: stepStartTime,
                      latency: 0
                    }
                    return [...prev, newMsg]
                  })
                  break

                case 'image_processing':
                  const procDetails = data.details || {}
                  setCurrentStep(data.message)
                  setActiveStepIndex(messages.length)
                  setMessages(prev => {
                    const newMsg: Message = {
                      author: 'system',
                      text: `${data.message}\n  Using Nano Banana: ${procDetails.using_nano_banana ? 'Yes' : 'No'}`,
                      type: 'response',
                      timestamp: stepStartTime,
                      latency: 0
                    }
                    return [...prev, newMsg]
                  })
                  break

                case 'image_complete':
                  const completeDetails = data.details || {}
                  setCurrentStep(`Image complete`)
                  setActiveStepIndex(messages.length)
                  setMessages(prev => {
                    const newMsg: Message = {
                      author: 'system',
                      text: `${data.message}\n  Status: ${completeDetails.status || 'N/A'}\n  Images: ${completeDetails.image_count || 0}`,
                      type: 'response',
                      timestamp: stepStartTime,
                      latency: Date.now() - stepStartTime
                    }
                    return [...prev, newMsg]
                  })
                  break

                case 'complete':
                  setCurrentStep('Complete!')
                  setActiveStepIndex(-1)
                  setFinalAd({
                    query: data.query,
                    agent_reasoning: data.reasoning,
                    ad_copy: data.ad_copy,
                    products: data.products || [],
                    generated_images: data.generated_images || [],
                    search_results: data.search_results,
                  })
                  setLiveAd(prev => ({
                    ...prev,
                    generated_images: data.generated_images || []
                  }))
                  setLoading(false)
                  break

                case 'error':
                  setCurrentStep('Error occurred')
                  setActiveStepIndex(-1)
                  setMessages(prev => [...prev, {
                    author: 'system',
                    text: `Error: ${data.message}`,
                    type: 'error',
                    timestamp: stepStartTime,
                    latency: 0
                  }])
                  setLoading(false)
                  break
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e)
            }
          }
        }
      }
    } catch (error) {
      console.error('Error:', error)
      const errorMessage = error instanceof Error ? error.message : String(error)
      setMessages(prev => [...prev, {
        author: 'system',
        text: `Error: ${errorMessage}\n\nMake sure the backend API is running on http://localhost:8001`,
        type: 'error',
        timestamp: Date.now(),
        latency: 0
      }])
      setLoading(false)
      setCurrentStep('')
      setActiveStepIndex(-1)
    }
  }

  const togglePrompt = (index: number) => {
    setExpandedPrompts(prev => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }

  const [showHistory, setShowHistory] = useState(false)
  const [historyItems, setHistoryItems] = useState<any[]>([])

  const fetchHistory = async () => {
    try {
      const res = await fetch('http://localhost:8001/api/history')
      if (res.ok) {
        const data = await res.json()
        setHistoryItems(data)
        setShowHistory(true)
      }
    } catch (e) {
      console.error('Failed to fetch history:', e)
    }
  }

  const loadHistoryItem = async (filename: string) => {
    try {
      setLoading(true)
      setShowHistory(false)
      const res = await fetch(`http://localhost:8001/api/history/${filename}`)
      if (res.ok) {
        const data = await res.json()
        setQuery(data.query)
        setFinalAd(data)
        setLiveAd(data)

        // Reconstruct messages from data
        const newMessages: Message[] = []

        // Reasoning message
        if (data.reasoning) {
          newMessages.push({
            author: 'system',
            text: data.reasoning.reasoning || 'Analysis complete',
            type: 'response',
            timestamp: Date.now(),
            latency: 0
          })
        }

        // Search results message
        if (data.search_results) {
          newMessages.push({
            author: 'system',
            text: `Found ${data.search_results.count} products`,
            type: 'response',
            products: data.search_results.products,
            timestamp: Date.now(),
            latency: 0
          })
        }

        // Copy message
        if (data.ad_copy) {
          newMessages.push({
            author: 'system',
            text: `Generated Copy:\n\n📰 Headline: "${data.ad_copy.headline}"\n\n📝 Body: "${data.ad_copy.body}"`,
            type: 'response',
            timestamp: Date.now(),
            latency: 0
          })
        }

        // Image message
        if (data.generated_images && data.generated_images.length > 0) {
          newMessages.push({
            author: 'system',
            text: `Generated ${data.generated_images.length} image(s)`,
            type: 'response',
            timestamp: Date.now(),
            latency: 0
          })
        }

        setMessages(newMessages)
        setCurrentStep('Loaded from history')
      }
    } catch (e) {
      console.error('Failed to load history item:', e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 relative">
      {/* History Sidebar */}
      {showHistory && (
        <div className="absolute inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex justify-end">
          <div className="w-96 bg-slate-900 h-full border-l border-slate-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h2 className="font-semibold text-white flex items-center gap-2">
                <Clock className="w-4 h-4" />
                History
              </h2>
              <button
                onClick={() => setShowHistory(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {historyItems.map((item) => (
                <button
                  key={item.filename}
                  onClick={() => loadHistoryItem(item.filename)}
                  className="w-full text-left p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 border border-slate-700 hover:border-violet-500/50 transition-all group"
                >
                  <div className="flex items-start gap-3">
                    {item.image_url ? (
                      <div className="w-16 h-16 rounded bg-slate-900 overflow-hidden flex-shrink-0">
                        <img src={item.image_url} alt="" className="w-full h-full object-cover" />
                      </div>
                    ) : (
                      <div className="w-16 h-16 rounded bg-slate-900 flex items-center justify-center flex-shrink-0">
                        <FileText className="w-6 h-6 text-slate-700" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white truncate group-hover:text-violet-300 transition-colors">
                        {item.query}
                      </p>
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                        {item.headline || 'No headline'}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-2 font-mono">
                        {new Date(item.timestamp * 1000).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
              {historyItems.length === 0 && (
                <div className="text-center py-8 text-slate-500 text-sm">
                  No history yet
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-xl border-b border-slate-800">
        <div className="max-w-full mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600">
                <Wand2 className="w-4 h-4 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-semibold tracking-tight text-white">
                  Ad Generation Agent
                </h1>
                <p className="text-xs text-slate-400 font-mono">
                  Qdrant, Google ADK Powered by Gemini, Freepik Image Studio Powered by Nano Banana
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={fetchHistory}
                className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors font-mono flex items-center gap-2"
              >
                <Clock className="w-4 h-4" />
                History
              </button>
              <Link
                href="/about"
                className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors font-mono"
              >
                About
              </Link>
              <form onSubmit={handleSubmit} className="flex items-center gap-2">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter ad query..."
                  className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all font-mono"
                  disabled={loading}
                  autoComplete="off"
                />
                <button
                  type="submit"
                  disabled={loading || !query.trim()}
                  className="px-4 py-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 disabled:from-slate-700 disabled:to-slate-700 text-white text-sm font-semibold rounded-lg transition-all flex items-center gap-2 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="text-xs">{currentStep}</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      <span>Generate</span>
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
      </header>

      {/* Split View Layout */}
      <div className="flex h-[calc(100vh-73px)] overflow-hidden">
        {/* Left Pane: Agent Progress Log (40%) */}
        <div className="w-[40%] border-r border-slate-800 bg-slate-900/50 flex flex-col">
          <div className="px-6 py-4 border-b border-slate-800">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Code2 className="w-4 h-4" />
                Agent Pipeline
              </h2>
              {loading && (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <div className="w-2 h-2 bg-violet-500 rounded-full animate-pulse"></div>
                  <span className="font-mono">Live</span>
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
            {/* Agent Reasoning Block - Special Treatment */}
            {liveAd.agent_reasoning && (
              <div className="mb-6 p-4 bg-slate-800/50 border border-violet-500/20 rounded-lg">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-4 h-4 text-violet-400" />
                  <h3 className="text-xs font-semibold text-violet-400 uppercase tracking-wider">Reasoning</h3>
                </div>
                <div className="space-y-2 text-xs font-mono text-slate-300 leading-relaxed">
                  {liveAd.agent_reasoning.search_queries && liveAd.agent_reasoning.search_queries.length > 0 && (
                    <div>
                      <span className="text-slate-500">queries:</span>
                      <div className="ml-4 mt-1 space-y-1">
                        {liveAd.agent_reasoning.search_queries.map((q, i) => (
                          <div key={i} className="text-violet-300">"{q}"</div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div>
                    <span className="text-slate-500">intent:</span>
                    <span className="ml-2 text-slate-300">"{liveAd.agent_reasoning.intent}"</span>
                  </div>
                  <div>
                    <span className="text-slate-500">strategy:</span>
                    <span className="ml-2 text-slate-300">{liveAd.agent_reasoning.search_strategy}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Timeline Messages */}
            {messages.map((message, index) => {
              const isActive = index === activeStepIndex
              const isCompleted = index < activeStepIndex
              const hasPrompt = !!message.prompt

              return (
                <div
                  key={index}
                  className={`relative pl-8 pb-4 border-l-2 transition-all duration-300 ${isActive
                    ? 'border-violet-500 bg-violet-500/10'
                    : isCompleted
                      ? 'border-slate-700 opacity-60'
                      : 'border-slate-800'
                    }`}
                >
                  {/* Timeline Dot */}
                  <div className={`absolute left-[-6px] top-0 w-3 h-3 rounded-full border-2 transition-all ${isActive
                    ? 'bg-violet-500 border-violet-400 shadow-lg shadow-violet-500/50 animate-pulse'
                    : isCompleted
                      ? 'bg-slate-600 border-slate-700'
                      : 'bg-slate-700 border-slate-800'
                    }`} />

                  <div className={`space-y-2 transition-all ${isActive ? '' : isCompleted ? 'opacity-50' : ''
                    }`}>
                    {/* Header with Latency */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {message.author === 'ad_generation_agent' ? (
                          <Sparkles className="w-3.5 h-3.5 text-violet-400" />
                        ) : (
                          <CheckCircle className={`w-3.5 h-3.5 ${isCompleted ? 'text-slate-600' : 'text-emerald-400'}`} />
                        )}
                        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                          {message.author === 'ad_generation_agent' ? 'Agent' : 'System'}
                        </span>
                      </div>
                      {message.latency !== undefined && message.latency > 0 && (
                        <div className="flex items-center gap-1 px-2 py-0.5 bg-slate-800 rounded text-xs font-mono text-slate-400">
                          <Clock className="w-3 h-3" />
                          <span>{message.latency}ms</span>
                        </div>
                      )}
                    </div>

                    {/* Message Text */}
                    <p className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed font-mono">
                      {message.text}
                    </p>

                    {/* Structured Data: Products */}
                    {message.products && message.products.length > 0 && (
                      <div className="mt-3 p-3 bg-slate-800/50 rounded border border-slate-700">
                        <div className="text-xs text-slate-500 mb-2 font-mono">products: [{message.products.length}]</div>
                        <div className="grid grid-cols-3 gap-2">
                          {message.products.map((product: any, pIdx: number) => (
                            <div key={pIdx} className="bg-slate-900 rounded p-1.5 border border-slate-700">
                              <div className="aspect-square bg-slate-800 rounded mb-1 overflow-hidden">
                                <img
                                  src={product.image_url || ''}
                                  alt={product.product_id}
                                  className="w-full h-full object-contain"
                                  onError={(e) => {
                                    const target = e.target as HTMLImageElement
                                    target.style.display = 'none'
                                  }}
                                />
                              </div>
                              <p className="text-[10px] font-mono text-slate-400 truncate">{product.product_id}</p>
                              <p className="text-[10px] text-emerald-400">{product.match_percentage}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Code Peek: Prompt */}
                    {hasPrompt && (
                      <div className="mt-2">
                        <button
                          onClick={() => togglePrompt(index)}
                          className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 transition-colors"
                        >
                          <Code2 className="w-3 h-3" />
                          <span>{expandedPrompts.has(index) ? 'Hide' : 'View'} Prompt</span>
                        </button>
                        {expandedPrompts.has(index) && (
                          <div className="mt-2 p-3 bg-slate-950 rounded border border-slate-700">
                            <pre className="text-xs font-mono text-slate-400 whitespace-pre-wrap overflow-x-auto">
                              {message.prompt}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right Pane: Live Canvas (60%) */}
        <div className="flex-1 bg-slate-950 overflow-y-auto">
          <div className="px-8 py-6">
            <div className="mb-6">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <Image className="w-4 h-4" />
                Live Assembly
              </h2>
            </div>

            {/* Skeleton/Live Ad */}
            {loading || liveAd.query || finalAd ? (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                {/* Ad Copy Section - Live Update */}
                {liveAd.ad_copy ? (
                  <div className="relative overflow-hidden bg-gradient-to-br from-violet-900/20 via-purple-900/20 to-pink-900/20 rounded-2xl p-12 border border-violet-500/20 shadow-xl">
                    <div className="relative z-10">
                      <div className="mb-4">
                        <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-violet-500/20 text-violet-300 border border-violet-500/30">
                          <CheckCircle className="w-3 h-3" />
                          Copy Generated
                        </span>
                      </div>
                      <h2 className="text-5xl md:text-6xl font-bold text-white mb-6 leading-tight tracking-tight">
                        {liveAd.ad_copy.headline}
                      </h2>
                      <p className="text-xl text-slate-300 mb-8 leading-relaxed max-w-2xl">
                        {liveAd.ad_copy.body}
                      </p>
                      <button className="px-8 py-4 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-violet-500/30">
                        {liveAd.ad_copy.call_to_action}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-900/50 rounded-2xl p-12 border border-slate-800">
                    <div className="h-8 bg-slate-800 rounded w-3/4 mb-4 animate-pulse"></div>
                    <div className="h-4 bg-slate-800 rounded w-full mb-2 animate-pulse"></div>
                    <div className="h-4 bg-slate-800 rounded w-5/6 animate-pulse"></div>
                  </div>
                )}

                {/* Generated Image - Live Update */}
                {liveAd.generated_images && liveAd.generated_images.length > 0 ? (
                  <div>
                    <div className="mb-4">
                      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Generated Image</h3>
                    </div>
                    {liveAd.generated_images.map((img, index) => (
                      <div key={index} className="space-y-4">
                        {img.image_urls && img.image_urls.length > 0 ? (
                          <div className="relative w-full bg-slate-900 rounded-2xl overflow-hidden shadow-2xl border border-slate-800">
                            <img
                              src={img.image_urls[0]}
                              alt={img.prompt}
                              className="w-full h-auto object-contain"
                              style={{ maxHeight: '600px' }}
                              onError={(e) => {
                                e.currentTarget.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="300"%3E%3Crect fill="%231e293b" width="400" height="300"/%3E%3Ctext fill="%23475569" font-family="monospace" font-size="14" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3EImage failed to load%3C/text%3E%3C/svg%3E';
                              }}
                            />
                          </div>
                        ) : (
                          <div className="relative aspect-video bg-slate-900 rounded-2xl flex items-center justify-center border border-slate-800">
                            <div className="text-center">
                              <Loader2 className="w-8 h-8 animate-spin text-slate-600 mx-auto mb-2" />
                              <p className="text-sm text-slate-500 font-mono">Rendering image...</p>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="bg-slate-900/50 rounded-2xl aspect-video border border-slate-800 flex items-center justify-center">
                    <div className="text-center">
                      <Image className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                      <p className="text-sm text-slate-500 font-mono">Waiting for image generation...</p>
                    </div>
                  </div>
                )}

                {/* Products Grid - Live Update */}
                {liveAd.products && liveAd.products.length > 0 ? (
                  <div>
                    <div className="mb-4">
                      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                        Featured Products ({liveAd.products.length})
                      </h3>
                      <p className="text-xs text-slate-500 mt-1 font-mono">Squid shopping queries dataset • 150k+ items</p>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                      {liveAd.products.map((product, index) => (
                        <div key={index} className="group bg-slate-900/50 border border-slate-800 rounded-xl p-4 transition-all duration-200 hover:border-slate-700 hover:bg-slate-900">
                          <div className="aspect-square bg-slate-950 rounded-lg mb-3 overflow-hidden border border-slate-800">
                            <img
                              src={product.image_url}
                              alt={product.product_id}
                              className="w-full h-full object-contain p-2 transition-transform duration-200 group-hover:scale-105"
                              onError={(e) => {
                                e.currentTarget.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="200"%3E%3Crect fill="%230f172a" width="200" height="200"/%3E%3Ctext fill="%23334155" font-family="monospace" font-size="12" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3EN/A%3C/text%3E%3C/svg%3E';
                              }}
                            />
                          </div>
                          <p className="text-xs font-mono text-slate-400 truncate mb-1">
                            {product.product_id}
                          </p>
                          <p className="text-xs font-semibold text-emerald-400">
                            {((product.score || 0) * 100).toFixed(1)}% match
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-900/50 rounded-2xl p-8 border border-slate-800">
                    <div className="text-center">
                      <Search className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                      <p className="text-sm text-slate-500 font-mono">Waiting for product search...</p>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Wand2 className="w-16 h-16 text-slate-700 mx-auto mb-4" />
                  <p className="text-sm text-slate-500 font-mono">Enter a query to begin</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

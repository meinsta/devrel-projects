'use client'

import Link from 'next/link'
import { ArrowLeft, Sparkles, Search, Image, FileText, Zap, Code2, Database, Wand2 } from 'lucide-react'

export default function About() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-slate-900/80 backdrop-blur-xl border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link href="/" className="p-2 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 hover:opacity-80 transition-opacity">
                <ArrowLeft className="w-4 h-4 text-white" />
              </Link>
              <div>
                <h1 className="text-lg font-semibold tracking-tight text-white">
                  How It Works
                </h1>
                <p className="text-xs text-slate-400 font-mono">
                  Architecture & Pipeline
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
        {/* Hero Section */}
        <div className="mb-12">
          <h1 className="text-4xl font-bold text-white mb-4">
            Ad Generation Agent
          </h1>
          <p className="text-xl text-slate-300 leading-relaxed">
            An AI-powered system that creates complete advertisements from simple text queries. 
            Watch the agent think, search, and create in real-time.
          </p>
        </div>

        {/* Architecture Overview */}
        <div className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
            <Code2 className="w-6 h-6 text-violet-400" />
            Architecture
          </h2>
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
            <div className="space-y-4 text-sm font-mono text-slate-300">
              <div className="flex items-start gap-4">
                <Database className="w-5 h-5 text-violet-400 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="text-violet-400 mb-1">Qdrant Vector Database</div>
                  <div className="text-slate-400">Searches 150k+ products from Squid shopping queries dataset using CLIP embeddings</div>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <Wand2 className="w-5 h-5 text-violet-400 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="text-violet-400 mb-1">Google ADK + Gemini</div>
                  <div className="text-slate-400">Orchestrates workflow, analyzes queries, generates prompts and ad copy</div>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <Image className="w-5 h-5 text-violet-400 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="text-violet-400 mb-1">Freepik Image Studio</div>
                  <div className="text-slate-400">Powered by Nano Banana (Gemini 2.5 Flash) for image generation with product references</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Pipeline Steps */}
        <div className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
            <Zap className="w-6 h-6 text-violet-400" />
            Pipeline
          </h2>
          
          <div className="space-y-6">
            {/* Step 1 */}
            <div className="relative pl-8 pb-6 border-l-2 border-violet-500/30">
              <div className="absolute left-[-6px] top-0 w-3 h-3 rounded-full bg-violet-500 border-2 border-slate-900"></div>
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
                <div className="flex items-center gap-3 mb-3">
                  <Search className="w-5 h-5 text-violet-400" />
                  <h3 className="text-lg font-semibold text-white">1. Query Analysis & Product Search</h3>
                </div>
                <p className="text-slate-300 mb-4 leading-relaxed">
                  The agent uses Gemini to analyze your query and break it down into 3-5 diverse search queries. 
                  This ensures variety in the final ad—for example, "thanksgiving dinner" becomes searches for 
                  "turkey", "board games", "carving knife", etc.
                </p>
                <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                  <div className="text-xs text-slate-500 mb-2 font-mono">Example:</div>
                  <div className="text-sm font-mono text-slate-300">
                    <div className="text-violet-400">Query:</div>
                    <div className="ml-4">"cozy thanksgiving dinner"</div>
                    <div className="text-violet-400 mt-2">Searches Generated:</div>
                    <div className="ml-4 space-y-1">
                      <div>1. "thanksgiving themed throw blankets"</div>
                      <div>2. "fall scented candles"</div>
                      <div>3. "cozy thanksgiving mugs"</div>
                      <div>4. "autumn harvest table centerpiece"</div>
                      <div>5. "rustic thanksgiving placemats"</div>
                    </div>
                  </div>
                </div>
                <p className="text-sm text-slate-400 mt-4">
                  Each search queries Qdrant's vector database (150k+ products) using CLIP embeddings for semantic similarity.
                  One best product is selected from each search to ensure diversity.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="relative pl-8 pb-6 border-l-2 border-violet-500/30">
              <div className="absolute left-[-6px] top-0 w-3 h-3 rounded-full bg-violet-500 border-2 border-slate-900"></div>
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
                <div className="flex items-center gap-3 mb-3">
                  <FileText className="w-5 h-5 text-violet-400" />
                  <h3 className="text-lg font-semibold text-white">2. Ad Copy Generation</h3>
                </div>
                <p className="text-slate-300 mb-4 leading-relaxed">
                  Gemini generates world-class ad copy with a minimalistic, clean style. The copywriter prompt 
                  is designed to create headlines, body text, and CTAs that feel like premium brand advertisements— 
                  no product codes or long paragraphs.
                </p>
                <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                  <div className="text-xs text-slate-500 mb-2 font-mono">Output:</div>
                  <div className="text-sm font-mono text-slate-300 space-y-2">
                    <div>
                      <span className="text-violet-400">Headline:</span>
                      <div className="ml-4">"Gather. Grateful. Cozy."</div>
                    </div>
                    <div>
                      <span className="text-violet-400">Body:</span>
                      <div className="ml-4">"Thanksgiving memories, made brighter with shared moments and simple comforts."</div>
                    </div>
                    <div>
                      <span className="text-violet-400">CTA:</span>
                      <div className="ml-4">"Shop the Cozy"</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Step 3 */}
            <div className="relative pl-8 pb-6 border-l-2 border-violet-500/30">
              <div className="absolute left-[-6px] top-0 w-3 h-3 rounded-full bg-violet-500 border-2 border-slate-900"></div>
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
                <div className="flex items-center gap-3 mb-3">
                  <Sparkles className="w-5 h-5 text-violet-400" />
                  <h3 className="text-lg font-semibold text-white">3. Image Prompt Generation</h3>
                </div>
                <p className="text-slate-300 mb-4 leading-relaxed">
                  Gemini creates a single, detailed image generation prompt that incorporates ALL selected products 
                  (one from each search) into a realistic, cohesive scene. The prompt emphasizes natural product 
                  placement, realistic composition, and includes the ad copy text directly in the image.
                </p>
                <p className="text-sm text-slate-400">
                  The prompt ensures products are on surfaces (not floating), have realistic shadows, and the 
                  text is naturally integrated into the composition.
                </p>
              </div>
            </div>

            {/* Step 4 */}
            <div className="relative pl-8 pb-6 border-l-2 border-violet-500/30">
              <div className="absolute left-[-6px] top-0 w-3 h-3 rounded-full bg-violet-500 border-2 border-slate-900"></div>
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
                <div className="flex items-center gap-3 mb-3">
                  <Image className="w-5 h-5 text-violet-400" />
                  <h3 className="text-lg font-semibold text-white">4. Image Generation with Freepik</h3>
                </div>
                <p className="text-slate-300 mb-4 leading-relaxed">
                  The system uses Freepik's Image Studio powered by Nano Banana (Gemini 2.5 Flash). Product images 
                  from Qdrant are downloaded, converted to base64, and sent as reference images to ensure the 
                  generated ad accurately features the actual products.
                </p>
                <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                  <div className="text-xs text-slate-500 mb-2 font-mono">Process:</div>
                  <div className="text-sm font-mono text-slate-300 space-y-1">
                    <div>1. Download product images from Qdrant URLs</div>
                    <div>2. Convert to base64 data URLs</div>
                    <div>3. Send to Freepik API with prompt + reference_images</div>
                    <div>4. Poll for completion (Nano Banana endpoint)</div>
                    <div>5. Download generated image and convert to data URL</div>
                  </div>
                </div>
                <p className="text-sm text-slate-400 mt-4">
                  Nano Banana (Gemini 2.5 Flash) accepts up to 3 reference images and generates a single image 
                  that incorporates all products naturally into the scene with the ad copy text included.
                </p>
              </div>
            </div>

            {/* Step 5 */}
            <div className="relative pl-8 border-l-2 border-violet-500/30">
              <div className="absolute left-[-6px] top-0 w-3 h-3 rounded-full bg-violet-500 border-2 border-slate-900"></div>
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
                <div className="flex items-center gap-3 mb-3">
                  <Zap className="w-5 h-5 text-violet-400" />
                  <h3 className="text-lg font-semibold text-white">5. Final Assembly</h3>
                </div>
                <p className="text-slate-300 leading-relaxed">
                  The complete advertisement is assembled with the generated image, ad copy, and featured products. 
                  All components are streamed to the frontend in real-time via Server-Sent Events (SSE), allowing 
                  you to watch the entire pipeline execute step-by-step.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Technical Details */}
        <div className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-6">Technical Stack</h2>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-violet-400 mb-3 uppercase tracking-wider">Backend</h3>
              <ul className="space-y-2 text-sm text-slate-300 font-mono">
                <li>• FastAPI (Python)</li>
                <li>• Google ADK Framework</li>
                <li>• Gemini 2.0 Flash (text)</li>
                <li>• Qdrant Vector DB</li>
                <li>• Freepik API</li>
                <li>• Server-Sent Events (SSE)</li>
              </ul>
            </div>
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-violet-400 mb-3 uppercase tracking-wider">Frontend</h3>
              <ul className="space-y-2 text-sm text-slate-300 font-mono">
                <li>• Next.js 14 (React)</li>
                <li>• TypeScript</li>
                <li>• Tailwind CSS</li>
                <li>• Real-time SSE streaming</li>
                <li>• Split-screen observability</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Data Source */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Database className="w-5 h-5 text-violet-400" />
            Data Source
          </h2>
          <p className="text-slate-300 leading-relaxed">
            Product images are sourced from the <span className="font-mono text-violet-400">Squid shopping queries dataset</span>, 
            containing <span className="font-semibold text-white">150,000+ items</span>. The dataset includes product images 
            with CLIP embeddings, enabling semantic search across a massive catalog of real products.
          </p>
        </div>
      </main>
    </div>
  )
}




'use client';

import { useState } from 'react';
import { Search, Scale, Trophy, BarChart3, BookOpen, Settings, FileText, Loader2, ChevronRight, CheckCircle, ListChecks } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import SearchInterface from '@/components/SearchInterface';
import AgentFlow from '@/components/AgentFlow';
import ResultsDisplay from '@/components/ResultsDisplay';

export default function DashboardPage() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'search' | 'workflow'>('search');
  const [isSearching, setIsSearching] = useState(false);
  const [agentSteps, setAgentSteps] = useState<any[]>([]);
  const [agentOutput, setAgentOutput] = useState<string[]>([]);
  const [results, setResults] = useState<any>(null);
  const [showVerbose, setShowVerbose] = useState(false);

  const handleSearch = async (searchQuery: string, searchMode: 'search' | 'workflow', city?: string) => {
    setQuery(searchQuery);
    setMode(searchMode);
    setIsSearching(true);
    setAgentSteps([]);
    setAgentOutput([]);
    setResults(null);

    try {
      const endpoint = searchMode === 'search' ? '/api/research' : '/api/workflow';
      const body = searchMode === 'search' 
        ? { query: searchQuery }
        : { query: searchQuery, city: city || undefined };
      
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'step') {
                setAgentSteps(prev => [...prev, data]);
              } else if (data.type === 'agent_output') {
                setAgentOutput(prev => [...prev, data.line]);
              } else if (data.type === 'result') {
                setResults(data);
                setIsSearching(false);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Search error:', error);
      setIsSearching(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="hidden w-64 border-r bg-muted/40 lg:block">
        <div className="flex h-full flex-col gap-2">
          {/* Logo */}
          <div className="flex h-[60px] items-center border-b px-6">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <Scale className="h-6 w-6 text-primary" />
              <span className="text-lg">Legal Research</span>
            </Link>
          </div>

          {/* Navigation */}
          <div className="flex-1 overflow-auto py-2">
            <nav className="grid gap-1 px-4">
              <Button variant="default" className="w-full justify-start gap-2 text-base">
                <Search className="h-5 w-5" />
                Search
              </Button>
              <Link href="/quiz">
                <Button variant="ghost" className="w-full justify-start gap-2 text-base">
                  <Trophy className="h-5 w-5" />
                  Quiz Mode
                </Button>
              </Link>
              <Link href="/experiments">
                <Button variant="ghost" className="w-full justify-start gap-2 text-base">
                  <BarChart3 className="h-5 w-5" />
                  Experiments
                </Button>
              </Link>
              <Button variant="ghost" className="w-full justify-start gap-2 text-base">
                <BookOpen className="h-5 w-5" />
                Browse Statutes
              </Button>
            </nav>

            {/* Stats in Sidebar */}
            <div className="mx-4 mt-6">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">System Stats</CardTitle>
                  <CardDescription className="text-xs">Real-time metrics</CardDescription>
                </CardHeader>
                <CardContent className="text-sm space-y-2">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Statutes</span>
                    <span className="font-semibold">155,974</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Model</span>
                    <span className="font-semibold">GPT-4o-mini</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Embedding</span>
                    <span className="font-semibold">bge-small</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Search</span>
                    <span className="font-semibold">Hybrid RRF</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Settings */}
          <div className="mt-auto border-t p-4">
            <Button variant="ghost" className="w-full justify-start gap-2 text-base">
              <Settings className="h-5 w-5" />
              Settings
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col">
        {/* Top Bar */}
        <header className="flex h-[60px] items-center gap-4 border-b bg-background px-6">
          <div className="flex-1">
            <h1 className="text-xl font-semibold">California Housing Law Research</h1>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">Qdrant</Badge>
            <Badge variant="outline">CrewAI</Badge>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">
          <div className="mx-auto max-w-7xl space-y-6">
            {/* Search Interface */}
            <SearchInterface onSearch={handleSearch} isSearching={isSearching} />

            {/* Results Section */}
            {(agentSteps.length > 0 || agentOutput.length > 0 || results) && (
              <div className="grid gap-6 lg:grid-cols-3">
                {/* Agent Process (Left Sidebar) */}
                <div className="lg:col-span-1 space-y-4">
                  {agentSteps.length > 0 && (
                    <AgentFlow steps={agentSteps} isSearching={isSearching} />
                  )}
                  
                  {agentOutput.length > 0 && (
                    <Card className="bg-slate-900 text-slate-100 border-slate-700">
                      <CardHeader className="cursor-pointer" onClick={() => setShowVerbose(!showVerbose)}>
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-sm font-mono text-green-400">
                            ▸ Agent Process ({agentOutput.length} lines)
                          </CardTitle>
                          <ChevronRight className={`h-4 w-4 transition-transform ${showVerbose ? 'rotate-90' : ''}`} />
                        </div>
                      </CardHeader>
                      {showVerbose && (
                        <CardContent>
                          <div className="space-y-1 text-xs font-mono">
                            {agentOutput.map((line, i) => (
                              <div key={i} className="text-green-400">{line}</div>
                            ))}
                          </div>
                        </CardContent>
                      )}
                    </Card>
                  )}
                </div>

                {/* Results (Main Area) */}
                <div className="lg:col-span-2">
                  {results && mode === 'search' && <ResultsDisplay results={results} query={query} />}
                  {results && mode === 'workflow' && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <ListChecks className="h-6 w-6 text-purple-600" />
                          Generated Workflow
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="whitespace-pre-wrap font-sans text-base leading-relaxed text-gray-800">
                          {results.workflow}
                        </pre>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>
            )}

            {/* Empty State */}
            {agentSteps.length === 0 && !results && !isSearching && (
              <div className="text-center py-12">
                <div className="mx-auto max-w-4xl space-y-6">
                  <FileText className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                  <div>
                    <h3 className="text-3xl font-semibold text-foreground mb-2">
                      From statute to step-by-step—in seconds, with receipts.
                    </h3>
                    <p className="text-muted-foreground text-xl">
                      California housing law, operationalized: verified cites, transparent search,
                      and hybrid retrieval across 155,974+ statutes.
                    </p>
                  </div>

                  <div className="flex items-center justify-center gap-6">
                    <div className="text-base text-muted-foreground">Powered by:</div>
                    <Badge variant="secondary" className="text-base px-4 py-2">
                      Qdrant - Hybrid Search + RRF
                    </Badge>
                    <Badge variant="secondary" className="text-base px-4 py-2">
                      CrewAI - Agentic Workflows
                    </Badge>
                  </div>

                  {/* Feature Cards */}
                  <div className="grid gap-4 md:grid-cols-3 mt-8">
                    <Card>
                      <CardHeader>
                        <div className="flex items-center gap-2 text-blue-600">
                          <Search className="h-5 w-5" />
                          <CardTitle className="text-base">Locate Controlling Law</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <p className="text-sm text-muted-foreground">• Surface governing sections instantly</p>
                        <p className="text-sm text-muted-foreground">• Civil Code + Code of Civ. Proc.</p>
                        <p className="text-sm text-muted-foreground">• Hybrid search (semantic + keyword)</p>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <div className="flex items-center gap-2 text-green-600">
                          <ChevronRight className="h-5 w-5" />
                          <CardTitle className="text-base">Verify Every Claim</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <p className="text-sm text-muted-foreground">• Line-level verbatim quotes</p>
                        <p className="text-sm text-muted-foreground">• Statute § links</p>
                        <p className="text-sm text-muted-foreground">• Defensible citations</p>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <div className="flex items-center gap-2 text-purple-600">
                          <CheckCircle className="h-5 w-5" />
                          <CardTitle className="text-base">Transparent Process</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <p className="text-sm text-muted-foreground">• See exactly how AI searches</p>
                        <p className="text-sm text-muted-foreground">• Confidence scores</p>
                        <p className="text-sm text-muted-foreground">• Know when to escalate</p>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Audience */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-8">
                    <Card className="text-center p-4 bg-blue-50 border-blue-200">
                      <CardTitle className="text-base text-blue-900">Attorneys</CardTitle>
                      <CardDescription className="text-sm text-blue-700">Defensible workflows</CardDescription>
                    </Card>
                    <Card className="text-center p-4 bg-purple-50 border-purple-200">
                      <CardTitle className="text-base text-purple-900">Paralegals</CardTitle>
                      <CardDescription className="text-sm text-purple-700">Quote-verified memos</CardDescription>
                    </Card>
                    <Card className="text-center p-4 bg-green-50 border-green-200">
                      <CardTitle className="text-base text-green-900">Property Mgrs</CardTitle>
                      <CardDescription className="text-sm text-green-700">Plain-English steps</CardDescription>
                    </Card>
                    <Card className="text-center p-4 bg-orange-50 border-orange-200">
                      <CardTitle className="text-base text-orange-900">Advocates</CardTitle>
                      <CardDescription className="text-sm text-orange-700">Tenant defenses</CardDescription>
                    </Card>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t bg-muted/40 px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4 text-sm text-muted-foreground">
            <div className="flex flex-wrap items-center gap-4">
              <span>Last updated: 2021</span>
              <span>•</span>
              <span>Temp: 0.3</span>
              <span>•</span>
              <span>Top-k: 20</span>
              <span>•</span>
              <span>Fusion: RRF</span>
            </div>
            <span>Powered by Qdrant + CrewAI</span>
          </div>
        </footer>
      </div>
    </div>
  );
}


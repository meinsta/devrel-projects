'use client';

import { useState, useEffect } from 'react';
import { Trophy, CheckCircle, XCircle, RefreshCw, ArrowLeft, Loader2 } from 'lucide-react';
import Link from 'next/link';

interface QuizQuestion {
  question: string;
  golden_answer: string;
  golden_statute_ids: number[];
  golden_citations: string[];
  question_idx: number;
}

interface QuizResult {
  ai_answer?: string;
  retrieved_statutes: any[];
  recall: number;
  precision: number;
  ai_correct: boolean;
  retrieved_count?: number;
  golden_count?: number;
}

export default function QuizMode() {
  const [currentQuestion, setCurrentQuestion] = useState<QuizQuestion | null>(null);
  const [userAnswer, setUserAnswer] = useState<string>('');
  const [aiResult, setAiResult] = useState<QuizResult | null>(null);
  const [userSubmitted, setUserSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [score, setScore] = useState({ user: 0, ai: 0, total: 0 });
  const [agentOutput, setAgentOutput] = useState<string[]>([]);

  const loadNewQuestion = async () => {
    setLoading(true);
    setUserAnswer('');
    setUserSubmitted(false);
    setAiResult(null);
    setAgentOutput([]);

    try {
      const response = await fetch('http://localhost:8000/api/quiz/question');
      
      if (!response.ok) {
        const error = await response.json();
        console.error('Quiz error:', error);
        setCurrentQuestion(null);
        setLoading(false);
        return;
      }
      
      const data = await response.json();
      setCurrentQuestion(data);
    } catch (error) {
      console.error('Error loading question:', error);
      setCurrentQuestion(null);
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async () => {
    if (!currentQuestion || !userAnswer) return;
    
    setLoading(true);
    setUserSubmitted(true);
    setAgentOutput([]);
    
    try {
      const response = await fetch('http://localhost:8000/api/quiz/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: currentQuestion.question,
          golden_answer: currentQuestion.golden_answer,
          golden_statute_ids: currentQuestion.golden_statute_ids,
          user_answer: userAnswer,
        }),
      });
      
      // Read streaming response
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
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.type === 'agent_output') {
                  // Add CrewAI verbose output
                  setAgentOutput(prev => [...prev, data.line]);
                } else if (data.type === 'result') {
                  // Final result
                  console.log('Received result:', data);
                  setAiResult(data);
                  setLoading(false);
                  
                  // Update scores
                  const userCorrect = userAnswer.toLowerCase() === currentQuestion.golden_answer.toLowerCase();
                  setScore(prev => ({
                    user: prev.user + (userCorrect ? 1 : 0),
                    ai: prev.ai + (data.ai_correct ? 1 : 0),
                    total: prev.total + 1
                  }));
                } else if (data.type === 'user_result') {
                  // User result confirmation
                  console.log('User result:', data);
                } else if (data.type === 'agent_step') {
                  // Agent step update
                  setAgentOutput(prev => [...prev, `[${data.step}] ${data.detail || ''}`]);
                }
              } catch (e) {
                console.error('Error parsing SSE data:', e, 'Line:', line);
              }
            }
          }
        }
      }
      
    } catch (error) {
      console.error('Error submitting answer:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNewQuestion();
  }, []);

  const userCorrect = userSubmitted && currentQuestion?.golden_answer && 
                      userAnswer.toLowerCase() === currentQuestion.golden_answer.toLowerCase();

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50 to-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Trophy className="h-8 w-8 text-purple-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Quiz Mode
                </h1>
                <p className="text-sm text-gray-600">
                  Test yourself vs. AI on California housing law
                </p>
              </div>
            </div>
            <Link
              href="/"
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Search
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Scoreboard */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6 border border-gray-200">
          <div className="grid grid-cols-3 gap-6 text-center">
            <div>
              <div className="text-3xl font-bold text-blue-600">{score.user}/{score.total}</div>
              <div className="text-sm text-gray-600">Your Score</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-purple-600">{score.ai}/{score.total}</div>
              <div className="text-sm text-gray-600">AI Score</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-gray-900">{score.total}</div>
              <div className="text-sm text-gray-600">Questions</div>
            </div>
          </div>
        </div>

        {/* Question */}
        {currentQuestion && (
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6 border border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">
              Question {score.total + 1}
            </h2>
            <p className="text-lg text-gray-800 leading-relaxed mb-6">
              {currentQuestion.question}
            </p>

            {!userSubmitted ? (
              <div className="space-y-4">
                <div className="flex gap-4">
                  <button
                    onClick={() => setUserAnswer('Yes')}
                    className={`flex-1 py-3 px-6 rounded-lg border-2 font-medium transition-all ${
                      userAnswer === 'Yes'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => setUserAnswer('No')}
                    className={`flex-1 py-3 px-6 rounded-lg border-2 font-medium transition-all ${
                      userAnswer === 'No'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
                    }`}
                  >
                    No
                  </button>
                </div>
                <button
                  onClick={submitAnswer}
                  disabled={!userAnswer || loading}
                  className="w-full py-3 px-6 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Checking...' : 'Submit Answer'}
                </button>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Results Comparison */}
                <div className="grid grid-cols-3 gap-4">
                  {/* Your Answer */}
                  <div className={`p-4 rounded-lg border-2 ${
                    userCorrect ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'
                  }`}>
                    <div className="flex items-center gap-2 mb-2">
                      {userCorrect ? (
                        <CheckCircle className="h-5 w-5 text-green-600" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-600" />
                      )}
                      <span className="font-semibold text-gray-900">Your Answer</span>
                    </div>
                    <div className="text-2xl font-bold">
                      {userAnswer}
                    </div>
                  </div>

                  {/* AI Answer */}
                  <div className={`p-4 rounded-lg border-2 ${
                    aiResult?.ai_correct ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'
                  }`}>
                    <div className="flex items-center gap-2 mb-2">
                      {aiResult?.ai_correct ? (
                        <CheckCircle className="h-5 w-5 text-green-600" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-600" />
                      )}
                      <span className="font-semibold text-gray-900">AI Answer</span>
                    </div>
                    <div className="text-2xl font-bold">
                      {aiResult?.ai_answer || (loading ? 'Thinking...' : 'N/A')}
                    </div>
                    {!aiResult?.ai_answer && !loading && (
                      <div className="text-xs text-red-600 mt-2">
                        Check browser console for errors
                      </div>
                    )}
                  </div>

                  {/* Correct Answer */}
                  <div className="p-4 rounded-lg border-2 border-gray-300 bg-gray-50">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle className="h-5 w-5 text-gray-600" />
                      <span className="font-semibold text-gray-900">Correct Answer</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900">
                      {currentQuestion.golden_answer}
                    </div>
                  </div>
                </div>

                {/* Agent Status (Clean, No Verbose) */}
                {loading && (
                  <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <div className="flex items-center gap-3">
                      <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                      <div>
                        <div className="text-sm font-medium text-blue-900">
                          AI Agent Analyzing
                        </div>
                        <div className="text-xs text-blue-700">
                          Hybrid search + legal reasoning...
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* AI Retrieval Metrics */}
                <div className="bg-blue-50 rounded-lg p-6 border border-blue-200">
                  <h4 className="font-semibold text-blue-900 mb-4">
                    AI Retrieval Performance
                  </h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm text-blue-700 mb-1">Recall</div>
                      <div className="text-2xl font-bold text-blue-900">
                        {((aiResult?.recall || 0) * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-blue-600">
                        Found {Math.round((aiResult?.recall || 0) * currentQuestion.golden_statute_ids.length)}/
                        {currentQuestion.golden_statute_ids.length} golden statutes
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-blue-700 mb-1">Precision</div>
                      <div className="text-2xl font-bold text-blue-900">
                        {((aiResult?.precision || 0) * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-blue-600">
                        Relevant results in top-5
                      </div>
                    </div>
                  </div>
                </div>

                {/* Golden Statutes */}
                <div className="bg-gray-50 rounded-lg p-6">
                  <h4 className="font-semibold text-gray-900 mb-3">
                    Golden Statutes ({currentQuestion.golden_statute_ids.length})
                  </h4>
                  <div className="space-y-2">
                    {currentQuestion.golden_citations.map((citation, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <CheckCircle className="h-4 w-4 text-green-600" />
                        <span className="text-gray-700">{citation}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Retrieved Statutes */}
                {aiResult && aiResult.retrieved_statutes.length > 0 && (
                  <div className="bg-white rounded-lg p-6 border border-gray-200">
                    <h4 className="font-semibold text-gray-900 mb-3">
                      AI Retrieved Statutes (Top 5)
                    </h4>
                    <div className="space-y-3">
                      {aiResult.retrieved_statutes.slice(0, 5).map((statute, i) => {
                        const isGolden = currentQuestion.golden_statute_ids.includes(statute.statute_idx);
                        return (
                          <div
                            key={i}
                            className={`p-3 rounded-lg border ${
                              isGolden ? 'border-green-500 bg-green-50' : 'border-gray-200 bg-gray-50'
                            }`}
                          >
                            <div className="flex items-start gap-3">
                              {isGolden ? (
                                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                              ) : (
                                <div className="h-5 w-5 mt-0.5" />
                              )}
                              <div className="flex-1">
                                <div className="font-medium text-gray-900">
                                  {statute.citation}
                                </div>
                                <div className="text-xs text-gray-600 mt-1">
                                  Score: {(statute.score * 100).toFixed(1)}%
                                  {isGolden && ' • ✓ Golden Statute'}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Next Question Button */}
                <button
                  onClick={loadNewQuestion}
                  className="w-full py-3 px-6 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 flex items-center justify-center gap-2"
                >
                  <RefreshCw className="h-5 w-5" />
                  Next Question
                </button>
              </div>
            )}
          </div>
        )}

        {/* Loading State */}
        {loading && !currentQuestion && (
          <div className="bg-white rounded-xl shadow-lg p-12 text-center">
            <RefreshCw className="h-12 w-12 animate-spin text-purple-600 mx-auto mb-4" />
            <p className="text-gray-600">Loading question...</p>
          </div>
        )}
        
        {/* Not Ready State */}
        {!loading && !currentQuestion && (
          <div className="bg-yellow-50 rounded-xl shadow-lg p-12 text-center border-2 border-yellow-200">
            <div className="text-6xl mb-4">⏳</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              Quiz Mode Coming Soon
            </h3>
            <p className="text-gray-700 mb-4">
              Questions collection is still being ingested into Qdrant.
            </p>
            <div className="bg-white rounded-lg p-4 max-w-md mx-auto">
              <p className="text-sm text-gray-600 mb-2">
                Current Progress:
              </p>
              <p className="text-lg font-semibold text-blue-600">
                ~7% of statutes ingested
              </p>
              <p className="text-xs text-gray-500 mt-2">
                Check back in a few hours, or monitor progress with:
                <code className="block bg-gray-100 p-2 mt-2 rounded">
                  python check_ingestion_progress.py --watch
                </code>
              </p>
            </div>
            <Link
              href="/"
              className="inline-flex items-center gap-2 mt-6 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Search
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}


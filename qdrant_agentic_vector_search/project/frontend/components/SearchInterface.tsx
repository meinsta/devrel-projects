'use client';

import { useState } from 'react';
import { Search, Loader2, ListChecks } from 'lucide-react';

interface SearchInterfaceProps {
  onSearch: (query: string, mode: 'search' | 'workflow', city?: string) => void;
  isSearching: boolean;
}

export default function SearchInterface({ onSearch, isSearching }: SearchInterfaceProps) {
  const [inputValue, setInputValue] = useState('');
  const [mode, setMode] = useState<'search' | 'workflow'>('search');
  const [city, setCity] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() && !isSearching) {
      onSearch(inputValue.trim(), mode, city || undefined);
    }
  };

  const searchExamples = [
    "Can a landlord evict a tenant without notice?",
    "What are the requirements for security deposit returns?",
    "Is rent control allowed in California cities?",
  ];
  
  const workflowExamples = [
    "Generate 3-day notice procedure for nonpayment",
    "Create habitability complaint workflow",
    "How to respond to unlawful detainer in Los Angeles",
  ];

  const examples = mode === 'search' ? searchExamples : workflowExamples;

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Mode Toggle */}
        <div className="flex gap-2 mb-4">
          <button
            type="button"
            onClick={() => setMode('search')}
            className={`flex items-center gap-2 px-5 py-3 rounded-lg font-medium text-base transition-colors ${
              mode === 'search'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
            disabled={isSearching}
          >
            <Search className="h-5 w-5" />
            Search Statutes
          </button>
          <button
            type="button"
            onClick={() => setMode('workflow')}
            className={`flex items-center gap-2 px-5 py-3 rounded-lg font-medium text-base transition-colors ${
              mode === 'workflow'
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
            disabled={isSearching}
          >
            <ListChecks className="h-5 w-5" />
            Generate Workflow
          </button>
        </div>

        <div className="relative">
          {mode === 'search' ? (
            <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          ) : (
            <ListChecks className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-purple-400" />
          )}
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={
              mode === 'search'
                ? "Ask a question about California housing law..."
                : "Describe the procedure you need (e.g., 'evict for nonpayment')..."
            }
            className="w-full pl-12 pr-32 py-4 text-xl border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            disabled={isSearching}
          />
          <button
            type="submit"
            disabled={isSearching || !inputValue.trim()}
            className={`absolute right-2 top-1/2 transform -translate-y-1/2 px-6 py-2 rounded-md text-base hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium text-white ${
              mode === 'search' ? 'bg-blue-600' : 'bg-purple-600'
            }`}
          >
            {isSearching ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                {mode === 'search' ? 'Searching' : 'Generating'}
              </span>
            ) : mode === 'search' ? 'Search' : 'Generate'
            }
          </button>
        </div>

        {/* City Input for Workflow Mode */}
        {mode === 'workflow' && (
          <div>
            <label className="block text-base font-medium text-gray-700 mb-2">
              City (optional - for local rule checking)
            </label>
            <input
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g., Los Angeles, San Francisco..."
              className="w-full px-4 py-3 text-base border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
              disabled={isSearching}
            />
          </div>
        )}

        {/* Example Questions */}
        <div className="flex flex-wrap gap-2">
          <span className="text-base text-gray-600">
            {mode === 'search' ? 'Try:' : 'Examples:'}
          </span>
          {examples.map((example, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setInputValue(example)}
              className="text-base px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700 transition-colors"
              disabled={isSearching}
            >
              {example}
            </button>
          ))}
        </div>
      </form>
    </div>
  );
}


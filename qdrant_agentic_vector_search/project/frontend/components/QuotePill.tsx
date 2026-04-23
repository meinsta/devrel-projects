'use client';

import { Copy, ExternalLink } from 'lucide-react';
import { useState } from 'react';

interface QuotePillProps {
  statute: string;
  lines?: string;
  quote: string;
  onOpen?: () => void;
}

export default function QuotePill({ statute, lines, quote, onOpen }: QuotePillProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const citation = lines ? `${statute} (L${lines})` : statute;
    const fullQuote = `${citation} — "${quote}"`;
    navigator.clipboard.writeText(fullQuote);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="inline-flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-sm group hover:bg-blue-100 transition-colors">
      <div className="flex items-center gap-2">
        <span className="font-mono text-blue-900 font-medium">
          {statute}
        </span>
        {lines && (
          <span className="text-blue-600 text-xs">
            (L{lines})
          </span>
        )}
      </div>
      
      <span className="text-gray-600">—</span>
      
      <span className="text-gray-700 italic max-w-xs truncate">
        "{quote.substring(0, 50)}..."
      </span>

      <div className="flex items-center gap-1 ml-2">
        <button
          onClick={handleCopy}
          className="p-1 hover:bg-blue-200 rounded transition-colors"
          title="Copy citation"
        >
          <Copy className="h-3 w-3 text-blue-700" />
        </button>
        {copied && (
          <span className="text-xs text-green-600">✓</span>
        )}
        {onOpen && (
          <button
            onClick={onOpen}
            className="p-1 hover:bg-blue-200 rounded transition-colors"
            title="Open full statute"
          >
            <ExternalLink className="h-3 w-3 text-blue-700" />
          </button>
        )}
      </div>
    </div>
  );
}


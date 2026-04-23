'use client';

import { X, Copy, ExternalLink } from 'lucide-react';
import { useState } from 'react';

interface StatuteDrawerProps {
  statute: any;
  isOpen: boolean;
  onClose: () => void;
  highlightLines?: string;
}

export default function StatuteDrawer({ statute, isOpen, onClose, highlightLines }: StatuteDrawerProps) {
  const [copied, setCopied] = useState(false);

  if (!isOpen || !statute) return null;

  const handleCopy = () => {
    const fullCitation = `${statute.citation}\n\n${statute.text}`;
    navigator.clipboard.writeText(fullCitation);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Parse highlighted lines if provided (e.g., "12-19")
  const lines = statute.text.split('\n');

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-full md:w-2/3 lg:w-1/2 bg-white shadow-2xl z-50 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 flex items-start justify-between">
          <div className="flex-1">
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {statute.citation}
            </h3>
            {statute.path && (
              <div className="text-sm text-gray-600">
                {statute.path.split('|').join(' › ')}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-gray-600" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Actions */}
          <div className="flex gap-3 mb-6">
            <button
              onClick={handleCopy}
              className="flex items-center gap-2 px-4 py-2 bg-blue-100 hover:bg-blue-200 text-blue-900 rounded-lg font-medium transition-colors"
            >
              <Copy className="h-4 w-4" />
              {copied ? 'Copied!' : 'Copy Citation'}
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-900 rounded-lg font-medium transition-colors">
              <ExternalLink className="h-4 w-4" />
              View on Official Site
            </button>
          </div>

          {/* Statute Text with Line Numbers */}
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div className="font-mono text-sm leading-7 space-y-1">
              {lines.map((line: string, i: number) => {
                const lineNum = i + 1;
                const isHighlighted = highlightLines && isLineHighlighted(lineNum, highlightLines);
                
                return (
                  <div
                    key={i}
                    className={`flex gap-4 ${
                      isHighlighted ? 'bg-yellow-100 -mx-2 px-2 py-1 rounded' : ''
                    }`}
                  >
                    <span className="text-gray-400 select-none w-8 text-right flex-shrink-0">
                      {lineNum}
                    </span>
                    <span className={isHighlighted ? 'text-gray-900 font-medium' : 'text-gray-700'}>
                      {line}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Metadata */}
          <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h4 className="text-sm font-semibold text-blue-900 mb-2">
              Metadata
            </h4>
            <div className="space-y-1 text-sm text-blue-800">
              <div><span className="font-medium">State:</span> California</div>
              <div><span className="font-medium">Year:</span> 2021</div>
              {statute.statute_idx && (
                <div><span className="font-medium">Statute ID:</span> {statute.statute_idx}</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function isLineHighlighted(lineNum: number, range: string): boolean {
  // Parse range like "12-19" or "15"
  if (range.includes('-')) {
    const [start, end] = range.split('-').map(Number);
    return lineNum >= start && lineNum <= end;
  }
  return lineNum === Number(range);
}


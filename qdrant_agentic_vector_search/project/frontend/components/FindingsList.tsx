'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import QuotePill from './QuotePill';

interface FindingsListProps {
  answer: string;
  statutes?: any[];
}

export default function FindingsList({ answer, statutes }: FindingsListProps) {
  const [showReasoning, setShowReasoning] = useState(false);

  // Parse findings from answer (simplified - would need better parsing)
  const findings = {
    governing_sections: statutes?.slice(0, 3).map(s => s.citation) || [],
    exceptions: 'none', // Would parse from answer
    deadlines: extractDeadlines(answer),
    local_overlay: extractLocalRules(answer),
  };

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl shadow-lg p-6 border border-blue-200">
      <h4 className="text-lg font-semibold text-blue-900 mb-4">
        Key Findings
      </h4>
      
      <div className="space-y-3">
        {/* Governing Sections */}
        {findings.governing_sections.length > 0 && (
          <div>
            <div className="text-base font-medium text-blue-900 mb-2">
              Governing sections:
            </div>
            <div className="flex flex-wrap gap-2">
              {findings.governing_sections.map((cite, i) => (
                <span key={i} className="px-3 py-1.5 bg-white border border-blue-300 rounded text-base font-mono text-blue-900">
                  {cite}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Exceptions */}
        <div className="text-base text-blue-800">
          <span className="font-medium">Exceptions found:</span> {findings.exceptions}
        </div>

        {/* Deadlines */}
        {findings.deadlines && (
          <div className="text-base text-blue-800">
            <span className="font-medium">Deadlines:</span> {findings.deadlines}
          </div>
        )}

        {/* Local Overlay */}
        {findings.local_overlay && (
          <div className="text-base text-blue-800">
            <span className="font-medium">Local overlay:</span> {findings.local_overlay}
          </div>
        )}
      </div>

      {/* Show Full Reasoning Toggle */}
      <button
        onClick={() => setShowReasoning(!showReasoning)}
        className="mt-4 flex items-center gap-2 text-base text-blue-700 hover:text-blue-900 font-medium"
      >
        {showReasoning ? (
          <>
            <ChevronUp className="h-5 w-5" />
            Hide reasoning
          </>
        ) : (
          <>
            <ChevronDown className="h-5 w-5" />
            Show full reasoning
          </>
        )}
      </button>

      {/* Full Reasoning (Collapsed by Default) */}
      {showReasoning && (
        <div className="mt-4 pt-4 border-t border-blue-200">
          <p className="text-base text-gray-700 leading-relaxed">
            {answer}
          </p>
        </div>
      )}
    </div>
  );
}

function extractDeadlines(text: string): string | null {
  // Simple extraction - look for day patterns
  const dayMatch = text.match(/(\d+)\s*days?/i);
  if (dayMatch) {
    return dayMatch[0];
  }
  return null;
}

function extractLocalRules(text: string): string | null {
  // Look for city mentions
  const cities = ['Los Angeles', 'San Francisco', 'Oakland', 'SF', 'LA'];
  for (const city of cities) {
    if (text.includes(city)) {
      return `${city} just-cause may apply`;
    }
  }
  return null;
}


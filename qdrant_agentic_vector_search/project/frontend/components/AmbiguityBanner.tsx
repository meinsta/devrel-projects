'use client';

import { AlertTriangle } from 'lucide-react';

interface AmbiguityBannerProps {
  message: string;
  partial_cite?: string;
}

export default function AmbiguityBanner({ message, partial_cite }: AmbiguityBannerProps) {
  return (
    <div className="bg-amber-50 border-l-4 border-amber-500 rounded-r-lg p-4 mb-6">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-amber-900 mb-1">
            ⚠️ Insufficient Statutory Basis
          </h4>
          <p className="text-sm text-amber-800 mb-2">
            {message}
          </p>
          {partial_cite && (
            <p className="text-xs text-amber-700">
              Partial rule found: {partial_cite}
            </p>
          )}
          <p className="text-xs text-amber-700 mt-2 italic">
            → Escalate to attorney for fact-specific analysis
          </p>
        </div>
      </div>
    </div>
  );
}


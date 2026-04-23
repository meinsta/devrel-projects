'use client';

import { CheckCircle, Circle, Calendar, FileText, AlertCircle } from 'lucide-react';
import { useState } from 'react';
import QuotePill from './QuotePill';

interface WorkflowStep {
  number: number;
  title: string;
  due_date?: string;
  required_docs: string[];
  citations: Array<{
    statute: string;
    lines?: string;
    quote: string;
  }>;
  local_alert?: string;
}

interface WorkflowStepsProps {
  steps: WorkflowStep[];
}

export default function WorkflowSteps({ steps }: WorkflowStepsProps) {
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());

  const toggleStep = (stepNum: number) => {
    setCompletedSteps(prev => {
      const next = new Set(prev);
      if (next.has(stepNum)) {
        next.delete(stepNum);
      } else {
        next.add(stepNum);
      }
      return next;
    });
  };

  return (
    <div className="space-y-4">
      {steps.map((step) => {
        const isCompleted = completedSteps.has(step.number);
        
        return (
          <div
            key={step.number}
            className={`bg-white rounded-lg border-l-4 p-6 shadow-sm transition-all ${
              isCompleted
                ? 'border-l-green-500 bg-green-50/30'
                : 'border-l-slate-200 hover:border-l-indigo-500'
            }`}
          >
            {/* Header */}
            <div className="flex items-start gap-4 mb-4">
              <button
                onClick={() => toggleStep(step.number)}
                className="flex-shrink-0 mt-1"
              >
                {isCompleted ? (
                  <CheckCircle className="h-6 w-6 text-green-600" />
                ) : (
                  <Circle className="h-6 w-6 text-gray-400 hover:text-gray-600" />
                )}
              </button>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <h4 className="text-lg font-semibold text-gray-900">
                    Step {step.number}: {step.title}
                  </h4>
                  
                  {step.due_date && (
                    <div className="flex items-center gap-2 px-3 py-1 bg-orange-100 border border-orange-300 rounded-lg text-sm flex-shrink-0">
                      <Calendar className="h-4 w-4 text-orange-700" />
                      <span className="font-medium text-orange-900">
                        Due: {step.due_date}
                      </span>
                    </div>
                  )}
                </div>

                {/* Local Alert */}
                {step.local_alert && (
                  <div className="mb-3 p-3 bg-yellow-50 border-l-4 border-yellow-500 rounded">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 text-yellow-700 mt-0.5" />
                      <p className="text-sm text-yellow-900">{step.local_alert}</p>
                    </div>
                  </div>
                )}

                {/* Required Docs */}
                {step.required_docs.length > 0 && (
                  <div className="mb-3">
                    <div className="text-xs text-gray-600 mb-2 flex items-center gap-2">
                      <FileText className="h-3 w-3" />
                      Required:
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {step.required_docs.map((doc, i) => (
                        <span
                          key={i}
                          className="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-xs text-gray-700"
                        >
                          {doc}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Citations (Quote Pills) */}
                {step.citations.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-600 mb-2">Citations:</div>
                    <div className="flex flex-wrap gap-2">
                      {step.citations.map((cite, i) => (
                        <QuotePill
                          key={i}
                          statute={cite.statute}
                          lines={cite.lines}
                          quote={cite.quote}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}

      {/* Export Button */}
      <div className="sticky bottom-4 right-4 flex justify-end">
        <button className="px-6 py-3 bg-indigo-600 text-white rounded-lg shadow-lg hover:bg-indigo-700 font-medium flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Export Packet ({steps.length} steps)
        </button>
      </div>
    </div>
  );
}


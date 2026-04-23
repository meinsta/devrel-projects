'use client';

import { CheckCircle, Loader2, Search, Brain, FileSearch, TrendingUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface AgentFlowProps {
  steps: any[];
  isSearching: boolean;
}

export default function AgentFlow({ steps, isSearching }: AgentFlowProps) {
  return (
    <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200 sticky top-4">
      <h3 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Brain className="h-6 w-6 text-blue-600" />
        Agent Process
      </h3>

      <div className="space-y-3">
        <AnimatePresence>
          {steps.map((step, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
            >
              <AgentStep step={step} />
            </motion.div>
          ))}
        </AnimatePresence>

        {isSearching && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg border-l-4 border-blue-500"
          >
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            <span className="text-base text-blue-900">Processing...</span>
          </motion.div>
        )}
      </div>
    </div>
  );
}

function AgentStep({ step }: { step: any }) {
  const getIcon = (type: string) => {
    switch (type) {
      case 'analyze':
        return <Brain className="h-5 w-5 text-purple-600" />;
      case 'search':
        return <Search className="h-5 w-5 text-blue-600" />;
      case 'retrieve':
        return <FileSearch className="h-5 w-5 text-green-600" />;
      case 'rank':
        return <TrendingUp className="h-5 w-5 text-orange-600" />;
      default:
        return <CheckCircle className="h-5 w-5 text-gray-600" />;
    }
  };

  const getColor = (type: string) => {
    switch (type) {
      case 'analyze':
        return 'border-purple-500 bg-purple-50';
      case 'search':
        return 'border-blue-500 bg-blue-50';
      case 'retrieve':
        return 'border-green-500 bg-green-50';
      case 'rank':
        return 'border-orange-500 bg-orange-50';
      default:
        return 'border-gray-500 bg-gray-50';
    }
  };

  return (
    <div className={`p-4 rounded-lg border-l-4 ${getColor(step.action)}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{getIcon(step.action)}</div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-base text-gray-900 mb-1">
            {step.title}
          </div>
          <div className="text-sm text-gray-600">
            {step.description}
          </div>
          {step.metadata && (
            <div className="mt-2 text-sm text-gray-500 flex items-center gap-2">
              {step.metadata.count && (
                <span className="px-2 py-0.5 bg-white rounded-full">
                  {step.metadata.count} results
                </span>
              )}
              {step.metadata.time && (
                <span className="px-2 py-0.5 bg-white rounded-full">
                  {step.metadata.time}ms
                </span>
              )}
            </div>
          )}
        </div>
        <CheckCircle className="h-4 w-4 text-green-600" />
      </div>
    </div>
  );
}


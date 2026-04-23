'use client';

import { useState } from 'react';
import { FileText, ExternalLink, TrendingUp, ChevronDown } from 'lucide-react';
import { motion } from 'framer-motion';
import FindingsList from './FindingsList';
import StatuteDrawer from './StatuteDrawer';
import Breadcrumb from './Breadcrumb';
import FilterBar from './FilterBar';
import AmbiguityBanner from './AmbiguityBanner';

interface ResultsDisplayProps {
  results: any;
  query?: string;
}

export default function ResultsDisplay({ results, query }: ResultsDisplayProps) {
  const [selectedStatute, setSelectedStatute] = useState<any>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const openStatuteDrawer = (statute: any) => {
    setSelectedStatute(statute);
    setDrawerOpen(true);
  };

  // Determine breadcrumb from query (simplified)
  const breadcrumbItems = ['California', 'Housing'];
  if (query?.toLowerCase().includes('evict')) breadcrumbItems.push('Eviction');
  else if (query?.toLowerCase().includes('rent')) breadcrumbItems.push('Rent');
  else if (query?.toLowerCase().includes('deposit')) breadcrumbItems.push('Deposits');

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb items={breadcrumbItems} />

      {/* Ambiguity Banner (conditional) */}
      {results.insufficient_basis && (
        <AmbiguityBanner
          message={results.ambiguity_message || 'The available statutes do not provide a clear answer to this question.'}
          partial_cite={results.partial_cite}
        />
      )}

      {/* Filter Bar */}
      <FilterBar totalResults={results.statutes?.length || 0} />

      {/* Summary */}
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
        <h3 className="text-xl font-semibold text-gray-900 mb-4">
          Research Results
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <StatCard
            label="Statutes Retrieved"
            value={results.statutes?.length || 0}
            icon={<FileText className="h-5 w-5 text-blue-600" />}
            tooltip="Number of relevant statutes found via hybrid search"
          />
          <StatCard
            label="Avg Retrieval Score"
            value={((results.avg_score || 0) * 100).toFixed(0)}
            icon={<TrendingUp className="h-5 w-5 text-slate-600" />}
            tooltip="Average ranking signal from RRF fusion (not legal strength)"
            showAsScore={true}
          />
          <StatCard
            label="Search Time"
            value={`${results.search_time || 0}ms`}
            icon={<FileText className="h-5 w-5 text-indigo-600" />}
            tooltip="Dense + sparse + fusion time"
          />
        </div>
      </div>

      {/* Findings (replaced AI Analysis paragraph) */}
      {results.answer && (
        <FindingsList answer={results.answer} statutes={results.statutes} />
      )}

      {/* Statutes */}
      <div className="space-y-4">
        <h4 className="text-xl font-semibold text-gray-900">
          Relevant Statutes ({results.statutes?.length || 0})
        </h4>
        {results.statutes?.map((statute: any, index: number) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <StatuteCard 
              statute={statute} 
              rank={index + 1}
              onOpenDrawer={() => openStatuteDrawer(statute)}
            />
          </motion.div>
        ))}
      </div>

      {/* Statute Drawer */}
      <StatuteDrawer
        statute={selectedStatute}
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}

function StatCard({ label, value, icon, tooltip, showAsScore }: any) {
  return (
    <div className="flex items-center gap-3 group relative">
      <div className="p-2 bg-gray-50 rounded-lg">
        {icon}
      </div>
      <div>
        <div className="text-3xl font-bold text-gray-900">
          {showAsScore ? (
            <span className="text-slate-700">{value}</span>
          ) : (
            value
          )}
        </div>
        <div className="text-sm text-gray-600">{label}</div>
      </div>
      {tooltip && (
        <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block w-56 p-2 bg-slate-800 text-white text-xs rounded-lg shadow-lg z-10">
          {tooltip}
        </div>
      )}
    </div>
  );
}

function StatuteCard({ statute, rank, onOpenDrawer }: any) {
  const [showFull, setShowFull] = useState(false);
  
  // Format section path
  const sectionPath = statute.path 
    ? statute.path.split('|').filter((p: string) => p.length < 50).join(' › ')
    : null;
  
  return (
    <div className="bg-white rounded-lg shadow-md p-6 border-l-4 border-l-slate-200 hover:border-l-indigo-500 hover:shadow-lg transition-all">
      <div className="flex items-start gap-4">
        <div className="flex-shrink-0 w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center">
          <span className="text-sm font-bold text-indigo-700">#{rank}</span>
        </div>

        <div className="flex-1 min-w-0">
          {/* Citation */}
          <div className="flex items-center gap-2 mb-2">
            <h5 className="font-semibold text-lg text-gray-900">
              {statute.citation}
            </h5>
            <span className="px-2 py-0.5 bg-slate-100 border border-slate-300 text-slate-700 text-sm rounded-full font-mono">
              Score: {statute.score.toFixed(2)}
            </span>
          </div>

          {/* Section Path */}
          {sectionPath && (
            <div className="text-sm text-slate-600 mb-3 font-medium">
              {sectionPath}
            </div>
          )}

          {/* Text with Preview Toggle */}
          <div className="text-base text-gray-700 leading-7">
            {showFull ? (
              statute.text
            ) : (
              statute.text.substring(0, 400) + (statute.text.length > 400 ? '...' : '')
            )}
          </div>

          {/* Preview Lines Chevron */}
          {statute.text.length > 400 && (
            <button
              onClick={() => setShowFull(!showFull)}
              className="mt-2 flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
            >
              <ChevronDown className={`h-4 w-4 transition-transform ${showFull ? 'rotate-180' : ''}`} />
              {showFull ? 'Show less' : 'Read full text'}
            </button>
          )}

          {/* Actions */}
          <div className="mt-4 flex items-center gap-3">
            <button 
              onClick={onOpenDrawer}
              className="text-base text-blue-600 hover:text-blue-700 font-medium"
            >
              Open statute →
            </button>
            <button 
              onClick={() => navigator.clipboard.writeText(statute.citation)}
              className="text-base text-gray-600 hover:text-gray-700"
            >
              Copy citation
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


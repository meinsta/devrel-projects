'use client';

import { Filter, X } from 'lucide-react';
import { useState } from 'react';

interface FilterBarProps {
  totalResults: number;
  onFilterChange?: (filters: any) => void;
}

export default function FilterBar({ totalResults, onFilterChange }: FilterBarProps) {
  const [activeFilters, setActiveFilters] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  const filters = {
    'Code Section': ['Civil Code', 'Code of Civ. Proc.', 'Business & Prof Code'],
    'Topic': ['Eviction', 'Rent', 'Deposits', 'Habitability', 'Retaliation'],
  };

  const toggleFilter = (filter: string) => {
    setActiveFilters(prev => 
      prev.includes(filter)
        ? prev.filter(f => f !== filter)
        : [...prev, filter]
    );
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-base font-medium transition-colors"
          >
            <Filter className="h-5 w-5" />
            Filters
            {activeFilters.length > 0 && (
              <span className="px-2 py-0.5 bg-indigo-600 text-white rounded-full text-sm">
                {activeFilters.length}
              </span>
            )}
          </button>
          
          <span className="text-base text-gray-600 font-medium">
            {totalResults} results
          </span>
        </div>

        {activeFilters.length > 0 && (
          <button
            onClick={() => setActiveFilters([])}
            className="text-base text-gray-600 hover:text-gray-900 font-medium"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Active Filters */}
      {activeFilters.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {activeFilters.map(filter => (
            <div
              key={filter}
              className="flex items-center gap-2 px-3 py-1.5 bg-indigo-100 text-indigo-900 rounded-full text-base"
            >
              {filter}
              <button
                onClick={() => toggleFilter(filter)}
                className="hover:bg-indigo-200 rounded-full p-0.5"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Filter Options */}
      {showFilters && (
        <div className="pt-3 border-t border-gray-200 space-y-3">
          {Object.entries(filters).map(([category, options]) => (
            <div key={category}>
              <div className="text-sm font-medium text-gray-700 mb-2">
                {category}
              </div>
              <div className="flex flex-wrap gap-2">
                {options.map(option => (
                  <button
                    key={option}
                    onClick={() => toggleFilter(option)}
                    className={`px-4 py-2 rounded-full text-base transition-colors ${
                      activeFilters.includes(option)
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


'use client';

import { ChevronRight } from 'lucide-react';

interface BreadcrumbProps {
  items: string[];
}

export default function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-600 mb-6">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          {i > 0 && <ChevronRight className="h-4 w-4 text-gray-400" />}
          <span className={i === items.length - 1 ? 'font-medium text-gray-900' : ''}>
            {item}
          </span>
        </div>
      ))}
    </div>
  );
}


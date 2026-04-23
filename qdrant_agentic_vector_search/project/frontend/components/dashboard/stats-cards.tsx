'use client';

import { FileText, TrendingUp, Clock, CheckCircle } from 'lucide-react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface StatsCardsProps {
  stats: {
    statutesRetrieved?: number;
    avgScore?: number;
    searchTime?: number;
    accuracy?: number;
  };
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: 'Statutes Retrieved',
      value: stats.statutesRetrieved || 0,
      icon: FileText,
      description: 'Documents found',
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'Avg Retrieval Score',
      value: `${((stats.avgScore || 0) * 100).toFixed(0)}%`,
      icon: TrendingUp,
      description: 'Ranking signal',
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      title: 'Search Time',
      value: `${stats.searchTime || 0}ms`,
      icon: Clock,
      description: 'Total query time',
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      title: 'Accuracy',
      value: `${stats.accuracy || 0}%`,
      icon: CheckCircle,
      description: 'Relevance score',
      color: 'text-amber-600',
      bgColor: 'bg-amber-50',
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {card.title}
            </CardTitle>
            <div className={`p-2 rounded-lg ${card.bgColor}`}>
              <card.icon className={`h-4 w-4 ${card.color}`} />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{card.value}</div>
            <p className="text-xs text-muted-foreground">
              {card.description}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}






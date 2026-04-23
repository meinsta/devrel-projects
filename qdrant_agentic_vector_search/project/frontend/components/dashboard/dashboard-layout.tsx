'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { Scale, Search, Trophy, Settings, BarChart3, BookOpen, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface DashboardLayoutProps {
  children: ReactNode;
  stats?: {
    totalSearches?: number;
    avgAccuracy?: string;
    statutesIndexed?: number;
    responseTime?: string;
  };
}

export default function DashboardLayout({ children, stats }: DashboardLayoutProps) {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="hidden w-64 border-r bg-muted/40 lg:block">
        <div className="flex h-full flex-col gap-2">
          {/* Logo/Header */}
          <div className="flex h-[60px] items-center border-b px-6">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <Scale className="h-6 w-6 text-primary" />
              <span className="text-lg">Legal Research</span>
            </Link>
          </div>

          {/* Navigation */}
          <div className="flex-1 overflow-auto py-2">
            <nav className="grid gap-1 px-4">
              <Link href="/">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-base"
                >
                  <Search className="h-5 w-5" />
                  Search
                </Button>
              </Link>
              <Link href="/quiz">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-base"
                >
                  <Trophy className="h-5 w-5" />
                  Quiz Mode
                </Button>
              </Link>
              <Link href="/analytics">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-base"
                >
                  <BarChart3 className="h-5 w-5" />
                  Analytics
                  <Badge variant="secondary" className="ml-auto">
                    New
                  </Badge>
                </Button>
              </Link>
              <Link href="/statutes">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-base"
                >
                  <BookOpen className="h-5 w-5" />
                  Browse Statutes
                </Button>
              </Link>
            </nav>

            {/* Stats Card in Sidebar */}
            {stats && (
              <div className="mx-4 mt-6">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">System Stats</CardTitle>
                    <CardDescription className="text-xs">
                      Real-time metrics
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="text-sm space-y-2">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Searches</span>
                      <span className="font-semibold">{stats.totalSearches?.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Accuracy</span>
                      <span className="font-semibold">{stats.avgAccuracy}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Statutes</span>
                      <span className="font-semibold">{stats.statutesIndexed?.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Avg Time</span>
                      <span className="font-semibold">{stats.responseTime}</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="mt-auto border-t p-4">
            <Button variant="ghost" className="w-full justify-start gap-2 text-base">
              <Settings className="h-5 w-5" />
              Settings
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col">
        {/* Top Bar */}
        <header className="flex h-[60px] items-center gap-4 border-b bg-background px-6">
          <Button variant="ghost" size="icon" className="lg:hidden">
            <Menu className="h-5 w-5" />
          </Button>
          <div className="flex-1">
            <h1 className="text-xl font-semibold">California Housing Law</h1>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="hidden sm:inline-flex">
              GPT-4o-mini
            </Badge>
            <Badge variant="outline" className="hidden sm:inline-flex">
              bge-small
            </Badge>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}






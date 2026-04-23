# shadcn/ui Dashboard Templates Guide 🎨

## Official shadcn Examples

shadcn/ui provides several production-ready examples at: https://ui.shadcn.com/examples

### Available Templates:

1. **Dashboard** (https://ui.shadcn.com/examples/dashboard)
   - Full admin layout with sidebar
   - Cards, charts, and data tables
   - Perfect for analytics

2. **Cards** (https://ui.shadcn.com/examples/cards)
   - Various card patterns
   - Notification cards
   - Stats displays

3. **Tasks** (https://ui.shadcn.com/examples/tasks)
   - Kanban-style layout
   - Drag and drop
   - Filtering and sorting

4. **Forms** (https://ui.shadcn.com/examples/forms)
   - Complex form layouts
   - Validation patterns
   - Multi-step forms

5. **Mail** (https://ui.shadcn.com/examples/mail)
   - Split-pane interface
   - List + detail view
   - Great for document browsing

6. **Music** (https://ui.shadcn.com/examples/music)
   - Media player UI
   - Sidebar + main content
   - Beautiful gradients

## What I've Created For You

### 1. Dashboard Layout Component

Located at: `components/dashboard/dashboard-layout.tsx`

**Features:**
- Responsive sidebar navigation
- Stats card in sidebar
- Top bar with badges
- Mobile-friendly hamburger menu
- Professional spacing and layout

**Usage:**
```tsx
import DashboardLayout from '@/components/dashboard/dashboard-layout';

export default function Page() {
  return (
    <DashboardLayout
      stats={{
        totalSearches: 1234,
        avgAccuracy: '94.2%',
        statutesIndexed: 155974,
        responseTime: '245ms',
      }}
    >
      <YourPageContent />
    </DashboardLayout>
  );
}
```

### 2. Stats Cards Component

Located at: `components/dashboard/stats-cards.tsx`

**Features:**
- Grid of metric cards
- Icons with colored backgrounds
- Responsive layout
- Hover effects

**Usage:**
```tsx
import StatsCards from '@/components/dashboard/stats-cards';

<StatsCards
  stats={{
    statutesRetrieved: 20,
    avgScore: 0.87,
    searchTime: 245,
    accuracy: 94,
  }}
/>
```

## Adding More Dashboard Components

### Install Common Dashboard Components:

```bash
cd project/frontend

# Navigation & Layout
npx shadcn@latest add navigation-menu
npx shadcn@latest add sheet  # For mobile menu
npx shadcn@latest add tabs

# Data Display
npx shadcn@latest add table
npx shadcn@latest add data-table  # Advanced table with sorting/filtering
npx shadcn@latest add chart  # If using recharts

# Forms & Inputs
npx shadcn@latest add form
npx shadcn@latest add input
npx shadcn@latest add select
npx shadcn@latest add textarea
npx shadcn@latest add checkbox
npx shadcn@latest add radio-group

# Feedback
npx shadcn@latest add alert
npx shadcn@latest add toast
npx shadcn@latest add progress
npx shadcn@latest add skeleton  # Loading states

# Overlays
npx shadcn@latest add dialog
npx shadcn@latest add alert-dialog
npx shadcn@latest add popover
npx shadcn@latest add tooltip

# Other Useful
npx shadcn@latest add avatar
npx shadcn@latest add breadcrumb
npx shadcn@latest add calendar
npx shadcn@latest add command  # Command palette
npx shadcn@latest add scroll-area
```

## Example: Integrate Dashboard Layout

Replace your current `app/page.tsx`:

```tsx
import DashboardLayout from '@/components/dashboard/dashboard-layout';
import StatsCards from '@/components/dashboard/stats-cards';
import SearchInterface from '@/components/SearchInterface';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function Home() {
  return (
    <DashboardLayout
      stats={{
        totalSearches: 1234,
        avgAccuracy: '94.2%',
        statutesIndexed: 155974,
        responseTime: '245ms',
      }}
    >
      <div className="space-y-6">
        {/* Hero Section */}
        <div>
          <h2 className="text-3xl font-bold tracking-tight">
            Search California Housing Law
          </h2>
          <p className="text-muted-foreground text-lg mt-2">
            AI-powered search across 155,974+ housing statutes
          </p>
        </div>

        {/* Stats */}
        <StatsCards
          stats={{
            statutesRetrieved: 20,
            avgScore: 0.87,
            searchTime: 245,
            accuracy: 94,
          }}
        />

        {/* Search Interface */}
        <Card>
          <CardHeader>
            <CardTitle>Search Statutes</CardTitle>
            <CardDescription>
              Ask a question about California housing law
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SearchInterface onSearch={handleSearch} isSearching={false} />
          </CardContent>
        </Card>

        {/* Recent Searches or other content */}
      </div>
    </DashboardLayout>
  );
}
```

## View Official Examples

You can explore and copy code from:

1. **Browse Online**: https://ui.shadcn.com/examples
2. **View Source**: All examples are on GitHub
3. **Copy Components**: Each example page has a "View Code" button

## Pro Tips

1. **Start with an Example**: Copy a full example layout that matches your needs
2. **Customize Colors**: Modify CSS variables in `globals.css`
3. **Mix Components**: Combine elements from different examples
4. **Use Blocks**: shadcn also has "Blocks" - larger pre-built sections
5. **Check Blocks**: https://ui.shadcn.com/blocks for ready-to-use sections

## Resources

- 📚 [Examples](https://ui.shadcn.com/examples)
- 🧱 [Blocks](https://ui.shadcn.com/blocks)
- 📖 [Components](https://ui.shadcn.com/docs/components)
- 🎨 [Themes](https://ui.shadcn.com/themes)
- 💡 [GitHub](https://github.com/shadcn-ui/ui)






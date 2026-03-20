import { useEffect, useMemo, useState } from 'react';
import {
  FinancialCard,
  FinancialCardContent,
  FinancialCardDescription,
  FinancialCardHeader,
  FinancialCardTitle,
} from '@/components/ui/financial-card';
import { Button } from '@/components/ui/button';
import {
  ArrowDownRight,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  TrendingDown,
  TrendingUp,
  Wallet,
  PiggyBank,
  Lightbulb,
  Calendar,
  BarChart3,
} from 'lucide-react';
import { getWeeklyDigest, type WeeklyDigest } from '@/api/digest';
import { formatMoney } from '@/lib/currency';

function currency(n: number) {
  return formatMoney(Number(n || 0));
}

function toWeekKey(d: Date): string {
  const iso = getISOWeek(d);
  return `${iso.year}-W${String(iso.week).padStart(2, '0')}`;
}

function getISOWeek(d: Date): { year: number; week: number } {
  const date = new Date(d.getTime());
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7));
  const yearStart = new Date(date.getFullYear(), 0, 4);
  const weekNumber =
    Math.round(((date.getTime() - yearStart.getTime()) / 86400000 + ((yearStart.getDay() + 6) % 7) + 1) / 7);
  return { year: date.getFullYear(), week: weekNumber };
}

export function WeeklyDigestPage() {
  const [data, setData] = useState<WeeklyDigest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentWeekOffset, setCurrentWeekOffset] = useState(0);

  const weekKey = useMemo(() => {
    const now = new Date();
    now.setDate(now.getDate() - currentWeekOffset * 7);
    return toWeekKey(now);
  }, [currentWeekOffset]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await getWeeklyDigest(weekKey);
        setData(res);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load digest');
      } finally {
        setLoading(false);
      }
    })();
  }, [weekKey]);

  const summaryCards = useMemo(() => {
    if (!data) return [];
    return [
      {
        title: 'Total Income',
        amount: currency(data.total_income),
        icon: TrendingUp,
        trend: 'up' as const,
        pct: data.week_over_week.income_change_pct,
      },
      {
        title: 'Total Expenses',
        amount: currency(data.total_expenses),
        icon: TrendingDown,
        trend: 'down' as const,
        pct: data.week_over_week.expense_change_pct,
      },
      {
        title: 'Net Savings',
        amount: currency(data.net_savings),
        icon: Wallet,
        trend: data.net_savings >= 0 ? ('up' as const) : ('down' as const),
      },
      {
        title: 'Savings Rate',
        amount: `${data.savings_rate}%`,
        icon: PiggyBank,
        trend: data.savings_rate >= 20 ? ('up' as const) : ('down' as const),
      },
    ];
  }, [data]);

  return (
    <div className="page-wrap">
      <div className="page-header">
        <div className="relative flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="page-title">Weekly Digest</h1>
            <p className="page-subtitle">
              {data
                ? `${data.period.start} → ${data.period.end}`
                : 'Loading…'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentWeekOffset((o) => o + 1)}
            >
              <ChevronLeft className="w-4 h-4" />
              Prev
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentWeekOffset(0)}
            >
              <Calendar className="w-4 h-4" />
              This Week
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={currentWeekOffset <= 0}
              onClick={() => setCurrentWeekOffset((o) => o - 1)}
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {error && <div className="error mb-6">{error}</div>}

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        {summaryCards.map((card, i) => (
          <FinancialCard
            key={i}
            variant="financial"
            className="group card-interactive fade-in-up"
          >
            <FinancialCardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <FinancialCardTitle className="text-sm font-medium text-muted-foreground">
                  {card.title}
                </FinancialCardTitle>
                <card.icon className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
              </div>
            </FinancialCardHeader>
            <FinancialCardContent>
              <div className="metric-value text-foreground mb-1">
                {loading ? '…' : card.amount}
              </div>
              {card.pct !== null && card.pct !== undefined && (
                <div className="flex items-center text-sm">
                  {card.pct > 0 ? (
                    <ArrowUpRight className="w-4 h-4 text-success mr-1" />
                  ) : card.pct < 0 ? (
                    <ArrowDownRight className="w-4 h-4 text-destructive mr-1" />
                  ) : null}
                  <span
                    className={`font-medium mr-2 ${
                      card.pct > 0
                        ? 'text-success'
                        : card.pct < 0
                        ? 'text-destructive'
                        : 'text-muted-foreground'
                    }`}
                  >
                    {card.pct > 0 ? '+' : ''}
                    {card.pct}%
                  </span>
                  <span className="text-muted-foreground">vs last week</span>
                </div>
              )}
            </FinancialCardContent>
          </FinancialCard>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Category breakdown */}
        <div className="lg:col-span-2">
          <FinancialCard variant="financial" className="fade-in-up">
            <FinancialCardHeader>
              <div className="flex items-center justify-between">
                <FinancialCardTitle className="section-title">
                  Category Breakdown
                </FinancialCardTitle>
                <BarChart3 className="w-5 h-5 text-muted-foreground" />
              </div>
              <FinancialCardDescription>
                Top spending categories for week {data?.week}
              </FinancialCardDescription>
            </FinancialCardHeader>
            <FinancialCardContent>
              {loading ? (
                <div className="text-sm text-muted-foreground">Loading…</div>
              ) : !data?.top_categories?.length ? (
                <div className="text-sm text-muted-foreground">
                  No expense data for this week.
                </div>
              ) : (
                <div className="space-y-4">
                  {data.top_categories.map((cat) => (
                    <div key={cat.name} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-foreground font-medium">
                          {cat.name}
                        </span>
                        <span className="text-muted-foreground">
                          {currency(cat.amount)} ({cat.percentage.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="chart-track h-2.5">
                        <div
                          className="chart-fill-primary h-2.5"
                          style={{
                            width: `${Math.max(2, Math.min(100, cat.percentage))}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </FinancialCardContent>
          </FinancialCard>
        </div>

        {/* Right column: Quick stats + Insights */}
        <div className="space-y-6">
          <FinancialCard variant="financial" className="fade-in-up">
            <FinancialCardHeader>
              <FinancialCardTitle className="section-title">
                Quick Stats
              </FinancialCardTitle>
            </FinancialCardHeader>
            <FinancialCardContent>
              <div className="space-y-4">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Daily Average Spend</span>
                  <span className="font-semibold text-foreground">
                    {loading ? '…' : data ? currency(data.daily_average) : '-'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Recurring Total</span>
                  <span className="font-semibold text-foreground">
                    {loading ? '…' : data ? currency(data.recurring_total) : '-'}
                  </span>
                </div>
              </div>
            </FinancialCardContent>
          </FinancialCard>

          <FinancialCard variant="financial" className="fade-in-up">
            <FinancialCardHeader>
              <div className="flex items-center justify-between">
                <FinancialCardTitle className="section-title">
                  Insights
                </FinancialCardTitle>
                <Lightbulb className="w-5 h-5 text-warning" />
              </div>
              <FinancialCardDescription>AI-generated observations</FinancialCardDescription>
            </FinancialCardHeader>
            <FinancialCardContent>
              {loading ? (
                <div className="text-sm text-muted-foreground">Analyzing…</div>
              ) : !data?.insights?.length ? (
                <div className="text-sm text-muted-foreground">
                  No insights for this week.
                </div>
              ) : (
                <ul className="space-y-3">
                  {data.insights.map((insight, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-foreground"
                    >
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                      {insight}
                    </li>
                  ))}
                </ul>
              )}
            </FinancialCardContent>
          </FinancialCard>
        </div>
      </div>
    </div>
  );
}

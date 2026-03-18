import { useMemo } from 'react';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import type { AccountOverview as OverviewType } from '@/api/accounts';
import { formatMoney } from '@/lib/currency';

type Props = {
  data: OverviewType | null;
  loading?: boolean;
};

const TYPE_COLORS: Record<string, string> = {
  bank: '#3b82f6',
  credit_card: '#ef4444',
  investment: '#10b981',
  cash: '#f59e0b',
  wallet: '#8b5cf6',
};

const TYPE_LABELS: Record<string, string> = {
  bank: 'Bank',
  credit_card: 'Credit Card',
  investment: 'Investment',
  cash: 'Cash',
  wallet: 'Wallet',
};

export function AccountOverview({ data, loading }: Props) {
  const cards = useMemo(() => {
    if (!data) return [];
    return [
      {
        title: 'Total Assets',
        value: formatMoney(data.total_assets),
        icon: Wallet,
        color: 'text-blue-500',
        bg: 'bg-blue-500/10',
      },
      {
        title: 'Total Income',
        value: formatMoney(data.total_income),
        icon: TrendingUp,
        color: 'text-emerald-500',
        bg: 'bg-emerald-500/10',
      },
      {
        title: 'Total Expenses',
        value: formatMoney(data.total_expenses),
        icon: TrendingDown,
        color: 'text-red-500',
        bg: 'bg-red-500/10',
      },
      {
        title: 'Net Worth',
        value: formatMoney(data.net_worth),
        icon: BarChart3,
        color: data.net_worth >= 0 ? 'text-emerald-500' : 'text-red-500',
        bg: data.net_worth >= 0 ? 'bg-emerald-500/10' : 'bg-red-500/10',
      },
    ];
  }, [data]);

  const distribution = useMemo(() => {
    if (!data) return [];
    const total = Object.values(data.distribution).reduce((s, v) => s + v, 0);
    if (total === 0) return [];
    return Object.entries(data.distribution)
      .map(([type, value]) => ({
        type,
        label: TYPE_LABELS[type] || type,
        value,
        pct: ((value / total) * 100).toFixed(1),
        color: TYPE_COLORS[type] || '#6b7280',
      }))
      .sort((a, b) => b.value - a.value);
  }, [data]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-28 animate-pulse rounded-xl border bg-muted/50"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.title}
              className="rounded-xl border bg-card p-4 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">{card.title}</p>
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg ${card.bg}`}
                >
                  <Icon className={`h-4 w-4 ${card.color}`} />
                </div>
              </div>
              <p className="mt-2 text-2xl font-bold">{card.value}</p>
            </div>
          );
        })}
      </div>

      {/* Distribution Chart (CSS-only donut) */}
      {distribution.length > 0 && (
        <div className="rounded-xl border bg-card p-4 shadow-sm">
          <h3 className="mb-4 text-sm font-medium text-muted-foreground">
            Asset Distribution
          </h3>
          <div className="flex flex-col items-center gap-6 sm:flex-row">
            {/* CSS Donut Chart */}
            <div className="relative flex-shrink-0">
              <svg width="140" height="140" viewBox="0 0 140 140">
                {(() => {
                  let offset = 0;
                  return distribution.map((seg) => {
                    const circumference = 2 * Math.PI * 56;
                    const dash = (circumference * Number(seg.pct)) / 100;
                    const gap = circumference - dash;
                    const el = (
                      <circle
                        key={seg.type}
                        cx="70"
                        cy="70"
                        r="56"
                        fill="none"
                        stroke={seg.color}
                        strokeWidth="12"
                        strokeDasharray={`${dash} ${gap}`}
                        strokeDashoffset={-offset}
                        strokeLinecap="butt"
                      />
                    );
                    offset += dash;
                    return el;
                  });
                })()}
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-xs text-muted-foreground">Accounts</span>
                <span className="text-lg font-bold">{data?.account_count ?? 0}</span>
              </div>
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-3">
              {distribution.map((seg) => (
                <div
                  key={seg.type}
                  className="flex items-center gap-2 rounded-lg border px-3 py-2"
                >
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: seg.color }}
                  />
                  <div>
                    <p className="text-xs text-muted-foreground">{seg.label}</p>
                    <p className="text-sm font-medium">
                      {seg.pct}% · {formatMoney(seg.value)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

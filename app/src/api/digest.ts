import { api } from './client';

export type WeekPeriod = {
  start: string;
  end: string;
};

export type TopCategory = {
  name: string;
  amount: number;
  percentage: number;
};

export type WeekOverWeek = {
  expense_change_pct: number | null;
  income_change_pct: number | null;
};

export type WeeklyDigest = {
  week: string;
  period: WeekPeriod;
  total_income: number;
  total_expenses: number;
  net_savings: number;
  savings_rate: number;
  top_categories: TopCategory[];
  daily_average: number;
  recurring_total: number;
  week_over_week: WeekOverWeek;
  insights: string[];
};

export type TrendWeek = {
  week: string;
  period: WeekPeriod;
  total_income: number;
  total_expenses: number;
  net_savings: number;
  savings_rate: number;
};

export async function getWeeklyDigest(week?: string): Promise<WeeklyDigest> {
  const query = week ? `?week=${encodeURIComponent(week)}` : '';
  return api<WeeklyDigest>(`/digest/weekly${query}`);
}

export async function getTrends(weeks = 4): Promise<TrendWeek[]> {
  return api<TrendWeek[]>(`/digest/trends?weeks=${weeks}`);
}

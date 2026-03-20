import { api } from './client';

export type SavingsGoal = {
  id: number;
  name: string;
  target_amount: number;
  current_amount: number;
  currency: string;
  category?: string;
  target_date?: string;
  milestones: string[];
  progress_percent: number;
  remaining: number;
  days_left?: number;
  created_at?: string;
  recent_contributions?: GoalContribution[];
  milestone_achieved?: string[];
};

export type GoalContribution = {
  id: number;
  amount: number;
  note?: string;
  created_at: string;
};

export type GoalCreate = {
  name: string;
  target_amount: number;
  category?: string;
  target_date?: string;
};

export type GoalUpdate = Partial<GoalCreate>;

export type GoalsSummary = {
  total_goals: number;
  completed: number;
  active: number;
  total_target: number;
  total_saved: number;
  overall_progress: number;
};

export async function listGoals(): Promise<SavingsGoal[]> {
  return api<SavingsGoal[]>('/savings-goals');
}

export async function getGoalSummary(): Promise<GoalsSummary> {
  return api<GoalsSummary>('/savings-goals/summary');
}

export async function getGoal(id: number): Promise<SavingsGoal> {
  return api<SavingsGoal>(`/savings-goals/${id}`);
}

export async function createGoal(data: GoalCreate): Promise<SavingsGoal> {
  return api<SavingsGoal>('/savings-goals', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateGoal(id: number, data: GoalUpdate): Promise<SavingsGoal> {
  return api<SavingsGoal>(`/savings-goals/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function deleteGoal(id: number): Promise<void> {
  return api(`/savings-goals/${id}`, { method: 'DELETE' });
}

export async function contributeToGoal(id: number, amount: number, note?: string): Promise<SavingsGoal> {
  return api<SavingsGoal>(`/savings-goals/${id}/contribute`, {
    method: 'POST',
    body: JSON.stringify({ amount, note }),
  });
}

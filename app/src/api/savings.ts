import { api } from './client';

export type Milestone = {
  threshold: number;
  reached: boolean;
  current_percent: number;
};

export type SavingsGoal = {
  id: number;
  user_id: number;
  name: string;
  target_amount: number;
  current_amount: number;
  target_date: string | null;
  icon: string;
  color: string;
  milestones: Milestone[];
  days_left: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type SavingsGoalCreate = {
  name: string;
  target_amount: number;
  target_date?: string | null;
  icon?: string;
  color?: string;
};

export type SavingsGoalUpdate = Partial<SavingsGoalCreate>;

export async function listSavingsGoals(): Promise<SavingsGoal[]> {
  return api<SavingsGoal[]>('/savings/goals');
}

export async function createSavingsGoal(payload: SavingsGoalCreate): Promise<SavingsGoal> {
  return api<SavingsGoal>('/savings/goals', { method: 'POST', body: payload });
}

export async function getSavingsGoal(id: number): Promise<SavingsGoal> {
  return api<SavingsGoal>(`/savings/goals/${id}`);
}

export async function updateSavingsGoal(id: number, payload: SavingsGoalUpdate): Promise<SavingsGoal> {
  return api<SavingsGoal>(`/savings/goals/${id}`, { method: 'PUT', body: payload });
}

export async function deleteSavingsGoal(id: number): Promise<{ message: string }> {
  return api<{ message: string }>(`/savings/goals/${id}`, { method: 'DELETE' });
}

export async function contributeToGoal(id: number, amount: number, note?: string): Promise<SavingsGoal> {
  return api<SavingsGoal>(`/savings/goals/${id}/contribute`, {
    method: 'POST',
    body: { amount, note },
  });
}

export async function withdrawFromGoal(id: number, amount: number, note?: string): Promise<SavingsGoal> {
  return api<SavingsGoal>(`/savings/goals/${id}/withdraw`, {
    method: 'POST',
    body: { amount, note },
  });
}

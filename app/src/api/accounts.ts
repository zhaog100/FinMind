import { api } from './client';

export type AccountType = 'bank' | 'credit_card' | 'investment' | 'cash' | 'wallet';

export type Account = {
  id: number;
  name: string;
  type: AccountType;
  balance: number;
  currency: string;
  icon: string | null;
  color: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type AccountCreate = {
  name: string;
  type?: AccountType;
  balance?: number;
  currency?: string;
  icon?: string | null;
  color?: string | null;
};

export type AccountUpdate = Partial<AccountCreate>;

export type AccountOverview = {
  total_assets: number;
  total_income: number;
  total_expenses: number;
  net_worth: number;
  account_count: number;
  distribution: Record<string, number>;
  accounts: Account[];
};

export async function listAccounts(): Promise<Account[]> {
  return api<Account[]>('/accounts');
}

export async function createAccount(payload: AccountCreate): Promise<Account> {
  return api<Account>('/accounts', { method: 'POST', body: payload });
}

export async function updateAccount(id: number, payload: AccountUpdate): Promise<Account> {
  return api<Account>(`/accounts/${id}`, { method: 'PUT', body: payload });
}

export async function deleteAccount(id: number): Promise<{ message: string }> {
  return api<{ message: string }>(`/accounts/${id}`, { method: 'DELETE' });
}

export async function getAccountOverview(): Promise<AccountOverview> {
  return api<AccountOverview>('/accounts/overview');
}

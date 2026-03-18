import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { Savings } from '@/pages/Savings';
import * as savingsApi from '@/api/savings';

// Mock the savings API
vi.mock('@/api/savings', () => ({
  listSavingsGoals: vi.fn(),
  createSavingsGoal: vi.fn(),
  deleteSavingsGoal: vi.fn(),
  contributeToGoal: vi.fn(),
  withdrawFromGoal: vi.fn(),
}));

// Mock useToast
vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

// Mock formatMoney
vi.mock('@/lib/currency', () => ({
  formatMoney: (n: number) => `$${n.toFixed(2)}`,
}));

function renderSavings() {
  return render(
    <BrowserRouter>
      <Savings />
    </BrowserRouter>,
  );
}

describe('Savings page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (savingsApi.listSavingsGoals as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  it('renders the page header', async () => {
    renderSavings();
    expect(screen.getByText('Savings Goals')).toBeDefined();
    expect(screen.getByText(/Track your savings/)).toBeDefined();
  });

  it('shows loading state initially', () => {
    (savingsApi.listSavingsGoals as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    renderSavings();
    expect(screen.getByText('Loading…')).toBeDefined();
  });

  it('shows empty state when no goals', async () => {
    renderSavings();
    expect(await screen.findByText('No savings goals yet')).toBeDefined();
  });

  it('renders goals when loaded', async () => {
    const mockGoals = [
      {
        id: 1,
        user_id: 1,
        name: 'Emergency Fund',
        target_amount: 10000,
        current_amount: 5000,
        target_date: '2026-12-31',
        icon: '🎯',
        color: '#6366f1',
        milestones: [
          { threshold: 25, reached: true, current_percent: 50 },
          { threshold: 50, reached: true, current_percent: 50 },
          { threshold: 75, reached: false, current_percent: 50 },
          { threshold: 100, reached: false, current_percent: 50 },
        ],
        days_left: 288,
        created_at: '2026-01-01T00:00:00',
        updated_at: '2026-01-01T00:00:00',
      },
    ];
    (savingsApi.listSavingsGoals as ReturnType<typeof vi.fn>).mockResolvedValue(mockGoals);
    renderSavings();
    expect(await screen.findByText('Emergency Fund')).toBeDefined();
    expect(screen.getByText('$5000.00')).toBeDefined();
    expect(screen.getByText('$10000.00')).toBeDefined();
  });

  it('opens create dialog on button click', async () => {
    const user = userEvent.setup();
    renderSavings();
    await screen.findByText('No savings goals yet');
    const buttons = screen.getAllByText('New Goal');
    await user.click(buttons[0]);
    expect(screen.getByText('Create Savings Goal')).toBeDefined();
  });
});

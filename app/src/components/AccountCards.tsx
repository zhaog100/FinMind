import {
  FinancialCard,
  FinancialCardContent,
  FinancialCardHeader,
  FinancialCardTitle,
  FinancialCardDescription,
} from '@/components/ui/financial-card';
import { ArrowDownRight, ArrowUpRight, Wallet } from 'lucide-react';
import { formatMoney } from '@/lib/currency';
import type { AccountOverview } from '@/api/dashboard';

function currency(n: number, code?: string) {
  return formatMoney(Number(n || 0), code);
}

type Props = {
  accounts: AccountOverview[];
  loading?: boolean;
};

export function AccountCards({ accounts, loading }: Props) {
  if (accounts.length === 0 && !loading) return null;

  return (
    <FinancialCard variant="financial" className="fade-in-up">
      <FinancialCardHeader>
        <div className="flex items-center justify-between">
          <FinancialCardTitle className="section-title">Accounts Overview</FinancialCardTitle>
          <Wallet className="w-5 h-5 text-muted-foreground" />
        </div>
        <FinancialCardDescription>Breakdown by currency</FinancialCardDescription>
      </FinancialCardHeader>
      <FinancialCardContent>
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading accounts…</div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {accounts.map((acct) => (
              <div key={acct.currency} className="rounded-lg border p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-foreground">{acct.currency}</span>
                  <span className="text-xs text-muted-foreground">{acct.transaction_count} txn(s)</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Income</span>
                    <div className="font-medium text-success flex items-center">
                      <ArrowUpRight className="w-3 h-3 mr-1" />
                      {currency(acct.total_income, acct.currency)}
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Expenses</span>
                    <div className="font-medium text-destructive flex items-center">
                      <ArrowDownRight className="w-3 h-3 mr-1" />
                      {currency(acct.total_expenses, acct.currency)}
                    </div>
                  </div>
                </div>
                <div className="border-t pt-2">
                  <span className="text-xs text-muted-foreground">Net Savings</span>
                  <div className={`font-semibold ${acct.net_savings >= 0 ? 'text-success' : 'text-destructive'}`}>
                    {currency(acct.net_savings, acct.currency)}
                  </div>
                </div>
                {acct.top_categories.length > 0 && (
                  <div className="space-y-1 pt-1">
                    {acct.top_categories.slice(0, 3).map((cat) => (
                      <div key={`${cat.category_id ?? 'uncat'}-${cat.category_name}`} className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground truncate mr-2">{cat.category_name}</span>
                        <span className="text-muted-foreground">{cat.share_pct.toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </FinancialCardContent>
    </FinancialCard>
  );
}

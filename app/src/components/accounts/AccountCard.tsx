import {
  Landmark,
  CreditCard,
  TrendingUp,
  Banknote,
  Wallet,
  MoreVertical,
  Pencil,
  Trash2,
} from 'lucide-react';
import type { Account } from '@/api/accounts';
import { formatMoney } from '@/lib/currency';

const TYPE_CONFIG: Record<
  string,
  { icon: typeof Landmark; label: string; defaultColor: string }
> = {
  bank: { icon: Landmark, label: 'Bank', defaultColor: '#3b82f6' },
  credit_card: { icon: CreditCard, label: 'Credit Card', defaultColor: '#ef4444' },
  investment: { icon: TrendingUp, label: 'Investment', defaultColor: '#10b981' },
  cash: { icon: Banknote, label: 'Cash', defaultColor: '#f59e0b' },
  wallet: { icon: Wallet, label: 'Wallet', defaultColor: '#8b5cf6' },
};

type Props = {
  account: Account;
  onEdit?: (account: Account) => void;
  onDelete?: (id: number) => void;
};

export function AccountCard({ account, onEdit, onDelete }: Props) {
  const cfg = TYPE_CONFIG[account.type] || TYPE_CONFIG.bank;
  const Icon = cfg.icon;
  const color = account.color || cfg.defaultColor;

  return (
    <div className="group relative rounded-xl border bg-card p-4 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ backgroundColor: `${color}20`, color }}
          >
            {account.icon ? (
              <span className="text-lg">{account.icon}</span>
            ) : (
              <Icon className="h-5 w-5" />
            )}
          </div>
          <div>
            <p className="font-medium leading-none">{account.name}</p>
            <p className="mt-1 text-xs text-muted-foreground">{cfg.label}</p>
          </div>
        </div>

        {(onEdit || onDelete) && (
          <div className="relative">
            <button
              className="rounded-md p-1 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-muted"
              onClick={(e) => {
                e.stopPropagation();
                // Simple menu for now — edit/delete shown in parent
              }}
            >
              <MoreVertical className="h-4 w-4 text-muted-foreground" />
            </button>
            {(onEdit || onDelete) && (
              <div className="absolute right-0 top-full z-10 mt-1 hidden w-32 rounded-md border bg-popover p-1 shadow-md group-hover:block">
                {onEdit && (
                  <button
                    className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-muted"
                    onClick={() => onEdit(account)}
                  >
                    <Pencil className="h-3 w-3" />
                    Edit
                  </button>
                )}
                {onDelete && (
                  <button
                    className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-destructive hover:bg-destructive/10"
                    onClick={() => onDelete(account.id)}
                  >
                    <Trash2 className="h-3 w-3" />
                    Delete
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-3">
        <p className="text-xl font-semibold" style={{ color }}>
          {formatMoney(account.balance, account.currency)}
        </p>
      </div>
    </div>
  );
}

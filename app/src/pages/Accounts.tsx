import { useEffect, useMemo, useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { AccountCard } from '@/components/accounts/AccountCard';
import { AccountOverview } from '@/components/accounts/AccountOverview';
import {
  listAccounts,
  getAccountOverview,
  createAccount,
  updateAccount,
  deleteAccount,
  type Account,
  type AccountCreate,
  type AccountType,
  type AccountOverview as OverviewType,
} from '@/api/accounts';

const ACCOUNT_TYPES: { value: AccountType; label: string }[] = [
  { value: 'bank', label: '🏦 Bank' },
  { value: 'credit_card', label: '💳 Credit Card' },
  { value: 'investment', label: '📈 Investment' },
  { value: 'cash', label: '💵 Cash' },
  { value: 'wallet', label: '👛 Wallet' },
];

const TYPE_LABELS: Record<string, string> = {
  bank: 'Bank',
  credit_card: 'Credit Card',
  investment: 'Investment',
  cash: 'Cash',
  wallet: 'Wallet',
};

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [overview, setOverview] = useState<OverviewType | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [form, setForm] = useState<AccountCreate>({ name: '', type: 'bank' });
  const [deleting, setDeleting] = useState<number | null>(null);

  async function loadData() {
    setLoading(true);
    try {
      const [accs, ov] = await Promise.all([
        listAccounts(),
        getAccountOverview(),
      ]);
      setAccounts(accs);
      setOverview(ov);
    } catch {
      // handled silently
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return accounts;
    const q = search.toLowerCase();
    return accounts.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        a.type.toLowerCase().includes(q),
    );
  }, [accounts, search]);

  const grouped = useMemo(() => {
    const groups: Record<string, Account[]> = {};
    for (const a of filtered) {
      const label = TYPE_LABELS[a.type] || a.type;
      (groups[label] ??= []).push(a);
    }
    return groups;
  }, [filtered]);

  function openCreate() {
    setEditing(null);
    setForm({ name: '', type: 'bank', balance: 0, currency: 'USD' });
    setDialogOpen(true);
  }

  function openEdit(account: Account) {
    setEditing(account);
    setForm({
      name: account.name,
      type: account.type,
      balance: account.balance,
      currency: account.currency,
      icon: account.icon,
      color: account.color,
    });
    setDialogOpen(true);
  }

  async function handleSave() {
    if (!form.name.trim()) return;
    try {
      if (editing) {
        await updateAccount(editing.id, form);
      } else {
        await createAccount(form);
      }
      setDialogOpen(false);
      loadData();
    } catch {
      // handled silently
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteAccount(id);
      loadData();
    } catch {
      // handled silently
    }
    setDeleting(null);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Accounts</h1>
          <p className="text-sm text-muted-foreground">
            Manage your financial accounts and track your net worth
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Add Account
        </Button>
      </div>

      {/* Overview */}
      <AccountOverview data={overview} loading={loading} />

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search accounts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Account Groups */}
      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-muted/50" />
          ))}
        </div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <p className="text-muted-foreground">
            {search ? 'No accounts match your search' : 'No accounts yet'}
          </p>
          {!search && (
            <Button variant="outline" className="mt-4" onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Add your first account
            </Button>
          )}
        </div>
      ) : (
        Object.entries(grouped).map(([label, items]) => (
          <div key={label} className="space-y-3">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold">{label}</h2>
              <Badge variant="secondary" className="text-xs">
                {items.length}
              </Badge>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((account) => (
                <AccountCard
                  key={account.id}
                  account={account}
                  onEdit={openEdit}
                  onDelete={(id) => setDeleting(id)}
                />
              ))}
            </div>
          </div>
        ))
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? 'Edit Account' : 'Add Account'}
            </DialogTitle>
            <DialogDescription>
              {editing
                ? 'Update your account details.'
                : 'Add a new financial account to track.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="mb-1 block text-sm font-medium">Name</label>
              <Input
                placeholder="e.g. Chase Checking"
                value={form.name}
                onChange={(e) =>
                  setForm({ ...form, name: e.target.value })
                }
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">Type</label>
              <div className="flex flex-wrap gap-2">
                {ACCOUNT_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setForm({ ...form, type: t.value })}
                    className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                      form.type === t.value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'hover:bg-muted'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Balance</label>
                <Input
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={form.balance ?? ''}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      balance: parseFloat(e.target.value) || 0,
                    })
                  }
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Currency</label>
                <Input
                  placeholder="USD"
                  value={form.currency ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, currency: e.target.value })
                  }
                  maxLength={10}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Icon (emoji)
                </label>
                <Input
                  placeholder="🏦"
                  value={form.icon ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, icon: e.target.value })
                  }
                  maxLength={4}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Color (hex)
                </label>
                <Input
                  placeholder="#3b82f6"
                  value={form.color ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, color: e.target.value })
                  }
                  maxLength={7}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={!form.name.trim()}>
              {editing ? 'Save Changes' : 'Create Account'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <Dialog open={deleting !== null} onOpenChange={() => setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Account</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this account? This action cannot
              be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleting && handleDelete(deleting)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

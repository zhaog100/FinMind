import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/components/ui/use-toast';
import { Progress } from '@/components/ui/progress';
import {
  PiggyBank,
  Plus,
  TrendingUp,
  TrendingDown,
  Trash2,
  Target,
  Calendar,
} from 'lucide-react';
import {
  listSavingsGoals,
  createSavingsGoal,
  deleteSavingsGoal,
  contributeToGoal,
  withdrawFromGoal,
  type SavingsGoal,
} from '@/api/savings';
import { formatMoney } from '@/lib/currency';

const ICON_OPTIONS = ['🎯', '🏠', '🚗', '✈️', '🎓', '💍', '💊', '🎮', '📱', '💰'];
const COLOR_OPTIONS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

function fmt(n: number) {
  return formatMoney(n);
}

function MilestoneBadge({ threshold, reached }: { threshold: number; reached: boolean }) {
  return (
    <span
      className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-[10px] font-bold border-2 ${
        reached
          ? 'bg-primary text-primary-foreground border-primary'
          : 'bg-muted text-muted-foreground border-muted-foreground/30'
      }`}
    >
      {threshold}%
    </span>
  );
}

function GoalCard({
  goal,
  onContribute,
  onWithdraw,
  onDelete,
}: {
  goal: SavingsGoal;
  onContribute: (g: SavingsGoal) => void;
  onWithdraw: (g: SavingsGoal) => void;
  onDelete: (g: SavingsGoal) => void;
}) {
  const pct = goal.target_amount > 0
    ? Math.min(100, (goal.current_amount / goal.target_amount) * 100)
    : 0;

  return (
    <div className="rounded-2xl border bg-card p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{goal.icon}</span>
          <div>
            <h3 className="font-semibold text-sm">{goal.name}</h3>
            {goal.days_left !== null && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {goal.days_left > 0 ? `${goal.days_left} days left` : 'Due today'}
              </p>
            )}
          </div>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={() => onDelete(goal)}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      <div className="mb-2">
        <div className="flex justify-between text-xs mb-1">
          <span className="font-medium">{fmt(goal.current_amount)}</span>
          <span className="text-muted-foreground">{fmt(goal.target_amount)}</span>
        </div>
        <div className="relative">
          <Progress value={pct} className="h-3" />
          {goal.milestones.map((m) => (
            <div
              key={m.threshold}
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-background"
              style={{
                left: `${m.threshold}%`,
                transform: 'translate(-50%, -50%)',
                backgroundColor: m.reached ? goal.color : '#d4d4d8',
              }}
              title={`${m.threshold}% — ${m.reached ? 'Reached!' : 'Not yet'}`}
            />
          ))}
        </div>
      </div>

      <div className="flex gap-1 mb-3">
        {goal.milestones.map((m) => (
          <MilestoneBadge key={m.threshold} threshold={m.threshold} reached={m.reached} />
        ))}
        <span className="text-xs text-muted-foreground ml-auto self-center">{pct.toFixed(1)}%</span>
      </div>

      {pct >= 100 && (
        <div className="mb-3 rounded-lg bg-green-500/10 text-green-600 text-xs font-medium px-3 py-1.5 text-center">
          🎉 Goal reached!
        </div>
      )}

      <div className="flex gap-2">
        <Button size="sm" variant="outline" className="flex-1" onClick={() => onContribute(goal)}>
          <TrendingUp className="h-3.5 w-3.5 mr-1" />
          Add
        </Button>
        <Button size="sm" variant="outline" className="flex-1" onClick={() => onWithdraw(goal)}>
          <TrendingDown className="h-3.5 w-3.5 mr-1" />
          Withdraw
        </Button>
      </div>
    </div>
  );
}

export function Savings() {
  const { toast } = useToast();
  const [goals, setGoals] = useState<SavingsGoal[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [txOpen, setTxOpen] = useState(false);
  const [txGoal, setTxGoal] = useState<SavingsGoal | null>(null);
  const [txType, setTxType] = useState<'contribute' | 'withdraw'>('contribute');
  const [txAmount, setTxAmount] = useState('');
  const [txNote, setTxNote] = useState('');

  // Create form state
  const [newName, setNewName] = useState('');
  const [newTarget, setNewTarget] = useState('');
  const [newDate, setNewDate] = useState('');
  const [newIcon, setNewIcon] = useState('🎯');
  const [newColor, setNewColor] = useState('#6366f1');

  const load = async () => {
    try {
      const data = await listSavingsGoals();
      setGoals(data);
    } catch (err: unknown) {
      toast({ title: 'Error', description: err instanceof Error ? err.message : 'Failed to load goals', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!newName.trim() || !newTarget) return;
    try {
      await createSavingsGoal({
        name: newName.trim(),
        target_amount: parseFloat(newTarget),
        target_date: newDate || null,
        icon: newIcon,
        color: newColor,
      });
      toast({ title: 'Goal created!' });
      setCreateOpen(false);
      setNewName('');
      setNewTarget('');
      setNewDate('');
      setNewIcon('🎯');
      setNewColor('#6366f1');
      load();
    } catch (err: unknown) {
      toast({ title: 'Error', description: err instanceof Error ? err.message : 'Failed', variant: 'destructive' });
    }
  };

  const handleDelete = async (goal: SavingsGoal) => {
    if (!confirm(`Delete "${goal.name}"? This cannot be undone.`)) return;
    try {
      await deleteSavingsGoal(goal.id);
      toast({ title: 'Goal deleted' });
      load();
    } catch (err: unknown) {
      toast({ title: 'Error', description: err instanceof Error ? err.message : 'Failed', variant: 'destructive' });
    }
  };

  const openTx = (goal: SavingsGoal, type: 'contribute' | 'withdraw') => {
    setTxGoal(goal);
    setTxType(type);
    setTxAmount('');
    setTxNote('');
    setTxOpen(true);
  };

  const handleTx = async () => {
    if (!txGoal || !txAmount) return;
    const amount = parseFloat(txAmount);
    if (isNaN(amount) || amount <= 0) return;
    try {
      if (txType === 'contribute') {
        await contributeToGoal(txGoal.id, amount, txNote || undefined);
        toast({ title: `Added ${fmt(amount)} to "${txGoal.name}"` });
      } else {
        await withdrawFromGoal(txGoal.id, amount, txNote || undefined);
        toast({ title: `Withdrew ${fmt(amount)} from "${txGoal.name}"` });
      }
      setTxOpen(false);
      load();
    } catch (err: unknown) {
      toast({ title: 'Error', description: err instanceof Error ? err.message : 'Failed', variant: 'destructive' });
    }
  };

  const totalSaved = goals.reduce((s, g) => s + g.current_amount, 0);
  const totalTarget = goals.reduce((s, g) => s + g.target_amount, 0);
  const completedCount = goals.filter((g) => g.current_amount >= g.target_amount).length;

  return (
    <div className="container-financial py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <PiggyBank className="h-6 w-6 text-primary" />
            Savings Goals
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track your savings and celebrate milestones
          </p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button><Plus className="h-4 w-4 mr-2" />New Goal</Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Create Savings Goal</DialogTitle>
              <DialogDescription>Set a target and start saving towards it.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="s-name">Goal Name</Label>
                <Input id="s-name" placeholder="e.g. Emergency Fund" value={newName} onChange={(e) => setNewName(e.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="s-target">Target Amount</Label>
                <Input id="s-target" type="number" min="0" step="0.01" placeholder="10000" value={newTarget} onChange={(e) => setNewTarget(e.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="s-date">Target Date (optional)</Label>
                <Input id="s-date" type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label>Icon</Label>
                <div className="flex gap-2 flex-wrap">
                  {ICON_OPTIONS.map((ic) => (
                    <button
                      key={ic}
                      type="button"
                      className={`w-10 h-10 rounded-lg text-xl flex items-center justify-center border-2 transition ${newIcon === ic ? 'border-primary bg-primary/10' : 'border-transparent hover:bg-muted'}`}
                      onClick={() => setNewIcon(ic)}
                    >
                      {ic}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid gap-2">
                <Label>Color</Label>
                <div className="flex gap-2 flex-wrap">
                  {COLOR_OPTIONS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      className={`w-8 h-8 rounded-full border-2 transition ${newColor === c ? 'border-foreground scale-110' : 'border-transparent'}`}
                      style={{ backgroundColor: c }}
                      onClick={() => setNewColor(c)}
                    />
                  ))}
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={!newName.trim() || !newTarget}>Create Goal</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="rounded-xl border bg-card p-4">
          <p className="text-xs text-muted-foreground mb-1">Total Saved</p>
          <p className="text-lg font-bold">{fmt(totalSaved)}</p>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-xs text-muted-foreground mb-1">Total Target</p>
          <p className="text-lg font-bold">{fmt(totalTarget)}</p>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-xs text-muted-foreground mb-1">Goals Completed</p>
          <p className="text-lg font-bold flex items-center gap-1">
            <Target className="h-4 w-4" />
            {completedCount} / {goals.length}
          </p>
        </div>
      </div>

      {/* Goal grid */}
      {loading ? (
        <div className="text-center py-12 text-muted-foreground">Loading…</div>
      ) : goals.length === 0 ? (
        <div className="text-center py-16">
          <PiggyBank className="h-12 w-12 mx-auto text-muted-foreground/40 mb-4" />
          <h3 className="text-lg font-medium mb-1">No savings goals yet</h3>
          <p className="text-sm text-muted-foreground mb-4">Create your first goal and start tracking your savings!</p>
          <Button onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4 mr-2" />New Goal</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {goals.map((g) => (
            <GoalCard key={g.id} goal={g} onContribute={(goal) => openTx(goal, 'contribute')} onWithdraw={(goal) => openTx(goal, 'withdraw')} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {/* Transaction dialog */}
      <Dialog open={txOpen} onOpenChange={setTxOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {txType === 'contribute' ? '💰 Add Funds' : '💸 Withdraw'}
            </DialogTitle>
            <DialogDescription>
              {txGoal?.name} — Current: {txGoal ? fmt(txGoal.current_amount) : ''}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="tx-amount">Amount</Label>
              <Input id="tx-amount" type="number" min="0" step="0.01" placeholder="100" value={txAmount} onChange={(e) => setTxAmount(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tx-note">Note (optional)</Label>
              <Input id="tx-note" placeholder="Monthly savings" value={txNote} onChange={(e) => setTxNote(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTxOpen(false)}>Cancel</Button>
            <Button onClick={handleTx} disabled={!txAmount}>
              {txType === 'contribute' ? 'Add Funds' : 'Withdraw'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

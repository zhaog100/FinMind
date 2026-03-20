import { useState, useEffect } from 'react';
import { listGoals, getGoalSummary, createGoal, contributeToGoal, deleteGoal, type SavingsGoal, type GoalsSummary, type GoalCreate } from '../api/savings-goals';
import { formatMoney } from '../lib/currency';

export default function SavingsGoals() {
  const [goals, setGoals] = useState<SavingsGoal[]>([]);
  const [summary, setSummary] = useState<GoalsSummary | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const [g, s] = await Promise.all([listGoals(), getGoalSummary()]);
    setGoals(g);
    setSummary(s);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (data: GoalCreate) => {
    await createGoal(data);
    setShowCreate(false);
    load();
  };

  const handleContribute = async (id: number, amount: number) => {
    await contributeToGoal(id, amount);
    load();
  };

  const handleDelete = async (id: number) => {
    if (confirm('Delete this goal?')) {
      await deleteGoal(id);
      load();
    }
  };

  if (loading) return <div className="p-6">Loading goals...</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Savings Goals</h1>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          + New Goal
        </button>
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SummaryCard label="Total Goals" value={String(summary.total_goals)} />
          <SummaryCard label="Active" value={String(summary.active)} />
          <SummaryCard label="Total Saved" value={formatMoney(summary.total_saved)} />
          <SummaryCard label="Overall Progress" value={`${summary.overall_progress}%`} />
        </div>
      )}

      <div className="grid gap-4">
        {goals.map(goal => (
          <GoalCard key={goal.id} goal={goal} onContribute={handleContribute} onDelete={handleDelete} />
        ))}
        {goals.length === 0 && (
          <div className="text-center py-12 text-gray-500">No savings goals yet. Create one to start tracking!</div>
        )}
      </div>

      {showCreate && <CreateGoalDialog onSave={handleCreate} onClose={() => setShowCreate(false)} />}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 rounded-lg border bg-card">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="text-xl font-bold mt-1">{value}</div>
    </div>
  );
}

function GoalCard({ goal, onContribute, onDelete }: { goal: SavingsGoal; onContribute: (id: number, amount: number) => void; onDelete: (id: number) => void }) {
  const [amount, setAmount] = useState('');
  const completed = goal.progress_percent >= 100;
  return (
    <div className={`p-4 rounded-lg border ${completed ? 'border-green-300 bg-green-50' : 'bg-card'}`}>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-lg">{goal.name}</h3>
          <div className="text-sm text-muted-foreground">
            {formatMoney(goal.current_amount, goal.currency)} / {formatMoney(goal.target_amount, goal.currency)}
            {goal.category && <span className="ml-2">· {goal.category}</span>}
            {goal.days_left !== null && goal.days_left >= 0 && <span className="ml-2">· {goal.days_left} days left</span>}
          </div>
        </div>
        <button onClick={() => onDelete(goal.id)} className="text-red-500 text-sm hover:underline">Delete</button>
      </div>

      {/* Progress bar */}
      <div className="mt-3">
        <div className="flex justify-between text-sm mb-1">
          <span>{goal.progress_percent}%</span>
          {goal.milestones.length > 0 && <span className="text-green-600">🎯 {goal.milestones.join(', ')}</span>}
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all ${completed ? 'bg-green-500' : 'bg-blue-500'}`}
            style={{ width: `${Math.min(100, goal.progress_percent)}%` }}
          />
        </div>
        {/* Milestone markers */}
        <div className="relative h-4 mt-1">
          {[25, 50, 75, 100].map(m => (
            <div key={m} className="absolute" style={{ left: `${m - 2}%` }}>
              <div className={`w-0.5 h-2 ${goal.progress_percent >= m ? 'bg-green-500' : 'bg-gray-300'}`} />
            </div>
          ))}
        </div>
      </div>

      {/* Contribute */}
      {!completed && (
        <div className="mt-3 flex gap-2">
          <input
            type="number" placeholder="Amount" value={amount}
            onChange={e => setAmount(e.target.value)}
            className="border rounded px-3 py-1 w-32 text-sm"
          />
          <button
            onClick={() => { if (amount) { onContribute(goal.id, parseFloat(amount)); setAmount(''); } }}
            className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
          >Add Savings</button>
        </div>
      )}

      {/* Recent contributions */}
      {goal.recent_contributions && goal.recent_contributions.length > 0 && (
        <div className="mt-3 text-sm text-muted-foreground">
          Recent: {goal.recent_contributions.slice(0, 3).map(c => formatMoney(c.amount, goal.currency)).join(', ')}
        </div>
      )}
    </div>
  );
}

function CreateGoalDialog({ onSave, onClose }: { onSave: (data: GoalCreate) => void; onClose: () => void }) {
  const [name, setName] = useState('');
  const [target, setTarget] = useState('');
  const [category, setCategory] = useState('');
  const [targetDate, setTargetDate] = useState('');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md space-y-4">
        <h2 className="text-lg font-bold">Create Savings Goal</h2>
        <input placeholder="Goal name" value={name} onChange={e => setName(e.target.value)} className="w-full border rounded px-3 py-2" />
        <input type="number" placeholder="Target amount" value={target} onChange={e => setTarget(e.target.value)} className="w-full border rounded px-3 py-2" />
        <input placeholder="Category (optional)" value={category} onChange={e => setCategory(e.target.value)} className="w-full border rounded px-3 py-2" />
        <input type="date" value={targetDate} onChange={e => setTargetDate(e.target.value)} className="w-full border rounded px-3 py-2" />
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 border rounded">Cancel</button>
          <button onClick={() => onSave({ name, target_amount: parseFloat(target), category: category || undefined, target_date: targetDate || undefined })} className="px-4 py-2 bg-blue-600 text-white rounded" disabled={!name || !target}>Create</button>
        </div>
      </div>
    </div>
  );
}

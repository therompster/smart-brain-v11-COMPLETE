<script>
  import { onMount } from 'svelte';
  
  let summary = null;
  let bills = [];
  let subscriptions = [];
  let loans = [];
  let loading = true;
  let activeTab = 'overview';
  
  onMount(async () => {
    await loadData();
  });
  
  async function loadData() {
    loading = true;
    try {
      const [summaryRes, billsRes, subsRes, loansRes] = await Promise.all([
        fetch('/api/financial/summary'),
        fetch('/api/financial/bills/upcoming?days=30'),
        fetch('/api/financial/subscriptions'),
        fetch('/api/financial/loans')
      ]);
      
      summary = await summaryRes.json();
      const billsData = await billsRes.json();
      bills = billsData.bills || [];
      const subsData = await subsRes.json();
      subscriptions = subsData.subscriptions || [];
      const loansData = await loansRes.json();
      loans = loansData.loans || [];
    } catch (err) {
      console.error('Failed to load financial data:', err);
    }
    loading = false;
  }
  
  async function markPaid(billId, amount) {
    await fetch(`/api/financial/bills/${billId}/pay?paid_amount=${amount}`, { method: 'POST' });
    await loadData();
  }
  
  function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount || 0);
  }
  
  function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
  
  function isOverdue(dateStr) {
    if (!dateStr) return false;
    return new Date(dateStr) < new Date();
  }
</script>

<div class="max-w-6xl mx-auto">
  <div class="mb-6">
    <h1 class="text-3xl font-bold text-white mb-2">💰 Financial Dashboard</h1>
    <p class="text-slate-400">Track bills, subscriptions, and loans</p>
  </div>
  
  {#if loading}
    <div class="text-center py-16 text-slate-400">Loading financial data...</div>
  {:else}
    <!-- Summary Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
      <!-- Pending Bills -->
      <div class="bg-gradient-to-br from-amber-900/30 to-orange-900/30 border border-amber-700/50 rounded-xl p-5">
        <div class="text-amber-400 text-sm mb-1">Pending Bills</div>
        <div class="text-3xl font-bold text-white">{formatCurrency(summary?.pending_bills?.total)}</div>
        <div class="text-sm text-slate-400">{summary?.pending_bills?.count || 0} bills due</div>
      </div>
      
      <!-- Overdue -->
      <div class="bg-gradient-to-br from-red-900/30 to-pink-900/30 border border-red-700/50 rounded-xl p-5">
        <div class="text-red-400 text-sm mb-1">Overdue</div>
        <div class="text-3xl font-bold text-white">{formatCurrency(summary?.overdue_bills?.total)}</div>
        <div class="text-sm text-slate-400">{summary?.overdue_bills?.count || 0} overdue</div>
      </div>
      
      <!-- Monthly Subscriptions -->
      <div class="bg-gradient-to-br from-blue-900/30 to-cyan-900/30 border border-blue-700/50 rounded-xl p-5">
        <div class="text-blue-400 text-sm mb-1">Monthly Subscriptions</div>
        <div class="text-3xl font-bold text-white">{formatCurrency(summary?.subscriptions?.monthly_cost)}</div>
        <div class="text-sm text-slate-400">{summary?.subscriptions?.count || 0} active</div>
      </div>
      
      <!-- Total Debt -->
      <div class="bg-gradient-to-br from-purple-900/30 to-violet-900/30 border border-purple-700/50 rounded-xl p-5">
        <div class="text-purple-400 text-sm mb-1">Total Loan Debt</div>
        <div class="text-3xl font-bold text-white">{formatCurrency(summary?.loans?.total_debt)}</div>
        <div class="text-sm text-slate-400">{formatCurrency(summary?.loans?.monthly_payments)}/mo payments</div>
      </div>
    </div>
    
    <!-- Monthly Obligations -->
    <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-5 mb-8">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-slate-400 text-sm">Total Monthly Obligations</div>
          <div class="text-4xl font-bold text-white">{formatCurrency(summary?.total_monthly_obligations)}</div>
        </div>
        <div class="text-6xl">📊</div>
      </div>
    </div>
    
    <!-- Tabs -->
    <div class="flex gap-2 mb-6">
      <button
        on:click={() => activeTab = 'bills'}
        class="px-4 py-2 rounded-lg transition-colors {activeTab === 'bills' ? 'bg-amber-600 text-white' : 'text-slate-300 hover:bg-slate-800'}"
      >
        Bills ({bills.length})
      </button>
      <button
        on:click={() => activeTab = 'subscriptions'}
        class="px-4 py-2 rounded-lg transition-colors {activeTab === 'subscriptions' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}"
      >
        Subscriptions ({subscriptions.length})
      </button>
      <button
        on:click={() => activeTab = 'loans'}
        class="px-4 py-2 rounded-lg transition-colors {activeTab === 'loans' ? 'bg-purple-600 text-white' : 'text-slate-300 hover:bg-slate-800'}"
      >
        Loans ({loans.length})
      </button>
    </div>
    
    <!-- Bills Tab -->
    {#if activeTab === 'bills'}
      <div class="space-y-3">
        {#if bills.length === 0}
          <div class="text-center py-12 text-slate-400">No upcoming bills</div>
        {:else}
          {#each bills as bill}
            <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-4 flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-full bg-amber-600/20 flex items-center justify-center text-2xl">
                  📄
                </div>
                <div>
                  <div class="font-semibold text-white">{bill.name}</div>
                  <div class="text-sm text-slate-400">
                    {bill.vendor || 'Unknown vendor'} • {bill.category || 'Uncategorized'}
                  </div>
                </div>
              </div>
              
              <div class="flex items-center gap-6">
                <div class="text-right">
                  <div class="text-xl font-bold text-white">{formatCurrency(bill.amount)}</div>
                  <div class="text-sm {isOverdue(bill.due_date) ? 'text-red-400' : 'text-slate-400'}">
                    Due {formatDate(bill.due_date)}
                    {#if isOverdue(bill.due_date)}
                      <span class="ml-1">⚠️</span>
                    {/if}
                  </div>
                </div>
                
                <button
                  on:click={() => markPaid(bill.id, bill.amount)}
                  class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium"
                >
                  Mark Paid
                </button>
              </div>
            </div>
          {/each}
        {/if}
      </div>
    {/if}
    
    <!-- Subscriptions Tab -->
    {#if activeTab === 'subscriptions'}
      <div class="space-y-3">
        {#if subscriptions.length === 0}
          <div class="text-center py-12 text-slate-400">No active subscriptions</div>
        {:else}
          {#each subscriptions as sub}
            <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-4 flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-full bg-blue-600/20 flex items-center justify-center text-2xl">
                  🔄
                </div>
                <div>
                  <div class="font-semibold text-white">{sub.name}</div>
                  <div class="text-sm text-slate-400">
                    {sub.vendor || 'Unknown'} • {sub.frequency}
                    {#if sub.auto_pay}
                      <span class="ml-2 text-green-400">Auto-pay ✓</span>
                    {/if}
                  </div>
                </div>
              </div>
              
              <div class="text-right">
                <div class="text-xl font-bold text-white">{formatCurrency(sub.amount)}</div>
                <div class="text-sm text-slate-400">
                  Next: {formatDate(sub.next_due_date)}
                </div>
              </div>
            </div>
          {/each}
        {/if}
      </div>
    {/if}
    
    <!-- Loans Tab -->
    {#if activeTab === 'loans'}
      <div class="space-y-3">
        {#if loans.length === 0}
          <div class="text-center py-12 text-slate-400">No active loans</div>
        {:else}
          {#each loans as loan}
            <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-4">
                  <div class="w-12 h-12 rounded-full bg-purple-600/20 flex items-center justify-center text-2xl">
                    🏦
                  </div>
                  <div>
                    <div class="font-semibold text-white">{loan.name}</div>
                    <div class="text-sm text-slate-400">
                      {loan.lender || 'Unknown lender'} • {loan.loan_type || 'Loan'}
                    </div>
                  </div>
                </div>
                
                <div class="text-right">
                  <div class="text-xl font-bold text-white">{formatCurrency(loan.current_balance)}</div>
                  <div class="text-sm text-slate-400">
                    {formatCurrency(loan.monthly_payment)}/mo @ {loan.interest_rate}%
                  </div>
                </div>
              </div>
              
              <!-- Progress bar -->
              <div class="mt-3">
                <div class="flex justify-between text-xs text-slate-400 mb-1">
                  <span>Progress</span>
                  <span>{Math.round((1 - loan.current_balance / loan.original_principal) * 100)}% paid</span>
                </div>
                <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    class="h-full bg-purple-500 transition-all"
                    style="width: {(1 - loan.current_balance / loan.original_principal) * 100}%"
                  ></div>
                </div>
                <div class="flex justify-between text-xs text-slate-500 mt-1">
                  <span>{formatCurrency(loan.original_principal - loan.current_balance)} paid</span>
                  <span>{formatCurrency(loan.original_principal)} total</span>
                </div>
              </div>
            </div>
          {/each}
        {/if}
      </div>
    {/if}
  {/if}
</div>

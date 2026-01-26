<script>
  import { onMount } from 'svelte';
  
  let tasks = [];
  let loading = true;
  let filter = 'all';
  let domainFilter = 'all';
  let domains = [];
  let view = 'grouped'; // 'grouped' or 'flat'
  
  const priorityColors = {
    'high': 'border-red-500 bg-red-500/10',
    'medium': 'border-amber-500 bg-amber-500/10',
    'low': 'border-blue-500 bg-blue-500/10'
  };
  
  const priorityBadge = {
    'high': 'bg-red-500',
    'medium': 'bg-amber-500',
    'low': 'bg-blue-500'
  };
  
  onMount(async () => {
    await Promise.all([loadTasks(), loadDomains()]);
  });
  
  async function loadTasks() {
    loading = true;
    const res = await fetch('/api/tasks?status=open');
    tasks = await res.json();
    loading = false;
  }
  
  async function loadDomains() {
    const res = await fetch('/api/domains');
    const data = await res.json();
    domains = data.domains || [];
  }
  
  async function completeTask(taskId) {
    await fetch(`/api/tasks/${taskId}/complete`, { method: 'POST' });
    await loadTasks();
  }
  
  async function promoteToToday(taskId) {
    // In a real impl, this would add to today's plan
    alert('Task promoted to today\'s focus!');
  }
  
  function getXpForTask(task) {
    const base = { high: 100, medium: 50, low: 20 }[task.priority] || 50;
    const durationBonus = Math.floor((task.estimated_duration_minutes || 30) / 15) * 10;
    return base + durationBonus;
  }
  
  $: filteredTasks = tasks.filter(t => {
    if (filter !== 'all' && t.priority !== filter) return false;
    if (domainFilter !== 'all' && t.domain !== domainFilter) return false;
    return true;
  });
  
  $: quickWins = filteredTasks.filter(t => (t.estimated_duration_minutes || 30) <= 30);
  $: bigTasks = filteredTasks.filter(t => (t.estimated_duration_minutes || 30) > 60);
  $: mediumTasks = filteredTasks.filter(t => {
    const dur = t.estimated_duration_minutes || 30;
    return dur > 30 && dur <= 60;
  });
  
  $: tasksByDomain = filteredTasks.reduce((acc, task) => {
    const domain = task.domain || 'uncategorized';
    if (!acc[domain]) acc[domain] = [];
    acc[domain].push(task);
    return acc;
  }, {});
  
  $: totalTime = filteredTasks.reduce((sum, t) => sum + (t.estimated_duration_minutes || 30), 0);
  $: totalXp = filteredTasks.reduce((sum, t) => sum + getXpForTask(t), 0);
</script>

<div class="max-w-5xl mx-auto space-y-6">
  <!-- Header Stats -->
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-white">Tasks</h1>
      <p class="text-slate-400 text-sm">{filteredTasks.length} tasks · ~{Math.round(totalTime/60)}h total · {totalXp} XP potential</p>
    </div>
    <div class="flex gap-2">
      <button 
        on:click={() => view = 'grouped'}
        class="px-3 py-1.5 rounded-lg text-sm {view === 'grouped' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'}"
      >
        Grouped
      </button>
      <button 
        on:click={() => view = 'flat'}
        class="px-3 py-1.5 rounded-lg text-sm {view === 'flat' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'}"
      >
        All
      </button>
    </div>
  </div>
  
  <!-- Filters -->
  <div class="flex gap-4 flex-wrap">
    <!-- Priority Filter -->
    <div class="flex items-center gap-2">
      <span class="text-xs text-slate-400">Priority:</span>
      <div class="flex gap-1">
        {#each ['all', 'high', 'medium', 'low'] as p}
          <button
            on:click={() => filter = p}
            class="px-3 py-1 rounded-full text-xs capitalize transition-colors {filter === p ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
          >
            {p}
          </button>
        {/each}
      </div>
    </div>
    
    <!-- Domain Filter -->
    <div class="flex items-center gap-2">
      <span class="text-xs text-slate-400">Domain:</span>
      <select 
        bind:value={domainFilter}
        class="bg-slate-700 text-white text-sm px-3 py-1 rounded-lg border border-slate-600"
      >
        <option value="all">All domains</option>
        {#each domains as d}
          <option value={d.path || d}>{d.name || d}</option>
        {/each}
      </select>
    </div>
  </div>
  
  {#if loading}
    <div class="text-center py-16">
      <div class="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
      <div class="text-slate-400">Loading tasks...</div>
    </div>
  {:else if filteredTasks.length === 0}
    <div class="text-center py-16 bg-slate-800/30 rounded-xl border border-slate-700">
      <div class="text-4xl mb-4">✨</div>
      <div class="text-white font-semibold">No tasks match your filters</div>
      <div class="text-slate-400 text-sm">Try adjusting the filters above</div>
    </div>
  {:else if view === 'grouped'}
    <!-- Grouped View -->
    <div class="space-y-6">
      <!-- Quick Wins Section -->
      {#if quickWins.length > 0}
        <div class="bg-emerald-900/20 border border-emerald-700/50 rounded-xl p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-emerald-400 flex items-center gap-2">
              🎯 Quick Wins <span class="text-sm font-normal text-emerald-400/70">≤30 min</span>
            </h2>
            <span class="text-xs text-emerald-400/70">{quickWins.length} tasks</span>
          </div>
          <div class="grid gap-2">
            {#each quickWins.slice(0, 5) as task}
              <div class="flex items-center gap-3 bg-slate-800/50 rounded-lg p-3 group">
                <button 
                  on:click={() => completeTask(task.id)}
                  class="w-5 h-5 rounded border-2 border-emerald-500/50 hover:bg-emerald-500 transition-colors flex-shrink-0"
                ></button>
                <div class="flex-1 min-w-0">
                  <div class="text-white font-medium truncate">{task.action}</div>
                  <div class="text-xs text-slate-400">{task.domain?.split('/')[1]} · ~{task.estimated_duration_minutes || 30}m</div>
                </div>
                <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span class="text-xs text-amber-400">+{getXpForTask(task)} XP</span>
                  <button 
                    on:click={() => completeTask(task.id)}
                    class="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs"
                  >
                    Done
                  </button>
                </div>
              </div>
            {/each}
            {#if quickWins.length > 5}
              <div class="text-center text-xs text-slate-400 pt-2">+{quickWins.length - 5} more quick wins</div>
            {/if}
          </div>
        </div>
      {/if}
      
      <!-- By Domain -->
      {#each Object.entries(tasksByDomain) as [domain, domainTasks]}
        <div class="bg-slate-800/30 border border-slate-700 rounded-xl p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-white capitalize">
              {domain.split('/').pop()}
            </h2>
            <span class="text-xs text-slate-500">{domainTasks.length} tasks</span>
          </div>
          <div class="space-y-2">
            {#each domainTasks.slice(0, 8) as task}
              <div class="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-slate-800/50 transition-colors group border-l-2 {priorityColors[task.priority]}">
                <button 
                  on:click={() => completeTask(task.id)}
                  class="w-5 h-5 rounded border-2 border-slate-500 hover:border-green-500 hover:bg-green-500 transition-colors flex-shrink-0"
                ></button>
                <div class="flex-1 min-w-0">
                  <div class="text-white font-medium truncate">{task.action}</div>
                </div>
                <div class="flex items-center gap-3 text-xs">
                  <span class="{priorityBadge[task.priority]} text-white px-2 py-0.5 rounded capitalize">{task.priority}</span>
                  <span class="text-slate-400">~{task.estimated_duration_minutes || 30}m</span>
                  <span class="text-amber-400/70 opacity-0 group-hover:opacity-100">+{getXpForTask(task)}</span>
                </div>
              </div>
            {/each}
            {#if domainTasks.length > 8}
              <div class="text-center text-xs text-slate-400 pt-2">+{domainTasks.length - 8} more</div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <!-- Flat View -->
    <div class="bg-slate-800/30 border border-slate-700 rounded-xl overflow-hidden">
      <table class="w-full">
        <thead class="bg-slate-800">
          <tr class="text-left text-xs text-slate-400 uppercase">
            <th class="p-3 w-10"></th>
            <th class="p-3">Task</th>
            <th class="p-3 w-24">Priority</th>
            <th class="p-3 w-20">Time</th>
            <th class="p-3 w-24">Domain</th>
            <th class="p-3 w-16">XP</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700">
          {#each filteredTasks as task}
            <tr class="hover:bg-slate-800/50 transition-colors">
              <td class="p-3">
                <button 
                  on:click={() => completeTask(task.id)}
                  class="w-5 h-5 rounded border-2 border-slate-500 hover:border-green-500 hover:bg-green-500 transition-colors"
                ></button>
              </td>
              <td class="p-3">
                <div class="text-white font-medium">{task.action}</div>
                <div class="text-xs text-slate-500 truncate max-w-md">{task.text}</div>
              </td>
              <td class="p-3">
                <span class="{priorityBadge[task.priority]} text-white text-xs px-2 py-0.5 rounded capitalize">{task.priority}</span>
              </td>
              <td class="p-3 text-slate-300 text-sm">~{task.estimated_duration_minutes || 30}m</td>
              <td class="p-3 text-slate-400 text-sm">{task.domain?.split('/')[1]}</td>
              <td class="p-3 text-amber-400 text-sm">+{getXpForTask(task)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

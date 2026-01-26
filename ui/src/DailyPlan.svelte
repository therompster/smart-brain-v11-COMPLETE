<script>
  import { onMount } from 'svelte';
  
  let tasks = [];
  let stats = null;
  let loading = true;
  let currentIndex = 0;
  let showQueue = true;
  
  onMount(async () => {
    await loadData();
  });
  
  async function loadData() {
    loading = true;
    
    // Get all open tasks
    const tasksRes = await fetch('/api/tasks?status=open');
    tasks = await tasksRes.json();
    
    // Get stats
    try {
      const statsRes = await fetch('/api/stats/today');
      stats = await statsRes.json();
    } catch (e) {
      stats = { completed_today: 0, xp_today: 0, streak: 0 };
    }
    
    loading = false;
  }
  
  async function completeTask(taskId) {
    await fetch(`/api/tasks/${taskId}/complete`, { method: 'POST' });
    await loadData();
    if (currentIndex >= tasks.length) currentIndex = 0;
  }
  
  function skipTask() {
    currentIndex = (currentIndex + 1) % tasks.length;
  }
  
  function selectTask(index) {
    currentIndex = index;
  }
  
  function getXP(task) {
    const base = { high: 100, medium: 50, low: 20 }[task.priority] || 50;
    const duration = task.estimated_duration_minutes || 30;
    return base + Math.floor(duration / 15) * 10;
  }
  
  $: currentTask = tasks[currentIndex];
  $: totalXP = tasks.reduce((sum, t) => sum + getXP(t), 0);
  
  const priorityColors = {
    high: 'border-red-500 bg-red-500/10',
    medium: 'border-amber-500 bg-amber-500/10',
    low: 'border-blue-500 bg-blue-500/10'
  };
  
  const priorityDots = {
    high: 'bg-red-500',
    medium: 'bg-amber-500', 
    low: 'bg-blue-500'
  };
</script>

<div class="flex gap-6 h-[calc(100vh-140px)]">
  
  <!-- MAIN: Current Task Focus -->
  <div class="flex-1 flex flex-col">
    
    {#if loading}
      <div class="flex-1 flex items-center justify-center">
        <div class="text-slate-400">Loading...</div>
      </div>
      
    {:else if tasks.length === 0}
      <div class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="text-6xl mb-4">🎉</div>
          <h2 class="text-2xl font-bold text-white mb-2">All clear!</h2>
          <p class="text-slate-400">No tasks right now</p>
        </div>
      </div>
      
    {:else if currentTask}
      <!-- Stats bar -->
      <div class="flex items-center gap-6 mb-6 text-sm">
        <div class="flex items-center gap-2 text-amber-400">
          <span>⚡</span>
          <span class="font-bold">{stats?.xp_today || 0} XP</span>
          <span class="text-slate-500">today</span>
        </div>
        <div class="flex items-center gap-2 text-orange-400">
          <span>🔥</span>
          <span class="font-bold">{stats?.streak || 0}</span>
          <span class="text-slate-500">day streak</span>
        </div>
        <div class="text-slate-500">
          {stats?.completed_today || 0} done · {tasks.length} remaining
        </div>
      </div>
      
      <!-- Current Task Card -->
      <div class="flex-1 flex items-center justify-center">
        <div class="w-full max-w-2xl">
          <div class="bg-gradient-to-br from-slate-800 to-slate-900 border-2 {priorityColors[currentTask.priority]} rounded-2xl p-8">
            
            <div class="text-center mb-6">
              <div class="text-sm text-slate-400 mb-3 uppercase tracking-wide">Focus on this</div>
              <h1 class="text-3xl font-bold text-white mb-4 leading-tight">{currentTask.action}</h1>
              
              {#if currentTask.text && currentTask.text !== currentTask.action}
                <div class="bg-slate-800/50 rounded-lg p-4 text-left mb-4">
                  <div class="text-xs text-slate-500 mb-1">Context:</div>
                  <div class="text-slate-300 text-sm whitespace-pre-wrap">{currentTask.text}</div>
                </div>
              {/if}
              
              <div class="flex items-center justify-center gap-4 text-sm text-slate-400">
                <span class="flex items-center gap-1">
                  <span class="w-2 h-2 rounded-full {priorityDots[currentTask.priority]}"></span>
                  {currentTask.priority}
                </span>
                {#if currentTask.estimated_duration_minutes}
                  <span>~{currentTask.estimated_duration_minutes}m</span>
                {/if}
                <span class="text-amber-400">+{getXP(currentTask)} XP</span>
              </div>
            </div>
            
            <div class="flex gap-3 justify-center">
              <button
                on:click={() => completeTask(currentTask.id)}
                class="px-8 py-4 bg-green-600 hover:bg-green-700 text-white rounded-xl font-bold text-lg transition-all"
              >
                ✓ Done
              </button>
              <button
                on:click={skipTask}
                class="px-6 py-4 bg-slate-700 hover:bg-slate-600 text-white rounded-xl transition-all"
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      </div>
    {/if}
  </div>
  
  <!-- SIDEBAR: Task Queue -->
  <div class="w-80 flex flex-col">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wide">Queue ({tasks.length})</h3>
      <button 
        on:click={() => showQueue = !showQueue}
        class="text-xs text-slate-500 hover:text-slate-300"
      >
        {showQueue ? 'Hide' : 'Show'}
      </button>
    </div>
    
    {#if showQueue}
      <div class="flex-1 overflow-y-auto space-y-2 pr-2">
        {#each tasks as task, i}
          <button
            on:click={() => selectTask(i)}
            class="w-full text-left p-3 rounded-lg border transition-all {
              i === currentIndex 
                ? 'bg-blue-600/20 border-blue-500' 
                : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
            }"
          >
            <div class="flex items-start gap-2">
              <span class="w-2 h-2 rounded-full mt-1.5 flex-shrink-0 {priorityDots[task.priority]}"></span>
              <div class="flex-1 min-w-0">
                <div class="text-sm text-white truncate">{task.action}</div>
                <div class="flex items-center gap-2 mt-1 text-xs text-slate-500">
                  {#if task.estimated_duration_minutes}
                    <span>{task.estimated_duration_minutes}m</span>
                  {/if}
                  <span>{task.domain?.split('/')[1] || task.domain}</span>
                </div>
              </div>
            </div>
          </button>
        {/each}
      </div>
      
      <!-- Queue summary -->
      <div class="mt-4 pt-4 border-t border-slate-700 text-xs text-slate-500">
        <div class="flex justify-between">
          <span>Total time:</span>
          <span>{Math.round(tasks.reduce((s, t) => s + (t.estimated_duration_minutes || 30), 0) / 60)}h {tasks.reduce((s, t) => s + (t.estimated_duration_minutes || 30), 0) % 60}m</span>
        </div>
        <div class="flex justify-between mt-1">
          <span>Potential XP:</span>
          <span class="text-amber-400">{totalXP}</span>
        </div>
      </div>
    {/if}
  </div>
</div>

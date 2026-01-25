<script>
  import { onMount } from 'svelte';
  
  let plan = null;
  let loading = true;
  let currentIndex = 0;
  
  onMount(async () => {
    await loadPlan();
  });
  
  async function loadPlan() {
    loading = true;
    const res = await fetch('/api/plan/daily');
    plan = await res.json();
    loading = false;
  }
  
  async function completeTask(taskId) {
    await fetch(`/api/tasks/${taskId}/complete`, { method: 'POST' });
    currentIndex++;
    if (currentIndex >= (plan.upcoming?.length || 0) + 1) {
      await loadPlan();
      currentIndex = 0;
    }
  }
  
  $: currentTask = currentIndex === 0 ? plan?.current_task : plan?.upcoming?.[currentIndex - 1];
  $: hasMore = plan && (currentIndex < (plan.upcoming?.length || 0));
</script>

<div class="max-w-3xl mx-auto">
  {#if loading}
    <div class="text-center py-16">
      <div class="text-slate-400">Planning your day...</div>
    </div>
  {:else if !plan?.current_task}
    <div class="bg-gradient-to-br from-green-900/20 to-emerald-900/20 border border-green-700/50 rounded-2xl p-12 text-center">
      <div class="text-6xl mb-4">🎉</div>
      <h2 class="text-3xl font-bold text-white mb-2">{plan.message}</h2>
      <p class="text-green-300">Take a break or start something new.</p>
    </div>
  {:else}
    <!-- Current Task -->
    <div class="bg-gradient-to-br from-blue-900/30 to-purple-900/30 border border-blue-700/50 rounded-2xl p-8 mb-6">
      <div class="text-center mb-6">
        <div class="text-sm text-blue-300 mb-2">YOUR FOCUS RIGHT NOW</div>
        <h1 class="text-3xl font-bold text-white mb-4">{currentTask.action}</h1>
        
        <div class="flex items-center justify-center gap-6 text-sm text-slate-300">
          <span class="flex items-center gap-2">
            ⏱️ ~{currentTask.duration}m
          </span>
          <span class="flex items-center gap-2">
            📍 {currentTask.domain.split('/')[1]}
          </span>
          {#if currentTask.suggested_time}
            <span class="flex items-center gap-2">
              🕐 {currentTask.suggested_time}
            </span>
          {/if}
        </div>
      </div>
      
      <div class="flex gap-3 justify-center">
        <button
          on:click={() => completeTask(currentTask.id)}
          class="px-8 py-4 bg-green-600 hover:bg-green-700 text-white rounded-xl font-semibold text-lg transition-all transform hover:scale-105 shadow-lg"
        >
          ✓ Done
        </button>
        <button
          on:click={() => currentIndex++}
          class="px-6 py-4 bg-slate-700 hover:bg-slate-600 text-white rounded-xl font-medium transition-all"
        >
          Skip for now
        </button>
      </div>
    </div>
    
    <!-- Upcoming Tasks -->
    {#if plan.upcoming && plan.upcoming.length > 0}
      <div class="bg-slate-800/30 border border-slate-700 rounded-xl p-6">
        <h3 class="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-wide">Up Next</h3>
        <div class="space-y-3">
          {#each plan.upcoming.slice(currentIndex > 0 ? currentIndex - 1 : 0, currentIndex + 3) as task, i}
            <div class="flex items-center gap-3 text-slate-300 py-2">
              <div class="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs">
                {i + 1}
              </div>
              <div class="flex-1">
                <div class="font-medium">{task.action}</div>
                <div class="text-xs text-slate-500">{task.suggested_time} · ~{task.duration}m</div>
              </div>
            </div>
          {/each}
        </div>
      </div>
      
      <div class="text-center mt-6 text-sm text-slate-400">
        {plan.message}
      </div>
    {/if}
  {/if}
</div>

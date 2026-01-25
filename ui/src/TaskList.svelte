<script>
  import { onMount } from 'svelte';
  
  let tasks = [];
  let loading = true;
  
  const priorityColors = {
    'high': 'bg-red-500',
    'medium': 'bg-amber-500',
    'low': 'bg-blue-500'
  };
  
  const domainColors = {
    'work/marriott': 'bg-blue-600',
    'work/mansour': 'bg-green-600',
    'personal': 'bg-purple-600',
    'learning': 'bg-amber-600',
    'admin': 'bg-gray-600'
  };
  
  onMount(async () => {
    await loadTasks();
  });
  
  async function loadTasks() {
    loading = true;
    const res = await fetch('/api/tasks?status=open');
    tasks = await res.json();
    loading = false;
  }
</script>

<div class="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
  <h2 class="text-xl font-bold text-white mb-4">Tasks</h2>
  
  {#if loading}
    <div class="text-slate-400 text-center py-8">Loading tasks...</div>
  {:else if tasks.length === 0}
    <div class="text-slate-400 text-center py-8">No tasks yet</div>
  {:else}
    <div class="space-y-3">
      {#each tasks as task (task.id)}
        <div class="bg-slate-700/50 rounded-lg p-4 border border-slate-600">
          <div class="flex items-start gap-3">
            <input type="checkbox" class="mt-1" />
            
            <div class="flex-1">
              <p class="text-white font-medium">{task.action}</p>
              <p class="text-slate-400 text-sm mt-1">{task.text}</p>
              
              <div class="flex items-center gap-2 mt-2">
                <span class="{priorityColors[task.priority]} text-white text-xs px-2 py-0.5 rounded">
                  {task.priority}
                </span>
                
                {#if task.estimated_duration_minutes}
                  <span class="text-slate-400 text-xs">
                    ~{task.estimated_duration_minutes}m
                  </span>
                {/if}
                
                <span class="text-slate-500 text-xs">
                  {task.domain.split('/')[1]}
                </span>
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

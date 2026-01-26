<script>
  import { onMount } from 'svelte';
  
  export let domain = 'work/marriott';
  
  let hierarchy = null;
  let loading = true;
  let expandedProjects = {};
  let showAddProject = false;
  let newProject = { name: '', description: '', keywords: '' };
  let suggestions = [];
  
  onMount(async () => {
    await loadHierarchy();
    await checkValidation();
  });
  
  async function loadHierarchy() {
    loading = true;
    const res = await fetch(`/api/hierarchy/${encodeURIComponent(domain)}`);
    hierarchy = await res.json();
    
    // Expand all by default
    hierarchy.projects.forEach(p => expandedProjects[p.id] = true);
    loading = false;
  }
  
  async function checkValidation() {
    const res = await fetch(`/api/projects/validate/${encodeURIComponent(domain)}`);
    const data = await res.json();
    suggestions = data.suggestions || [];
  }
  
  async function createProject() {
    if (!newProject.name) return;
    
    await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...newProject, domain })
    });
    
    newProject = { name: '', description: '', keywords: '' };
    showAddProject = false;
    await loadHierarchy();
  }
  
  async function assignToProject(taskId, projectId) {
    await fetch(`/api/tasks/${taskId}/assign-project`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId })
    });
    await loadHierarchy();
  }
  
  async function acceptSuggestion(suggestion) {
    await assignToProject(suggestion.task_id, suggestion.suggested_project_id);
    suggestions = suggestions.filter(s => s.task_id !== suggestion.task_id);
  }
  
  function toggleProject(id) {
    expandedProjects[id] = !expandedProjects[id];
    expandedProjects = expandedProjects;
  }
  
  const priorityDots = {
    high: 'bg-red-500',
    medium: 'bg-amber-500',
    low: 'bg-blue-500'
  };
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-white">{domain.split('/')[1] || domain}</h2>
    <button
      on:click={() => showAddProject = true}
      class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm"
    >
      + Add Project
    </button>
  </div>
  
  <!-- Reassignment Suggestions -->
  {#if suggestions.length > 0}
    <div class="bg-amber-900/30 border border-amber-600/50 rounded-xl p-4">
      <h3 class="text-sm font-semibold text-amber-400 mb-3">🔄 Suggested Reassignments</h3>
      <div class="space-y-2">
        {#each suggestions as s}
          <div class="flex items-center justify-between bg-slate-800/50 rounded-lg p-3">
            <div class="flex-1">
              <div class="text-white text-sm">{s.task_action}</div>
              <div class="text-xs text-slate-400">
                {s.current_project || 'Unassigned'} → <span class="text-green-400">{s.suggested_project}</span>
                <span class="text-slate-500">({Math.round(s.confidence * 100)}% confident)</span>
              </div>
            </div>
            <div class="flex gap-2">
              <button
                on:click={() => acceptSuggestion(s)}
                class="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-xs"
              >
                Accept
              </button>
              <button
                on:click={() => suggestions = suggestions.filter(x => x.task_id !== s.task_id)}
                class="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-white rounded text-xs"
              >
                Dismiss
              </button>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}
  
  <!-- Add Project Modal -->
  {#if showAddProject}
    <div class="bg-slate-800 border border-slate-600 rounded-xl p-6">
      <h3 class="text-lg font-semibold text-white mb-4">New Project</h3>
      <div class="space-y-4">
        <div>
          <label class="block text-sm text-slate-400 mb-1">Name</label>
          <input
            bind:value={newProject.name}
            placeholder="e.g., ECMP AI"
            class="w-full bg-slate-700 text-white px-3 py-2 rounded-lg border border-slate-600"
          />
        </div>
        <div>
          <label class="block text-sm text-slate-400 mb-1">Description</label>
          <input
            bind:value={newProject.description}
            placeholder="What is this project about?"
            class="w-full bg-slate-700 text-white px-3 py-2 rounded-lg border border-slate-600"
          />
        </div>
        <div>
          <label class="block text-sm text-slate-400 mb-1">Keywords (comma separated)</label>
          <input
            bind:value={newProject.keywords}
            placeholder="RAG, AI, intent, TIP"
            class="w-full bg-slate-700 text-white px-3 py-2 rounded-lg border border-slate-600"
          />
        </div>
        <div class="flex gap-3">
          <button
            on:click={createProject}
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
          >
            Create
          </button>
          <button
            on:click={() => showAddProject = false}
            class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  {/if}
  
  {#if loading}
    <div class="text-slate-400">Loading...</div>
  {:else if hierarchy}
    <!-- Projects -->
    <div class="space-y-4">
      {#each hierarchy.projects as project}
        <div class="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <!-- Project Header -->
          <button
            on:click={() => toggleProject(project.id)}
            class="w-full flex items-center justify-between p-4 hover:bg-slate-800/70 transition-colors"
          >
            <div class="flex items-center gap-3">
              <span class="text-lg">{expandedProjects[project.id] ? '▼' : '▶'}</span>
              <div class="text-left">
                <h3 class="text-lg font-semibold text-white">{project.name}</h3>
                {#if project.description}
                  <p class="text-sm text-slate-400">{project.description}</p>
                {/if}
              </div>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-sm text-slate-400">{project.tasks?.length || 0} tasks</span>
            </div>
          </button>
          
          <!-- Tasks -->
          {#if expandedProjects[project.id] && project.tasks?.length > 0}
            <div class="border-t border-slate-700 p-4 space-y-2">
              {#each project.tasks as task}
                <div class="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-700/50">
                  <span class="w-2 h-2 rounded-full {priorityDots[task.priority]}"></span>
                  <div class="flex-1">
                    <div class="text-white text-sm">{task.action}</div>
                    {#if task.text && task.text !== task.action}
                      <div class="text-xs text-slate-500 truncate">{task.text}</div>
                    {/if}
                  </div>
                  {#if task.estimated_duration_minutes}
                    <span class="text-xs text-slate-500">{task.estimated_duration_minutes}m</span>
                  {/if}
                </div>
              {/each}
            </div>
          {:else if expandedProjects[project.id]}
            <div class="border-t border-slate-700 p-4 text-slate-500 text-sm">
              No tasks in this project
            </div>
          {/if}
        </div>
      {/each}
    </div>
    
    <!-- Unassigned Tasks -->
    {#if hierarchy.unassigned_tasks?.length > 0}
      <div class="bg-slate-800/30 border border-dashed border-slate-600 rounded-xl p-4">
        <h3 class="text-sm font-semibold text-slate-400 mb-3">📋 Unassigned Tasks</h3>
        <div class="space-y-2">
          {#each hierarchy.unassigned_tasks as task}
            <div class="flex items-center gap-3 p-2 bg-slate-800/50 rounded-lg">
              <span class="w-2 h-2 rounded-full {priorityDots[task.priority]}"></span>
              <div class="flex-1 text-white text-sm">{task.action}</div>
              <select
                on:change={(e) => assignToProject(task.id, parseInt(e.target.value))}
                class="bg-slate-700 text-white text-xs px-2 py-1 rounded border border-slate-600"
              >
                <option value="">Assign to...</option>
                {#each hierarchy.projects as p}
                  <option value={p.id}>{p.name}</option>
                {/each}
              </select>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>

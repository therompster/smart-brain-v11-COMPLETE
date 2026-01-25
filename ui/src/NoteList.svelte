<script>
  import { createEventDispatcher } from 'svelte';
  
  export let notes = [];
  
  const dispatch = createEventDispatcher();
  
  const domainColors = {
    'work/marriott': 'bg-blue-600',
    'work/mansour': 'bg-green-600',
    'personal': 'bg-purple-600',
    'learning': 'bg-amber-600',
    'admin': 'bg-gray-600'
  };
  
  const domainLabels = {
    'work/marriott': 'Marriott',
    'work/mansour': 'Konstellate',
    'personal': 'Personal',
    'learning': 'Learning',
    'admin': 'Admin'
  };
  
  function formatDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  }
  
  function truncate(text, length = 150) {
    if (text.length <= length) return text;
    return text.slice(0, length) + '...';
  }
</script>

<div class="grid gap-4">
  {#if notes.length === 0}
    <div class="text-center py-16">
      <div class="text-6xl mb-4">📝</div>
      <h2 class="text-2xl font-bold text-white mb-2">No notes yet</h2>
      <p class="text-slate-400 mb-6">Start writing to build your second brain</p>
    </div>
  {:else}
    {#each notes as note (note.id)}
      <div
        on:click={() => dispatch('edit', note)}
        class="bg-slate-800/50 border border-slate-700 rounded-xl p-5 hover:border-slate-600 hover:bg-slate-800/70 transition-all cursor-pointer group"
      >
        <div class="flex items-start justify-between mb-3">
          <h3 class="text-xl font-semibold text-white group-hover:text-blue-400 transition-colors">
            {note.title}
          </h3>
          
          <div class="flex items-center gap-2">
            <span class="{domainColors[note.domain]} text-white text-xs px-2 py-1 rounded font-medium">
              {domainLabels[note.domain]}
            </span>
            <span class="text-slate-500 text-xs px-2 py-1 bg-slate-700/50 rounded">
              {note.type}
            </span>
          </div>
        </div>
        
        <p class="text-slate-300 text-sm mb-3 leading-relaxed">
          {truncate(note.content)}
        </p>
        
        <div class="flex items-center gap-4 text-xs text-slate-500">
          <span>{formatDate(note.created_at)}</span>
          <span>·</span>
          <span>{note.content.length} chars</span>
        </div>
      </div>
    {/each}
  {/if}
</div>

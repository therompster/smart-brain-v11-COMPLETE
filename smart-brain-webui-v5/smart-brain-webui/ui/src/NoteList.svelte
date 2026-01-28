<script>
  import { createEventDispatcher } from 'svelte';
  export let notes = [];
  const dispatch = createEventDispatcher();
  
  function formatDate(dateStr) {
    const date = new Date(dateStr);
    const days = Math.floor((new Date() - date) / (1000 * 60 * 60 * 24));
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  }
</script>

<div class="grid gap-4">
  {#if notes.length === 0}
    <div class="text-center py-16">
      <div class="text-6xl mb-4">📝</div>
      <h2 class="text-2xl font-bold text-white mb-2">No notes yet</h2>
      <p class="text-slate-400">Start writing to build your second brain</p>
    </div>
  {:else}
    {#each notes as note}
      <div on:click={() => dispatch('edit', note)} on:keydown={e => e.key === 'Enter' && dispatch('edit', note)}
        role="button" tabindex="0"
        class="bg-slate-800/50 border border-slate-700 rounded-xl p-5 hover:border-slate-600 cursor-pointer">
        <div class="flex items-start justify-between mb-3">
          <h3 class="text-xl font-semibold text-white hover:text-blue-400">{note.title}</h3>
          <span class="text-slate-500 text-xs px-2 py-1 bg-slate-700/50 rounded">{note.type}</span>
        </div>
        <p class="text-slate-300 text-sm mb-3">{note.content.slice(0, 150)}...</p>
        <div class="text-xs text-slate-500">{formatDate(note.created_at)}</div>
      </div>
    {/each}
  {/if}
</div>

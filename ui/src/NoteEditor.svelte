<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import { marked } from 'marked';
  
  export let note = null;
  
  const dispatch = createEventDispatcher();
  
  let title = note?.title || '';
  let content = note?.content || '';
  let selectedDomain = note?.domain || '';
  let selectedType = note?.type || 'Note';
  
  let processing = false;
  let saving = false;
  let suggestions = null;
  let showPreview = false;
  let domains = [];
  
  const types = ['Project', 'Area', 'Note'];
  
  let processTimeout;
  
  onMount(async () => {
    await loadDomains();
  });
  
  async function loadDomains() {
    const res = await fetch('/api/domains');
    const data = await res.json();
    domains = data.domains.map(d => ({
      value: d.path,
      label: d.name,
      color: `bg-${d.color}-600`
    }));
  }
  
  $: if (content && !note) {
    clearTimeout(processTimeout);
    processTimeout = setTimeout(processContent, 1000);
  }
  
  $: preview = content ? marked(content) : '';
  
  async function processContent() {
    if (!content || content.length < 10) return;
    
    processing = true;
    try {
      const res = await fetch('/api/notes/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, title })
      });
      
      suggestions = await res.json();
      
      if (!title) title = suggestions.suggested_title;
      selectedDomain = suggestions.suggested_domain;
      selectedType = suggestions.suggested_type;
      
    } catch (err) {
      console.error('Processing failed:', err);
    } finally {
      processing = false;
    }
  }
  
  async function save() {
    if (!title || !content || !selectedDomain) {
      alert('Title, content, and domain are required');
      return;
    }
    
    saving = true;
    try {
      const res = await fetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          title, 
          content, 
          domain: selectedDomain, 
          type: selectedType 
        })
      });
      
      if (res.ok) {
        dispatch('saved');
      } else {
        alert('Save failed');
      }
    } catch (err) {
      console.error('Save failed:', err);
      alert('Save failed');
    } finally {
      saving = false;
    }
  }
  
  function cancel() {
    dispatch('cancel');
  }
</script>

<div class="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
  <!-- Top bar -->
  <div class="border-b border-slate-700 bg-slate-900/50 p-4 flex items-center justify-between">
    <input
      type="text"
      bind:value={title}
      placeholder="Note title..."
      disabled={saving}
      class="flex-1 bg-transparent text-2xl font-bold text-white placeholder-slate-500 outline-none disabled:opacity-50"
    />
    
    {#if processing}
      <div class="text-slate-400 text-sm flex items-center gap-2">
        <div class="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        Processing...
      </div>
    {/if}
  </div>
  
  <!-- Metadata -->
  <div class="border-b border-slate-700 bg-slate-900/30 p-4 flex gap-4 flex-wrap">
    <!-- Domain -->
    <div>
      <label class="block text-xs text-slate-400 mb-1">Domain</label>
      <select
        bind:value={selectedDomain}
        disabled={saving}
        class="bg-slate-700 text-white px-3 py-1.5 rounded-lg border border-slate-600 focus:border-blue-500 outline-none disabled:opacity-50"
      >
        <option value="">Select domain...</option>
        {#each domains as d}
          <option value={d.value}>{d.label}</option>
        {/each}
      </select>
    </div>
    
    <!-- Type -->
    <div>
      <label class="block text-xs text-slate-400 mb-1">Type</label>
      <select
        bind:value={selectedType}
        disabled={saving}
        class="bg-slate-700 text-white px-3 py-1.5 rounded-lg border border-slate-600 focus:border-blue-500 outline-none disabled:opacity-50"
      >
        {#each types as t}
          <option value={t}>{t}</option>
        {/each}
      </select>
    </div>
    
    <!-- Suggestions -->
    {#if suggestions}
      <div class="flex items-end gap-2">
        <span class="text-xs text-slate-400">AI suggests: </span>
        <span class="text-sm text-blue-400">{domains.find(d => d.value === suggestions.suggested_domain)?.label || suggestions.suggested_domain}</span>
        {#if suggestions.confidence < 0.7}
          <span class="text-xs text-amber-400">(uncertain)</span>
        {/if}
      </div>
    {/if}
    
    <!-- Preview toggle -->
    <div class="ml-auto flex items-end">
      <button
        on:click={() => showPreview = !showPreview}
        disabled={saving}
        class="text-sm text-slate-400 hover:text-white transition-colors disabled:opacity-50"
      >
        {showPreview ? 'Edit' : 'Preview'}
      </button>
    </div>
  </div>
  
  <!-- Editor / Preview -->
  <div class="flex" style="height: calc(100vh - 320px);">
    {#if showPreview}
      <div class="flex-1 p-6 overflow-auto prose prose-invert max-w-none">
        {@html preview}
      </div>
    {:else}
      <textarea
        bind:value={content}
        disabled={saving}
        placeholder="Start writing..."
        class="flex-1 bg-transparent text-slate-100 p-6 outline-none resize-none font-mono text-sm leading-relaxed disabled:opacity-50"
      />
    {/if}
  </div>
  
  <!-- Bottom bar -->
  <div class="border-t border-slate-700 bg-slate-900/50 p-4 flex items-center justify-between">
    <div class="text-sm text-slate-400">
      {content.length} chars
      {#if suggestions?.keywords?.length}
        · Keywords: {suggestions.keywords.join(', ')}
      {/if}
    </div>
    
    <div class="flex gap-3">
      <button
        on:click={cancel}
        disabled={saving}
        class="px-4 py-2 text-slate-300 hover:text-white transition-colors disabled:opacity-50"
      >
        Cancel
      </button>
      <button
        on:click={save}
        disabled={saving}
        class="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
      >
        {#if saving}
          <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          Saving...
        {:else}
          Save Note
        {/if}
      </button>
    </div>
  </div>
</div>

<style>
  textarea::placeholder {
    @apply text-slate-600;
  }
</style>
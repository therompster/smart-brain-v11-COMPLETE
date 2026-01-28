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
  
  // Clarification flow
  let clarifications = [];
  let clarificationAnswers = {};
  let savedNoteId = null;
  let showClarifications = false;
  
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
        const result = await res.json();
        
        // Check if clarifications needed
        if (result.clarifications_needed && result.clarifications_needed.length > 0) {
          clarifications = result.clarifications_needed;
          savedNoteId = result.note_id;
          showClarifications = true;
          saving = false;
        } else {
          dispatch('saved');
        }
      } else {
        alert('Save failed');
      }
    } catch (err) {
      console.error('Save failed:', err);
      alert('Save failed');
    } finally {
      if (!showClarifications) saving = false;
    }
  }
  
  async function submitClarifications() {
    saving = true;
    try {
      await fetch(`/api/notes/${savedNoteId}/clarify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: savedNoteId,
          answers: clarificationAnswers
        })
      });
      
      dispatch('saved');
    } catch (err) {
      console.error('Clarification failed:', err);
      alert('Failed to save clarifications');
    } finally {
      saving = false;
    }
  }
  
  function skipClarifications() {
    submitClarifications();
  }
  
  function cancel() {
    dispatch('cancel');
  }
</script>

{#if showClarifications}
  <!-- Clarification Flow -->
  <div class="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
    <div class="border-b border-slate-700 bg-slate-900/50 p-6">
      <div class="flex items-center gap-3 mb-2">
        <div class="w-10 h-10 bg-amber-600 rounded-full flex items-center justify-center">
          <span class="text-xl">🤔</span>
        </div>
        <div>
          <h2 class="text-xl font-bold text-white">Quick clarifications</h2>
          <p class="text-slate-400 text-sm">Some tasks need more context so future-you knows what they mean</p>
        </div>
      </div>
    </div>
    
    <div class="p-6 space-y-6 max-h-[60vh] overflow-y-auto">
      {#each clarifications as c, i}
        <div class="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
          <div class="mb-3">
            <div class="text-slate-400 text-sm mb-1">Task:</div>
            <div class="text-white font-medium">{c.action}</div>
            {#if c.original_text && c.original_text !== c.action}
              <div class="text-slate-500 text-sm mt-1">From: "{c.original_text}"</div>
            {/if}
          </div>
          
          <div class="mb-3">
            <label class="text-amber-400 text-sm font-medium">{c.question}</label>
          </div>
          
          <textarea
            bind:value={clarificationAnswers[c.task_index]}
            placeholder="Type your answer..."
            rows="2"
            class="w-full bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-600 focus:border-amber-500 outline-none resize-none"
          ></textarea>
        </div>
      {/each}
    </div>
    
    <div class="border-t border-slate-700 bg-slate-900/50 p-4 flex items-center justify-between">
      <div class="text-sm text-slate-400">
        {Object.keys(clarificationAnswers).filter(k => clarificationAnswers[k]).length} of {clarifications.length} answered
      </div>
      
      <div class="flex gap-3">
        <button
          on:click={skipClarifications}
          class="px-4 py-2 text-slate-300 hover:text-white transition-colors"
        >
          Skip all
        </button>
        <button
          on:click={submitClarifications}
          disabled={saving}
          class="px-6 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
        >
          {#if saving}
            Saving...
          {:else}
            Save Tasks
          {/if}
        </button>
      </div>
    </div>
  </div>
  
{:else}
  <!-- Normal Editor -->
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
      
      {#if suggestions}
        <div class="flex items-end gap-2">
          <span class="text-xs text-slate-400">AI suggests: </span>
          <span class="text-sm text-blue-400">{domains.find(d => d.value === suggestions.suggested_domain)?.label || suggestions.suggested_domain}</span>
        </div>
      {/if}
      
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
{/if}

<style>
  textarea::placeholder {
    @apply text-slate-600;
  }
</style>

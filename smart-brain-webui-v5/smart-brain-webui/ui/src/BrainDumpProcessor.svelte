<script>
  import { createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  export let initialContent = '';
  export let domain = 'work/marriott';
  
  let content = initialContent;
  let analyzing = false;
  let saving = false;
  let result = null;
  let step = 'input'; // input, review, clarify, consolidate, done
  let clarifications = {};
  let selectedProjects = [];
  let projectSuggestions = [];
  let consolidations = [];
  let hierarchySuggestions = [];
  let selectedConsolidations = [];
  let selectedHierarchies = [];
  
  // Item type configuration
  const itemTypeConfig = {
    task: { icon: '✅', color: 'blue', label: 'Task' },
    note: { icon: '📝', color: 'slate', label: 'Note' },
    idea: { icon: '💡', color: 'yellow', label: 'Idea' },
    question: { icon: '❓', color: 'purple', label: 'Question' },
    decision: { icon: '⚖️', color: 'green', label: 'Decision' },
    reference: { icon: '🔗', color: 'cyan', label: 'Reference' },
    project: { icon: '📁', color: 'indigo', label: 'Project' }
  };
  
  async function analyze() {
    if (!content.trim()) return;
    
    analyzing = true;
    try {
      // Get analysis
      const res = await fetch('/api/brain-dump/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, domain })
      });
      result = await res.json();
      
      // Get project suggestions
      const projRes = await fetch('/api/brain-dump/suggest-projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, domain })
      });
      const projData = await projRes.json();
      projectSuggestions = projData.suggestions || [];
      
      // Store consolidations from result
      consolidations = result.project_consolidations || [];
      hierarchySuggestions = result.project_hierarchy || [];
      
      // If there are ambiguous items, go to clarify step
      if (result.ambiguous_items?.length > 0) {
        step = 'clarify';
      } else if (consolidations.length > 0 || hierarchySuggestions.length > 0) {
        step = 'consolidate';
      } else {
        step = 'review';
      }
    } catch (err) {
      console.error('Analysis failed:', err);
      alert('Failed to analyze brain dump');
    } finally {
      analyzing = false;
    }
  }
  
  function skipClarification() {
    if (consolidations.length > 0 || hierarchySuggestions.length > 0) {
      step = 'consolidate';
    } else {
      step = 'review';
    }
  }
  
  function submitClarifications() {
    if (consolidations.length > 0 || hierarchySuggestions.length > 0) {
      step = 'consolidate';
    } else {
      step = 'review';
    }
  }
  
  function toggleHierarchy(idx) {
    if (selectedHierarchies.includes(idx)) {
      selectedHierarchies = selectedHierarchies.filter(i => i !== idx);
    } else {
      selectedHierarchies = [...selectedHierarchies, idx];
    }
  }
  
  function skipConsolidation() {
    step = 'review';
  }
  
  function acceptConsolidations() {
    step = 'review';
  }
  
  function toggleConsolidation(index) {
    if (selectedConsolidations.includes(index)) {
      selectedConsolidations = selectedConsolidations.filter(i => i !== index);
    } else {
      selectedConsolidations = [...selectedConsolidations, index];
    }
  }
  
  async function saveAll() {
    saving = true;
    try {
      // Get selected consolidations
      const appliedConsolidations = selectedConsolidations.map(i => consolidations[i]);
      
      // Get selected hierarchies
      const appliedHierarchies = selectedHierarchies.map(i => hierarchySuggestions[i]);
      
      const res = await fetch('/api/brain-dump/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: result.items || result.tasks, // Support both new and old format
          domain,
          clarifications,
          create_projects: selectedProjects,
          consolidations: appliedConsolidations,
          hierarchies: appliedHierarchies
        })
      });
      
      const data = await res.json();
      step = 'done';
      
      setTimeout(() => {
        dispatch('saved', data);
      }, 2000);
    } catch (err) {
      console.error('Save failed:', err);
      alert('Failed to save items');
    } finally {
      saving = false;
    }
  }
  
  function toggleProject(name) {
    if (selectedProjects.includes(name)) {
      selectedProjects = selectedProjects.filter(p => p !== name);
    } else {
      selectedProjects = [...selectedProjects, name];
    }
  }
  
  const priorityColors = {
    high: 'bg-red-500/20 border-red-500 text-red-300',
    medium: 'bg-amber-500/20 border-amber-500 text-amber-300',
    low: 'bg-blue-500/20 border-blue-500 text-blue-300'
  };
  
  // Computed: items grouped by type
  $: itemsByType = (result?.items_by_type || groupItemsByType(result?.items || result?.tasks || []));
  
  function groupItemsByType(items) {
    const grouped = {};
    for (const item of items) {
      const type = item.item_type || 'task';
      if (!grouped[type]) grouped[type] = [];
      grouped[type].push(item);
    }
    return grouped;
  }
  
  $: totalItems = Object.values(itemsByType).reduce((sum, arr) => sum + arr.length, 0);
</script>

<div class="max-w-4xl mx-auto">
  {#if step === 'input'}
    <!-- Input Step -->
    <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-xl font-bold text-white">Brain Dump Processor</h2>
          <p class="text-sm text-slate-400">Paste your messy notes - I'll extract tasks, notes, ideas & more</p>
        </div>
        <select
          bind:value={domain}
          class="bg-slate-700 text-white px-3 py-2 rounded-lg border border-slate-600"
        >
          <option value="work/marriott">Marriott</option>
          <option value="work/konstellate">Konstellate</option>
          <option value="personal">Personal</option>
        </select>
      </div>
      
      <textarea
        bind:value={content}
        placeholder="Paste your brain dump here...

Examples of what I can handle:
- GREG - system mapping, intent stuff
- TODO for driftguard: bank setup, stock checks
- TIP AI: high level diagram, embeddings
- ? how do we handle caching for templates
- DECIDED: use AEM for template storage
- idea: could add voice notes later
- ref: https://docs.example.com/api"
        rows="16"
        class="w-full bg-slate-900 text-white p-4 rounded-lg border border-slate-600 
               focus:border-blue-500 outline-none font-mono text-sm resize-none"
      ></textarea>
      
      <div class="flex items-center justify-between mt-4">
        <div class="text-sm text-slate-400">
          {content.split('\n').filter(l => l.trim()).length} lines
        </div>
        <button
          on:click={analyze}
          disabled={analyzing || !content.trim()}
          class="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 
                 disabled:text-slate-500 text-white rounded-lg font-semibold 
                 transition-all flex items-center gap-2"
        >
          {#if analyzing}
            <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            Analyzing...
          {:else}
            🧠 Process Brain Dump
          {/if}
        </button>
      </div>
    </div>
    
  {:else if step === 'clarify'}
    <!-- Clarification Step -->
    <div class="bg-amber-900/20 border border-amber-600/50 rounded-xl p-6 mb-6">
      <div class="flex items-center gap-3 mb-4">
        <span class="text-2xl">🤔</span>
        <div>
          <h2 class="text-xl font-bold text-white">Some items need clarification</h2>
          <p class="text-sm text-amber-300">These are too vague - future-you won't know what to do</p>
        </div>
      </div>
      
      <div class="space-y-4">
        {#each result.ambiguous_items as item, i}
          <div class="bg-slate-800/70 rounded-lg p-4">
            <div class="flex items-start gap-3">
              <span class="text-amber-400 mt-1">⚠️</span>
              <div class="flex-1">
                <div class="text-white font-medium mb-1">"{item.text}"</div>
                <div class="text-sm text-slate-400 mb-3">{item.question}</div>
                
                {#if item.possible_interpretations?.length}
                  <div class="text-xs text-slate-500 mb-2">
                    Possible meanings: {item.possible_interpretations.join(' | ')}
                  </div>
                {/if}
                
                {#if item.suggested_type}
                  <div class="text-xs text-blue-400 mb-2">
                    Suggested type: {itemTypeConfig[item.suggested_type]?.icon} {itemTypeConfig[item.suggested_type]?.label}
                  </div>
                {/if}
                
                <input
                  type="text"
                  bind:value={clarifications[item.text]}
                  placeholder="What did you mean by this?"
                  class="w-full bg-slate-700 text-white px-3 py-2 rounded border 
                         border-slate-600 focus:border-amber-500 outline-none text-sm"
                />
              </div>
            </div>
          </div>
        {/each}
      </div>
      
      <div class="flex justify-end gap-3 mt-6">
        <button
          on:click={skipClarification}
          class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
        >
          Skip (keep vague)
        </button>
        <button
          on:click={submitClarifications}
          class="px-6 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-medium"
        >
          Continue with clarifications
        </button>
      </div>
    </div>
    
  {:else if step === 'consolidate'}
    <!-- Project Consolidation Step -->
    <div class="bg-indigo-900/20 border border-indigo-600/50 rounded-xl p-6 mb-6">
      <div class="flex items-center gap-3 mb-4">
        <span class="text-2xl">🔄</span>
        <div>
          <h2 class="text-xl font-bold text-white">Project Cleanup Suggestions</h2>
          <p class="text-sm text-indigo-300">Review these suggestions for organizing your projects</p>
        </div>
      </div>
      
      <!-- Consolidations (merge duplicates) -->
      {#if consolidations.length > 0}
        <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">Merge Duplicates</h3>
        <div class="space-y-4 mb-6">
          {#each consolidations as cons, i}
            <label class="block bg-slate-800/70 rounded-lg p-4 cursor-pointer hover:bg-slate-800">
              <div class="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={selectedConsolidations.includes(i)}
                  on:change={() => toggleConsolidation(i)}
                  class="mt-1"
                />
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-2">
                    <span class="text-xs px-2 py-0.5 rounded bg-indigo-600/30 text-indigo-300 capitalize">
                      {cons.consolidation_type}
                    </span>
                    <span class="text-xs text-slate-500">{Math.round(cons.confidence * 100)}% confident</span>
                  </div>
                  
                  <div class="text-white font-medium mb-1">
                    {#if cons.consolidation_type === 'merge'}
                      Merge: {cons.variants.join(', ')} → <span class="text-green-400">{cons.suggested_name}</span>
                    {:else if cons.consolidation_type === 'rename'}
                      Rename: {cons.variants[0]} → <span class="text-green-400">{cons.suggested_name}</span>
                    {:else}
                      {cons.variants.join(', ')} → <span class="text-green-400">{cons.suggested_name}</span>
                    {/if}
                  </div>
                  
                  <div class="text-sm text-slate-400">{cons.reason}</div>
                  
                  {#if cons.suggested_description}
                    <div class="text-xs text-slate-500 mt-1">
                      Description: {cons.suggested_description}
                    </div>
                  {/if}
                </div>
              </div>
            </label>
          {/each}
        </div>
      {/if}
      
      <!-- Hierarchy Suggestions (parent-child relationships) -->
      {#if hierarchySuggestions.length > 0}
        <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">Project Hierarchy</h3>
        <p class="text-xs text-slate-500 mb-3">These projects might belong under a parent project:</p>
        <div class="space-y-4 mb-6">
          {#each hierarchySuggestions as hier, i}
            <label class="block bg-slate-800/70 rounded-lg p-4 cursor-pointer hover:bg-slate-800">
              <div class="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={selectedHierarchies.includes(i)}
                  on:change={() => toggleHierarchy(i)}
                  class="mt-1"
                />
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-2">
                    <span class="text-xs px-2 py-0.5 rounded bg-purple-600/30 text-purple-300">
                      nest under
                    </span>
                    <span class="text-xs text-slate-500">{Math.round(hier.confidence * 100)}% confident</span>
                  </div>
                  
                  <div class="text-white font-medium mb-1">
                    <span class="text-amber-400">{hier.child_project}</span> → under → <span class="text-green-400">{hier.parent_project}</span>
                  </div>
                  
                  <div class="text-sm text-slate-400">{hier.reason}</div>
                </div>
              </div>
            </label>
          {/each}
        </div>
      {/if}
      
      <div class="flex justify-end gap-3 mt-6">
        <button
          on:click={skipConsolidation}
          class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
        >
          Skip cleanup
        </button>
        <button
          on:click={acceptConsolidations}
          class="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium"
        >
          Apply {selectedConsolidations.length + selectedHierarchies.length} changes
        </button>
      </div>
    </div>
    
  {:else if step === 'review'}
    <!-- Review Step -->
    <div class="space-y-6">
      <!-- Summary -->
      <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <h2 class="text-xl font-bold text-white mb-4">📊 Analysis Summary</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          {#each Object.entries(itemsByType) as [type, items]}
            <div class="bg-slate-700/50 rounded-lg p-3 text-center">
              <div class="text-2xl mb-1">{itemTypeConfig[type]?.icon || '📄'}</div>
              <div class="text-2xl font-bold text-white">{items.length}</div>
              <div class="text-xs text-slate-400">{itemTypeConfig[type]?.label || type}s</div>
            </div>
          {/each}
          <div class="bg-slate-700/50 rounded-lg p-3 text-center">
            <div class="text-2xl mb-1">👤</div>
            <div class="text-2xl font-bold text-green-400">{result.people_detected?.length || 0}</div>
            <div class="text-xs text-slate-400">People</div>
          </div>
          <div class="bg-slate-700/50 rounded-lg p-3 text-center">
            <div class="text-2xl mb-1">⚠️</div>
            <div class="text-2xl font-bold text-amber-400">{result.ambiguous_items?.length || 0}</div>
            <div class="text-xs text-slate-400">Ambiguous</div>
          </div>
        </div>
      </div>
      
      <!-- Project Suggestions -->
      {#if projectSuggestions.length > 0}
        <div class="bg-purple-900/20 border border-purple-600/50 rounded-xl p-6">
          <h3 class="text-lg font-semibold text-white mb-3">🆕 Suggested New Projects</h3>
          <div class="space-y-2">
            {#each projectSuggestions as proj}
              <label class="flex items-start gap-3 p-3 bg-slate-800/50 rounded-lg cursor-pointer hover:bg-slate-800">
                <input
                  type="checkbox"
                  checked={selectedProjects.includes(proj.name)}
                  on:change={() => toggleProject(proj.name)}
                  class="mt-1"
                />
                <div class="flex-1">
                  <div class="text-white font-medium">{proj.name}</div>
                  <div class="text-sm text-slate-400">{proj.description}</div>
                  <div class="text-xs text-purple-400 mt-1">
                    Keywords: {proj.keywords?.join(', ') || 'none'}
                  </div>
                </div>
                <div class="text-xs text-slate-500">{Math.round(proj.confidence * 100)}%</div>
              </label>
            {/each}
          </div>
        </div>
      {/if}
      
      <!-- Detected Context -->
      {#if result.people_detected?.length || result.projects_detected?.length}
        <div class="flex gap-4">
          {#if result.people_detected?.length}
            <div class="flex-1 bg-green-900/20 border border-green-600/50 rounded-xl p-4">
              <h4 class="text-sm font-semibold text-green-400 mb-2">👤 People Detected</h4>
              <div class="flex flex-wrap gap-2">
                {#each result.people_detected as person}
                  <span class="px-2 py-1 bg-green-600/30 text-green-300 rounded text-sm">{person}</span>
                {/each}
              </div>
            </div>
          {/if}
          {#if result.projects_detected?.length}
            <div class="flex-1 bg-purple-900/20 border border-purple-600/50 rounded-xl p-4">
              <h4 class="text-sm font-semibold text-purple-400 mb-2">📁 Projects Detected</h4>
              <div class="flex flex-wrap gap-2">
                {#each result.projects_detected as proj}
                  <span class="px-2 py-1 bg-purple-600/30 text-purple-300 rounded text-sm">{proj}</span>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}
      
      <!-- Items by Type -->
      {#each Object.entries(itemsByType) as [type, items]}
        {#if items.length > 0}
          <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>{itemTypeConfig[type]?.icon || '📄'}</span>
              {itemTypeConfig[type]?.label || type}s ({items.length})
            </h3>
            <div class="space-y-2 max-h-72 overflow-y-auto">
              {#each items as item}
                <div class="flex items-start gap-3 p-3 bg-slate-700/30 rounded-lg border-l-2 
                           {type === 'task' ? priorityColors[item.priority] : 'border-slate-600'}">
                  <div class="flex-1">
                    <div class="text-white font-medium">{item.action}</div>
                    {#if item.original_text && item.original_text !== item.action}
                      <div class="text-xs text-slate-500 mt-1">Original: "{item.original_text}"</div>
                    {/if}
                    <div class="flex items-center gap-3 mt-2 text-xs flex-wrap">
                      {#if item.project}
                        <span class="text-purple-400">📁 {item.project}</span>
                      {/if}
                      {#if item.person}
                        <span class="text-green-400">👤 {item.person}</span>
                      {/if}
                      {#if item.estimated_minutes && type === 'task'}
                        <span class="text-slate-500">~{item.estimated_minutes}m</span>
                      {/if}
                      {#if item.sub_items?.length}
                        <span class="text-blue-400">+{item.sub_items.length} sub-items</span>
                      {/if}
                      {#if item.tags?.length}
                        {#each item.tags as tag}
                          <span class="px-1.5 py-0.5 bg-slate-600 rounded text-slate-300">#{tag}</span>
                        {/each}
                      {/if}
                    </div>
                  </div>
                  {#if type === 'task'}
                    <span class="text-xs px-2 py-0.5 rounded capitalize {priorityColors[item.priority]}">{item.priority}</span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      {/each}
      
      <!-- Actions -->
      <div class="flex justify-between items-center">
        <button
          on:click={() => { step = 'input'; result = null; }}
          class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
        >
          ← Start Over
        </button>
        <div class="flex gap-3">
          <button
            on:click={() => dispatch('cancel')}
            class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
          >
            Cancel
          </button>
          <button
            on:click={saveAll}
            disabled={saving}
            class="px-6 py-3 bg-green-600 hover:bg-green-700 disabled:bg-slate-700 
                   text-white rounded-lg font-semibold flex items-center gap-2"
          >
            {#if saving}
              <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              Saving...
            {:else}
              ✓ Save {totalItems} Items
            {/if}
          </button>
        </div>
      </div>
    </div>
    
  {:else if step === 'done'}
    <!-- Done Step -->
    <div class="bg-green-900/20 border border-green-600/50 rounded-xl p-12 text-center">
      <div class="text-6xl mb-4">🎉</div>
      <h2 class="text-2xl font-bold text-white mb-2">Brain Dump Processed!</h2>
      <p class="text-green-300 mb-4">
        {totalItems} items saved
        {#if selectedProjects.length}
          • {selectedProjects.length} projects created
        {/if}
        {#if selectedConsolidations.length}
          • {selectedConsolidations.length} projects merged
        {/if}
        {#if selectedHierarchies.length}
          • {selectedHierarchies.length} hierarchies set
        {/if}
      </p>
      <p class="text-slate-400 text-sm">Redirecting to tasks...</p>
    </div>
  {/if}
</div>

<script>
  import { createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  export let initialContent = '';
  export let domain = 'work/marriott';
  
  let content = initialContent;
  let analyzing = false;
  let saving = false;
  let result = null;
  let step = 'input'; // input -> organize -> clarify -> review -> done
  let clarifications = {};
  let organizationChoices = {};
  let parentChoices = {}; // For modules/services: which parent?
  let defaultProjectChoice = 'inbox';
  let existingProjects = [];
  
  const itemTypeConfig = {
    task: { icon: '✅', color: 'blue', label: 'Task' },
    note: { icon: '📝', color: 'slate', label: 'Note' },
    idea: { icon: '💡', color: 'yellow', label: 'Idea' },
    question: { icon: '❓', color: 'purple', label: 'Question' },
    decision: { icon: '⚖️', color: 'green', label: 'Decision' },
    reference: { icon: '🔗', color: 'cyan', label: 'Reference' }
  };
  
  const orgTypeOptions = [
    { value: 'platform', label: '📦 Platform', description: 'Top-level, I own this' },
    { value: 'module', label: '🧱 Module', description: 'Subsystem with children' },
    { value: 'service', label: '🔧 Service', description: 'Leaf-level capability' },
    { value: 'system', label: '⚙️ System', description: 'External, I integrate with it' },
    { value: 'existing', label: '✅ Exists', description: 'Already in system' },
    { value: 'ignore', label: '🚫 Ignore', description: 'Skip this' }
  ];
  
  const typeColors = {
    platform: 'bg-indigo-600/30 text-indigo-300',
    module: 'bg-blue-600/30 text-blue-300',
    service: 'bg-green-600/30 text-green-300',
    system: 'bg-amber-600/30 text-amber-300',
    person: 'bg-pink-600/30 text-pink-300'
  };
  
  $: itemsByType = result?.items_by_type || {};
  $: totalItems = Object.values(itemsByType).flat().length;
  $: detectedOrganization = result?.detected_organization || null;
  $: typosFixed = result?.typos_fixed || [];
  $: garbageFiltered = result?.garbage_filtered || [];
  $: hierarchy = result?.project_hierarchy || [];
  
  // Get platforms/modules for parent selection
  $: availableParents = (detectedOrganization?.groups || [])
    .filter(g => ['platform', 'module'].includes(organizationChoices[g.name] || g.type))
    .map(g => g.name);
  
  async function loadExistingProjects() {
    try {
      const res = await fetch(`/api/projects?domain=${domain}`);
      const data = await res.json();
      existingProjects = data.projects || data || [];
    } catch (err) {
      existingProjects = [];
    }
  }
  
  async function analyze() {
    if (!content.trim()) return;
    
    analyzing = true;
    try {
      await loadExistingProjects();
      
      const res = await fetch('/api/brain-dump/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, domain })
      });
      result = await res.json();
      
      // Initialize choices from suggestions
      if (result.detected_organization?.groups) {
        result.detected_organization.groups.forEach(group => {
          organizationChoices[group.name] = group.suggested_as || group.type;
          if (group.parent) {
            parentChoices[group.name] = group.parent;
          }
        });
      }
      
      step = result.detected_organization?.groups?.length > 0 ? 'organize' : 
             result.ambiguous_items?.length > 0 ? 'clarify' : 'review';
    } catch (err) {
      console.error('Analysis failed:', err);
      alert('Failed to analyze brain dump');
    } finally {
      analyzing = false;
    }
  }
  
  function setOrganizationType(groupName, type) {
    organizationChoices[groupName] = type;
    organizationChoices = { ...organizationChoices };
  }
  
  function setParent(groupName, parent) {
    parentChoices[groupName] = parent;
    parentChoices = { ...parentChoices };
  }
  
  function confirmOrganization() {
    step = result.ambiguous_items?.length > 0 ? 'clarify' : 'review';
  }
  
  function skipClarification() {
    step = 'review';
  }
  
  function submitClarifications() {
    step = 'review';
  }
  
  async function save() {
    saving = true;
    try {
      // Build create list for platforms/modules/services (not systems)
      const createProjects = Object.entries(organizationChoices)
        .filter(([_, type]) => ['platform', 'module', 'service'].includes(type))
        .map(([name, _]) => name);
      
      const payload = {
        domain,
        items: result.items,
        clarifications,
        organization_choices: {
          group_assignments: organizationChoices,
          parent_assignments: parentChoices,
          default_project: defaultProjectChoice,
          create_projects: createProjects
        }
      };
      
      const res = await fetch('/api/brain-dump/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const saveResult = await res.json();
      if (saveResult.success !== false) {
        step = 'done';
      } else {
        alert('Save failed: ' + (saveResult.error || 'Unknown error'));
      }
    } catch (err) {
      alert('Failed to save items');
    } finally {
      saving = false;
    }
  }
  
  function reset() {
    content = '';
    result = null;
    step = 'input';
    clarifications = {};
    organizationChoices = {};
    parentChoices = {};
  }
  
  function close() {
    dispatch('close');
  }
</script>

<div class="max-w-4xl mx-auto p-6">
  <!-- Header -->
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-bold text-white">🧠 Brain Dump Processor</h1>
      <p class="text-slate-400 text-sm mt-1">
        {#if step === 'input'}Paste your messy notes
        {:else if step === 'organize'}Review organization
        {:else if step === 'clarify'}Clarify ambiguous items
        {:else if step === 'review'}Review & save
        {:else}Done!{/if}
      </p>
    </div>
    <button on:click={close} class="p-2 text-slate-400 hover:text-white">✕</button>
  </div>

  {#if step === 'input'}
    <div class="bg-slate-800 rounded-xl p-6">
      <textarea
        bind:value={content}
        placeholder="Paste your brain dump here..."
        rows="16"
        class="w-full bg-slate-900 text-white p-4 rounded-lg border border-slate-600 
               focus:border-blue-500 outline-none font-mono text-sm resize-none"
      ></textarea>
      
      <div class="flex items-center justify-between mt-4">
        <span class="text-sm text-slate-400">{content.split('\n').filter(l => l.trim()).length} lines</span>
        <button
          on:click={analyze}
          disabled={analyzing || !content.trim()}
          class="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 
                 text-white rounded-lg font-semibold flex items-center gap-2"
        >
          {#if analyzing}
            <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            Analyzing...
          {:else}
            🧠 Process
          {/if}
        </button>
      </div>
    </div>
    
  {:else if step === 'organize'}
    <div class="space-y-6">
      <!-- AI Insights Banner -->
      {#if typosFixed.length > 0 || garbageFiltered.length > 0 || hierarchy.length > 0}
        <div class="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-500/30 rounded-xl p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">🤖</span>
            <span class="font-semibold text-white">AI Cleaned Up Your Notes</span>
          </div>
          <div class="grid grid-cols-3 gap-4 text-sm">
            {#if typosFixed.length > 0}
              <div class="bg-slate-800/50 rounded-lg p-3">
                <div class="text-green-400 font-medium mb-1">✏️ Typos Fixed ({typosFixed.length})</div>
                {#each typosFixed.slice(0, 3) as typo}
                  <div class="text-slate-400 text-xs">
                    <span class="line-through text-red-400/70">{typo.from}</span> → <span class="text-green-400">{typo.to}</span>
                  </div>
                {/each}
              </div>
            {/if}
            {#if garbageFiltered.length > 0}
              <div class="bg-slate-800/50 rounded-lg p-3">
                <div class="text-amber-400 font-medium mb-1">🗑️ Garbage Removed ({garbageFiltered.length})</div>
                <div class="text-slate-400 text-xs">{garbageFiltered.slice(0, 5).join(', ')}</div>
              </div>
            {/if}
            {#if hierarchy.length > 0}
              <div class="bg-slate-800/50 rounded-lg p-3">
                <div class="text-blue-400 font-medium mb-1">📊 Hierarchy Detected</div>
                {#each hierarchy.slice(0, 2) as h}
                  <div class="text-slate-400 text-xs">{h.child} → under {h.parent}</div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Organization Groups -->
      <div class="bg-emerald-900/20 border border-emerald-600/50 rounded-xl p-6">
        <div class="flex items-center gap-3 mb-4">
          <span class="text-2xl">📂</span>
          <div>
            <h2 class="text-xl font-bold text-white">How should I organize these?</h2>
            <p class="text-sm text-emerald-300">Found {detectedOrganization?.groups?.length || 0} groups</p>
          </div>
        </div>
        
        <div class="space-y-3">
          {#each detectedOrganization?.groups || [] as group}
            <div class="bg-slate-800/70 rounded-lg p-4">
              <div class="flex items-start justify-between gap-4">
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="text-lg font-semibold text-white">{group.name}</span>
                    <span class="text-xs px-2 py-0.5 rounded bg-slate-600">{group.items_count} items</span>
                    <span class="text-xs px-2 py-0.5 rounded {typeColors[group.type] || 'bg-slate-600'}">
                      {group.type}
                    </span>
                  </div>
                  
                  {#if group.classification_reason}
                    <div class="text-xs text-slate-500 mb-2">💡 {group.classification_reason}</div>
                  {/if}
                  
                  {#if group.merged_from?.length > 1}
                    <div class="text-xs text-purple-400 mb-2">🔀 Merged: {group.merged_from.join(' + ')}</div>
                  {/if}
                  
                  {#if group.integrates_with?.length > 0}
                    <div class="text-xs text-cyan-400 mb-2">🔌 Integrates: {group.integrates_with.join(', ')}</div>
                  {/if}
                  
                  {#if group.sample_items?.length > 0}
                    <div class="text-xs text-slate-400">
                      {#each group.sample_items.slice(0, 2) as sample}
                        <div class="truncate">• {sample}</div>
                      {/each}
                    </div>
                  {/if}
                </div>
                
                <div class="flex flex-col gap-2">
                  <select
                    value={organizationChoices[group.name] || group.type}
                    on:change={(e) => setOrganizationType(group.name, e.target.value)}
                    class="bg-slate-700 text-white px-3 py-2 rounded-lg border border-slate-600 text-sm"
                  >
                    {#each orgTypeOptions as opt}
                      <option value={opt.value}>{opt.label}</option>
                    {/each}
                  </select>
                  
                  <!-- Parent selector for modules/services -->
                  {#if ['module', 'service'].includes(organizationChoices[group.name] || group.type)}
                    <select
                      value={parentChoices[group.name] || group.parent || ''}
                      on:change={(e) => setParent(group.name, e.target.value)}
                      class="bg-slate-600 text-white px-3 py-2 rounded-lg border border-slate-500 text-sm"
                    >
                      <option value="">↳ Select parent...</option>
                      {#each availableParents.filter(p => p !== group.name) as parent}
                        <option value={parent}>{parent}</option>
                      {/each}
                    </select>
                  {/if}
                </div>
              </div>
            </div>
          {/each}
        </div>
        
        {#if detectedOrganization?.unassigned_count > 0}
          <div class="mt-4 bg-amber-900/30 border border-amber-600/30 rounded-lg p-4">
            <div class="text-amber-300 font-medium mb-2">
              ⚠️ {detectedOrganization.unassigned_count} items have no group
            </div>
            <select
              bind:value={defaultProjectChoice}
              class="bg-slate-700 text-white px-3 py-2 rounded-lg border border-slate-600 text-sm w-full"
            >
              <option value="inbox">📥 Inbox</option>
              <option value="none">🚫 Leave unassigned</option>
              {#each existingProjects as proj}
                <option value={proj.name || proj}>{proj.name || proj}</option>
              {/each}
            </select>
          </div>
        {/if}
        
        <div class="flex justify-end gap-3 mt-6">
          <button on:click={() => step = 'input'} class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg">
            ← Back
          </button>
          <button on:click={confirmOrganization} class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium">
            Continue →
          </button>
        </div>
      </div>
    </div>
    
  {:else if step === 'clarify'}
    <div class="bg-amber-900/20 border border-amber-600/50 rounded-xl p-6">
      <div class="flex items-center gap-3 mb-4">
        <span class="text-2xl">🤔</span>
        <h2 class="text-xl font-bold text-white">Clarify ambiguous items</h2>
      </div>
      
      <div class="space-y-4">
        {#each result.ambiguous_items as item}
          <div class="bg-slate-800/70 rounded-lg p-4">
            <div class="text-white font-medium mb-1">"{item.text}"</div>
            <div class="text-sm text-slate-400 mb-2">{item.question}</div>
            <input
              type="text"
              bind:value={clarifications[item.text]}
              placeholder="What did you mean?"
              class="w-full bg-slate-700 text-white px-3 py-2 rounded border border-slate-600 text-sm"
            />
          </div>
        {/each}
      </div>
      
      <div class="flex justify-end gap-3 mt-6">
        <button on:click={skipClarification} class="px-4 py-2 bg-slate-700 text-white rounded-lg">Skip</button>
        <button on:click={submitClarifications} class="px-6 py-2 bg-amber-600 text-white rounded-lg font-medium">Continue</button>
      </div>
    </div>
    
  {:else if step === 'review'}
    <div class="space-y-6">
      <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <h2 class="text-xl font-bold text-white mb-4">📊 Summary</h2>
        <div class="grid grid-cols-4 gap-3">
          {#each Object.entries(itemsByType) as [type, items]}
            {#if items.length > 0}
              <div class="bg-slate-700/50 rounded-lg p-3 text-center">
                <div class="text-2xl">{itemTypeConfig[type]?.icon || '📄'}</div>
                <div class="text-xl font-bold text-white">{items.length}</div>
                <div class="text-xs text-slate-400">{itemTypeConfig[type]?.label || type}</div>
              </div>
            {/if}
          {/each}
        </div>
      </div>
      
      {#each Object.entries(itemsByType) as [type, items]}
        {#if items.length > 0}
          <div class="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h3 class="text-lg font-semibold text-white mb-4">
              {itemTypeConfig[type]?.icon} {itemTypeConfig[type]?.label}s ({items.length})
            </h3>
            <div class="space-y-2 max-h-64 overflow-y-auto">
              {#each items as item}
                <div class="bg-slate-700/50 rounded-lg p-3 flex items-start justify-between">
                  <div>
                    <div class="text-white">{item.action}</div>
                    {#if item.project}
                      <div class="text-xs text-blue-400 mt-1">📁 {item.project}</div>
                    {/if}
                  </div>
                  {#if item.priority !== 'medium'}
                    <span class="text-xs px-2 py-0.5 rounded {item.priority === 'high' ? 'bg-red-600/30 text-red-300' : 'bg-slate-600'}">
                      {item.priority}
                    </span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      {/each}
      
      <div class="flex justify-end gap-3">
        <button on:click={() => step = 'organize'} class="px-4 py-2 bg-slate-700 text-white rounded-lg">← Back</button>
        <button
          on:click={save}
          disabled={saving}
          class="px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold flex items-center gap-2"
        >
          {#if saving}
            <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            Saving...
          {:else}
            💾 Save {totalItems} Items
          {/if}
        </button>
      </div>
    </div>
    
  {:else if step === 'done'}
    <div class="bg-green-900/20 border border-green-600/50 rounded-xl p-8 text-center">
      <div class="text-6xl mb-4">✅</div>
      <h2 class="text-2xl font-bold text-white mb-2">Done!</h2>
      <p class="text-slate-400 mb-6">Saved {result?.summary?.total_structured || 0} items</p>
      <div class="flex justify-center gap-4">
        <button on:click={reset} class="px-6 py-2 bg-blue-600 text-white rounded-lg">Process Another</button>
        <button on:click={close} class="px-6 py-2 bg-slate-700 text-white rounded-lg">Close</button>
      </div>
    </div>
  {/if}
</div>
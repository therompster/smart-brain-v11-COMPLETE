<script>
  import { createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  export let question;
  
  let answer = '';
  
  async function submit() {
    if (!answer.trim()) return;
    
    await fetch(`/api/questions/${question.id}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer })
    });
    
    dispatch('answered');
  }
  
  function skip() {
    dispatch('answered');
  }
</script>

<div class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
  <div class="bg-slate-800 border-2 border-blue-500 rounded-2xl p-8 max-w-xl w-full shadow-2xl">
    
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <div class="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center">
        <span class="text-xl">🤔</span>
      </div>
      <div>
        <div class="text-blue-400 text-sm uppercase tracking-wide">Quick Question</div>
        <div class="text-white font-semibold">Help me understand this better</div>
      </div>
    </div>
    
    <!-- Question -->
    <div class="mb-6">
      <h2 class="text-xl font-bold text-white mb-4">{question.question}</h2>
      
      {#if question.context}
        <div class="bg-slate-900/50 border border-slate-700 rounded-lg p-4 text-sm">
          <div class="text-slate-400 whitespace-pre-wrap">{question.context}</div>
        </div>
      {/if}
    </div>
    
    <!-- Answer Input -->
    <div class="mb-6">
      {#if question.options && question.options.length > 0 && question.type === 'domain_routing'}
        <!-- Multiple choice for domain routing -->
        <div class="space-y-2">
          {#each question.options as option}
            <button
              on:click={() => answer = option}
              class="w-full text-left px-4 py-3 rounded-lg border transition-all {
                answer === option 
                  ? 'bg-blue-600 border-blue-500 text-white' 
                  : 'bg-slate-700 border-slate-600 text-slate-300 hover:border-slate-500'
              }"
            >
              {option}
            </button>
          {/each}
        </div>
      {:else}
        <!-- Free text for task clarification -->
        <textarea
          bind:value={answer}
          placeholder="Type your clarification..."
          rows="3"
          class="w-full bg-slate-700 text-white px-4 py-3 rounded-lg border border-slate-600 focus:border-blue-500 outline-none resize-none text-lg"
          autofocus
        ></textarea>
        <p class="text-xs text-slate-500 mt-2">Be specific - this will be added to the task so you remember later</p>
      {/if}
    </div>
    
    <!-- Actions -->
    <div class="flex gap-3">
      <button
        on:click={submit}
        disabled={!answer.trim()}
        class="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg font-semibold transition-all"
      >
        Save & Continue
      </button>
      <button
        on:click={skip}
        class="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition-all"
      >
        Skip
      </button>
    </div>
  </div>
</div>

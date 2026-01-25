<script>
  import { createEventDispatcher, onMount } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  export let question;
  
  let answer = '';
  
  async function submit() {
    await fetch(`/api/questions/${question.id}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        answer,
        type: question.type,
        keywords: question.context || '',
        suggested_domain: question.context?.match(/Suggested: (\S+)/)?.[1]
      })
    });
    
    dispatch('answered');
  }
</script>

<div class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
  <div class="bg-slate-800 border-2 border-blue-500 rounded-2xl p-8 max-w-lg w-full shadow-2xl">
    <div class="mb-6">
      <div class="text-blue-400 text-sm mb-2 uppercase tracking-wide">Need Your Help</div>
      <h2 class="text-2xl font-bold text-white mb-2">{question.question}</h2>
      {#if question.context}
        <p class="text-slate-400 text-sm">{question.context}</p>
      {/if}
    </div>
    
    <div class="mb-6">
      {#if question.options && question.options.length > 0}
        <!-- Multiple choice -->
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
        <!-- Free text -->
        <textarea
          bind:value={answer}
          placeholder="Type your answer..."
          rows="3"
          class="w-full bg-slate-700 text-white px-4 py-3 rounded-lg border border-slate-600 focus:border-blue-500 outline-none resize-none"
          autofocus
        ></textarea>
      {/if}
    </div>
    
    <button
      on:click={submit}
      disabled={!answer}
      class="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg font-semibold transition-all disabled:cursor-not-allowed"
    >
      Continue
    </button>
    
    <p class="text-xs text-slate-500 text-center mt-4">
      This helps me learn your preferences
    </p>
  </div>
</div>

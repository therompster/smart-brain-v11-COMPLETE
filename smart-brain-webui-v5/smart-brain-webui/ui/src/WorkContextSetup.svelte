<script>
  import { createEventDispatcher, onMount } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  let loading = true;
  let question = null;
  let answer = '';
  let complete = false;
  let status = null;
  
  onMount(async () => {
    await loadQuestion();
  });
  
  async function loadQuestion() {
    loading = true;
    
    // Get current status
    const statusRes = await fetch('/api/work-context/interview/status');
    status = await statusRes.json();
    
    // Get next question
    const res = await fetch('/api/work-context/interview/next');
    const data = await res.json();
    
    question = data.question;
    complete = data.complete;
    answer = '';
    loading = false;
  }
  
  async function submitAnswer() {
    if (!answer.trim()) return;
    
    loading = true;
    const res = await fetch('/api/work-context/interview/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question_id: question.id,
        answer: answer
      })
    });
    
    const result = await res.json();
    
    if (result.complete) {
      complete = true;
      loading = false;
      dispatch('complete');
    } else {
      await loadQuestion();
    }
  }
  
  async function reset() {
    if (!confirm('Reset interview and start over?')) return;
    
    await fetch('/api/work-context/interview/reset', { method: 'POST' });
    await loadQuestion();
  }
  
  function skip() {
    dispatch('skip');
  }
</script>

<div class="max-w-2xl mx-auto">
  <div class="bg-gradient-to-br from-indigo-900/30 to-purple-900/30 border border-indigo-700/50 rounded-2xl p-8">
    {#if loading}
      <div class="text-center py-8">
        <div class="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <div class="text-slate-400">Loading...</div>
      </div>
    {:else if complete}
      <div class="text-center py-8">
        <div class="text-5xl mb-4">✅</div>
        <h2 class="text-2xl font-bold text-white mb-2">Setup Complete!</h2>
        <p class="text-slate-300 mb-6">Your work context has been saved. The system will now use this to better organize your brain dumps.</p>
        <button
          on:click={() => dispatch('complete')}
          class="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium"
        >
          Start Using Brain Dump
        </button>
      </div>
    {:else if question}
      <div class="mb-6">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-indigo-300 uppercase tracking-wide">{question.phase}</span>
          {#if status?.answers?.platforms}
            <button
              on:click={reset}
              class="text-xs text-slate-500 hover:text-slate-300"
            >
              Reset
            </button>
          {/if}
        </div>
        <h2 class="text-2xl font-bold text-white mb-2">{question.question}</h2>
        {#if question.help}
          <p class="text-slate-400 text-sm">{question.help}</p>
        {/if}
      </div>
      
      <div class="mb-6">
        {#if question.type === 'multiline'}
          <textarea
            bind:value={answer}
            placeholder={question.placeholder}
            rows="6"
            class="w-full bg-slate-800/50 text-white px-4 py-3 rounded-lg border border-slate-600 focus:border-indigo-500 outline-none resize-none font-mono text-sm"
          ></textarea>
        {:else if question.type === 'textarea'}
          <textarea
            bind:value={answer}
            placeholder={question.placeholder}
            rows="4"
            class="w-full bg-slate-800/50 text-white px-4 py-3 rounded-lg border border-slate-600 focus:border-indigo-500 outline-none resize-none"
          ></textarea>
        {:else}
          <input
            type="text"
            bind:value={answer}
            placeholder={question.placeholder}
            class="w-full bg-slate-800/50 text-white px-4 py-3 rounded-lg border border-slate-600 focus:border-indigo-500 outline-none"
          />
        {/if}
      </div>
      
      <div class="flex justify-between">
        <button
          on:click={skip}
          class="px-4 py-2 text-slate-400 hover:text-white"
        >
          Skip for now
        </button>
        <button
          on:click={submitAnswer}
          disabled={!answer.trim()}
          class="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg font-medium"
        >
          Continue →
        </button>
      </div>
    {:else}
      <div class="text-center py-8">
        <h2 class="text-xl text-white mb-4">Let's learn about your work</h2>
        <p class="text-slate-400 mb-6">This helps the system organize your brain dumps automatically.</p>
        <button
          on:click={loadQuestion}
          class="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium"
        >
          Start Setup
        </button>
      </div>
    {/if}
  </div>
</div>

<script>
  import { createEventDispatcher, onMount } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  let currentQuestion = null;
  let answers = {};
  let loading = true;
  let totalQuestions = 7;
  
  onMount(async () => {
    await loadNextQuestion();
  });
  
  async function loadNextQuestion() {
    loading = true;
    const res = await fetch('/api/onboarding/next', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ previous_answers: answers })
    });
    const data = await res.json();
    currentQuestion = data.question;
    loading = false;
    
    if (!currentQuestion) {
      await complete();
    }
  }
  
  async function next() {
    await loadNextQuestion();
  }
  
  function back() {
    const keys = Object.keys(answers);
    if (keys.length > 0) {
      delete answers[keys[keys.length - 1]];
      answers = answers;
      loadNextQuestion();
    }
  }
  
  async function complete() {
    await fetch('/api/onboarding/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(answers)
    });
    dispatch('complete');
  }
  
  $: progress = ((Object.keys(answers).length + 1) / totalQuestions) * 100;
</script>

<div class="max-w-2xl mx-auto">
  <div class="bg-gradient-to-br from-blue-900/30 to-purple-900/30 border border-blue-700/50 rounded-2xl p-8">
    {#if loading}
      <div class="text-center text-slate-400">Loading...</div>
    {:else if currentQuestion}
      <div class="mb-6">
        <div class="flex justify-between text-sm text-slate-400 mb-2">
          <span>Question {Object.keys(answers).length + 1} of {totalQuestions}</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div class="h-full bg-blue-500 transition-all" style="width: {progress}%"></div>
        </div>
      </div>
      
      <div class="mb-8">
        <h2 class="text-2xl font-bold text-white mb-4">{currentQuestion.question}</h2>
        
        {#if currentQuestion.type === 'text'}
          <input
            type="text"
            bind:value={answers[currentQuestion.id]}
            placeholder={currentQuestion.placeholder}
            class="w-full bg-slate-700 text-white px-4 py-3 rounded-lg border border-slate-600 focus:border-blue-500 outline-none"
          />
        {:else if currentQuestion.type === 'textarea'}
          <textarea
            bind:value={answers[currentQuestion.id]}
            placeholder={currentQuestion.placeholder}
            rows="4"
            class="w-full bg-slate-700 text-white px-4 py-3 rounded-lg border border-slate-600 focus:border-blue-500 outline-none resize-none"
          ></textarea>
        {:else if currentQuestion.type === 'select'}
          <select
            bind:value={answers[currentQuestion.id]}
            class="w-full bg-slate-700 text-white px-4 py-3 rounded-lg border border-slate-600 focus:border-blue-500 outline-none"
          >
            <option value="">Select...</option>
            {#each currentQuestion.options as option}
              <option value={option}>{option}</option>
            {/each}
          </select>
        {:else if currentQuestion.type === 'allocation'}
          <div class="space-y-3">
            {#each currentQuestion.domains as domain, i}
              <div class="flex items-center gap-3">
                <label for="balance_{i}" class="flex-1 text-slate-300">{domain}</label>
                <input
                  id="balance_{i}"
                  name="balance_{i}"
                  type="number"
                  bind:value={answers[`work_balance_${i}`]}
                  min="0"
                  max="100"
                  class="w-20 bg-slate-700 text-white px-3 py-2 rounded-lg border border-slate-600"
                />
                <span class="text-slate-400">%</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
      
      <div class="flex justify-between">
        <button
          on:click={back}
          disabled={Object.keys(answers).length === 0}
          class="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg disabled:opacity-50"
        >
          Back
        </button>
        
        <button
          on:click={next}
          class="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold"
        >
          Next
        </button>
      </div>
    {/if}
  </div>
</div>

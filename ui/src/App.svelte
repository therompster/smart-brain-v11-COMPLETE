<script>
  import { onMount } from 'svelte';
  import NoteEditor from './NoteEditor.svelte';
  import NoteList from './NoteList.svelte';
  import TaskList from './TaskList.svelte';
  import DailyPlan from './DailyPlan.svelte';
  import Onboarding from './Onboarding.svelte';
  import QuestionModal from './QuestionModal.svelte';
  import ProjectView from './ProjectView.svelte';

  let view = 'plan';
  let showOnboarding = false;
  let pendingQuestion = null;
  let notes = [];
  let selectedNote = null;
  let domains = [];
  let selectedDomain = 'work/marriott';

  onMount(async () => {
    await checkOnboarding();
    await loadDomains();
    await checkQuestions();
    await loadNotes();
    setInterval(checkQuestions, 5000);
  });

  async function checkOnboarding() {
    const res = await fetch('/api/onboarding/status');
    const data = await res.json();
    showOnboarding = !data.completed;
  }
  
  async function loadDomains() {
    const res = await fetch('/api/domains');
    const data = await res.json();
    domains = data.domains || [];
    if (domains.length > 0 && domains[0].path) {
      selectedDomain = domains[0].path;
    }
  }
  
  async function checkQuestions() {
    const res = await fetch('/api/questions/pending');
    const data = await res.json();
    pendingQuestion = data.questions?.length > 0 ? data.questions[0] : null;
  }

  async function loadNotes() {
    const res = await fetch('/api/notes');
    notes = await res.json();
  }

  function newNote() { selectedNote = null; view = 'editor'; }
  function editNote(note) { selectedNote = note; view = 'editor'; }
  async function handleNoteSaved() { await loadNotes(); await checkQuestions(); view = 'plan'; selectedNote = null; }
  function handleOnboardingComplete() { showOnboarding = false; loadDomains(); }
  async function handleQuestionAnswered() { await checkQuestions(); }
</script>

<div class="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
  {#if pendingQuestion}
    <QuestionModal question={pendingQuestion} on:answered={handleQuestionAnswered} />
  {/if}
  
  {#if showOnboarding}
    <div class="py-16">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-white mb-2">Welcome to Second Brain</h1>
        <p class="text-slate-400">Let's learn about you</p>
      </div>
      <Onboarding on:complete={handleOnboardingComplete} />
    </div>
  {:else}
    <header class="border-b border-slate-700 bg-slate-900/50 backdrop-blur">
      <div class="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <h1 class="text-2xl font-bold text-white">Second Brain</h1>
        <div class="flex gap-3">
          <button on:click={() => view = 'plan'} class="px-4 py-2 rounded-lg {view === 'plan' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">Today</button>
          <button on:click={() => view = 'projects'} class="px-4 py-2 rounded-lg {view === 'projects' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">Projects</button>
          <button on:click={() => view = 'tasks'} class="px-4 py-2 rounded-lg {view === 'tasks' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">Tasks</button>
          <button on:click={() => view = 'list'} class="px-4 py-2 rounded-lg {view === 'list' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">Notes</button>
          <button on:click={newNote} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium">+ New Note</button>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 py-8">
      {#if view === 'plan'}
        <DailyPlan />
      {:else if view === 'projects'}
        <!-- Domain selector + hierarchy -->
        <div class="mb-6 flex items-center gap-4">
          <label class="text-slate-400 text-sm">Domain:</label>
          <select bind:value={selectedDomain} class="bg-slate-700 text-white px-3 py-2 rounded-lg border border-slate-600">
            {#each domains as d}
              <option value={d.path || d}>{d.name || d}</option>
            {/each}
          </select>
        </div>
        {#key selectedDomain}
          <ProjectView domain={selectedDomain} />
        {/key}
      {:else if view === 'editor'}
        <NoteEditor note={selectedNote} on:saved={handleNoteSaved} on:cancel={() => view = 'plan'} />
      {:else if view === 'tasks'}
        <TaskList />
      {:else}
        <NoteList {notes} on:edit={(e) => editNote(e.detail)} />
      {/if}
    </main>
  {/if}
</div>

<style>
  :global(body) { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
</style>

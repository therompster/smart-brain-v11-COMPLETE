<script>
  import { onMount } from 'svelte';
  import NoteEditor from './NoteEditor.svelte';
  import NoteList from './NoteList.svelte';
  import TaskList from './TaskList.svelte';
  import DailyPlan from './DailyPlan.svelte';
  import Onboarding from './Onboarding.svelte';
  import QuestionModal from './QuestionModal.svelte';
  import ProjectView from './ProjectView.svelte';
  import Financial from './Financial.svelte';
  import BrainDumpProcessor from './BrainDumpProcessor.svelte';
  import WorkContextSetup from './WorkContextSetup.svelte';

  let view = 'plan';
  let workContextComplete = false;
  let showOnboarding = false;
  let pendingQuestion = null;
  let notes = [];
  let selectedNote = null;
  let domains = [];
  let selectedDomain = 'work/marriott';

  onMount(async () => {
    await checkOnboarding();
    await checkWorkContext();
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
  
  async function checkWorkContext() {
    const res = await fetch('/api/work-context/interview/status');
    const data = await res.json();
    workContextComplete = data.phase === 'complete';
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
  function handleBrainDumpSaved() { view = 'tasks'; }
  function handleWorkContextComplete() { workContextComplete = true; view = 'dump'; }
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
        <div class="flex gap-2">
          <button on:click={() => view = 'plan'} class="px-3 py-2 rounded-lg text-sm {view === 'plan' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">Today</button>
          <button on:click={() => view = 'projects'} class="px-3 py-2 rounded-lg text-sm {view === 'projects' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">Projects</button>
          <button on:click={() => view = 'tasks'} class="px-3 py-2 rounded-lg text-sm {view === 'tasks' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">Tasks</button>
          <button on:click={() => view = 'financial'} class="px-3 py-2 rounded-lg text-sm {view === 'financial' ? 'bg-amber-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">💰</button>
          <button on:click={() => view = 'list'} class="px-3 py-2 rounded-lg text-sm {view === 'list' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}">Notes</button>
          <div class="w-px bg-slate-700 mx-1"></div>
          <button on:click={() => view = 'dump'} class="px-3 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium">🧠 Dump</button>
          <button on:click={newNote} class="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium">+ Note</button>
          <button on:click={() => view = 'setup'} class="px-3 py-2 rounded-lg text-sm {view === 'setup' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}" title="Work Context Setup">⚙️</button>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 py-8">
      {#if view === 'plan'}
        <DailyPlan />
      {:else if view === 'setup'}
        <WorkContextSetup on:complete={handleWorkContextComplete} on:skip={() => view = 'plan'} />
      {:else if view === 'dump'}
        <BrainDumpProcessor domain={selectedDomain} on:saved={handleBrainDumpSaved} on:cancel={() => view = 'plan'} />
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
      {:else if view === 'financial'}
        <Financial />
      {:else}
        <NoteList {notes} on:edit={(e) => editNote(e.detail)} />
      {/if}
    </main>
  {/if}
</div>

<style>
  :global(body) { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
</style>

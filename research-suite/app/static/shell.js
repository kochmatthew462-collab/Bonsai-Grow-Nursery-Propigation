/*
 * The top-level tab switch between the research half and the charting half.
 *
 * The two halves are separate applications that share a shell, a session token
 * and a stylesheet, and nothing else. They keep separate DOM roots (`#view` and
 * `#chart-view`) and separate navs, so neither can paint over the other, and the
 * charting reference payload is fetched lazily the first time its tab is opened —
 * a nurse who only ever writes papers never pays for it.
 *
 * The active tab is recorded in sessionStorage rather than the URL. A tab name in
 * a URL is harmless, but the token arrives in the fragment and is cleared on load
 * (see `takeToken` in app.js), so writing to the URL afterwards risks a race with
 * that cleanup for no benefit.
 */
'use strict';

const shell = { tab: 'research' };

const TAB_BRAND = {
  research: '📑 Koch Research Suite',
  charting: '🩺 Clinical charting',
};

function applyTab(name) {
  shell.tab = name === 'charting' ? 'charting' : 'research';
  const charting = shell.tab === 'charting';

  document.getElementById('view').hidden = charting;
  document.getElementById('chart-view').hidden = !charting;
  document.getElementById('brand-text').textContent =
    TAB_BRAND[shell.tab].slice(2).trim();

  // Each half owns its own nav. Hiding both here and letting the active half's
  // own render() decide whether to show its nav keeps the two from fighting over
  // the same element on a switch.
  document.getElementById('nav').hidden = true;
  document.getElementById('chart-nav').hidden = true;
  document.getElementById('project-label').hidden = charting;
  document.getElementById('switch-project').hidden = charting || !state.project;
  document.getElementById('encounter-label').hidden = !charting;
  document.getElementById('switch-encounter').hidden = !charting;

  for (const button of document.querySelectorAll('.tabbar button')) {
    const active = button.dataset.tab === shell.tab;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  }

  try {
    sessionStorage.setItem('active_tab', shell.tab);
  } catch (error) { /* private browsing — the default tab is fine */ }

  if (charting) {
    guard(async () => {
      await initCharting();
      renderChart();
    });
  } else {
    render();
  }
}

document.querySelector('.tabbar').addEventListener('click', (event) => {
  const name = event.target.closest('button');
  if (name && name.dataset.tab) applyTab(name.dataset.tab);
});

document.getElementById('chart-nav').addEventListener('click', (event) => {
  const view = event.target.dataset && event.target.dataset.cview;
  if (view) goChart(view);
});

document.getElementById('switch-encounter').addEventListener('click', () => {
  chartState.encounter = null;
  chartState.draft = null;
  chartState.preview = null;
  goChart('note');
});

let remembered = 'research';
try {
  remembered = sessionStorage.getItem('active_tab') || 'research';
} catch (error) { /* ignore */ }
applyTab(remembered);

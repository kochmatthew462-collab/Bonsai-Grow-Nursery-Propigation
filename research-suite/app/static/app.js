/*
 * Koch Research Suite — front end.
 *
 * Vanilla JavaScript, no build step, no dependencies. Same reasoning as the
 * nursery tracker in this repo: the app stays a set of plain files you can read,
 * and the Content-Security-Policy in main.py forbids third-party script anyway.
 *
 * The session token arrives in the URL fragment (`#token=…`). A fragment is
 * never sent to a server or written to a proxy log, which is why it is used
 * rather than a query string. It is moved into memory and the fragment is
 * cleared on load so it does not linger in the address bar or in history.
 */
'use strict';

const state = {
  token: '',
  config: null,
  configError: '',
  project: null,
  view: 'projects',
  busy: false,
};

/* ------------------------------------------------------------------ plumbing */

function takeToken() {
  const match = /(?:^|[#&])token=([^&]+)/.exec(location.hash || '');
  if (match) {
    setToken(decodeURIComponent(match[1]));
    history.replaceState(null, '', location.pathname);
    return;
  }
  try {
    state.token = sessionStorage.getItem('research_token') || '';
  } catch (error) {
    state.token = '';
  }
}

function setToken(value) {
  state.token = (value || '').trim();
  try {
    if (state.token) sessionStorage.setItem('research_token', state.token);
    else sessionStorage.removeItem('research_token');
  } catch (error) { /* private browsing — memory only, which still works */ }
}

/* A rejected token has to be forgotten, not remembered.

   takeToken stores whatever arrives in the fragment and then strips the
   fragment from the address bar. So pasting one stale URL was permanent: the
   bad token went into sessionStorage, every reload read it back, and "Try
   again" resent it. There was no way out from inside the page — the only
   escape was pasting a *different* URL, which is exactly what someone stuck in
   this state does not have. */

function forgetToken() {
  setToken('');
}

/* Accepts the whole launch URL or the bare token, because at this point the
   user is copying out of a terminal and either is a reasonable thing to grab. */

function tokenFromPaste(text) {
  const value = (text || '').trim();
  const match = /(?:[#&?]token=)([^&\s]+)/.exec(value);
  if (match) return decodeURIComponent(match[1]);
  return /^[A-Za-z0-9_-]{16,}$/.test(value) ? value : '';
}

async function api(path, options = {}) {
  const headers = Object.assign(
    { 'X-Research-Token': state.token },
    options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    options.headers || {},
  );
  const response = await fetch(path, Object.assign({}, options, { headers }));
  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }
  if (!response.ok) {
    const detail = (payload && payload.detail) || `HTTP ${response.status}`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return payload;
}

const post = (path, body) =>
  api(path, { method: 'POST', body: JSON.stringify(body || {}) });

function toast(message, bad = false) {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.hidden = false;
  node.classList.toggle('toast-bad', bad);
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { node.hidden = true; }, bad ? 9000 : 4500);
}

async function guard(work) {
  if (state.busy) return;
  state.busy = true;
  document.body.classList.add('busy');
  try {
    await work();
  } catch (error) {
    toast(error.message || String(error), true);
  } finally {
    state.busy = false;
    document.body.classList.remove('busy');
  }
}

/* --------------------------------------------------------------- DOM helpers */

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name === 'class') node.className = value;
    else if (name === 'html') node.innerHTML = value;
    else if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else if (value === true) node.setAttribute(name, '');
    else if (value !== false && value !== null && value !== undefined) {
      node.setAttribute(name, String(value));
    }
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function card(title, ...children) {
  return el('div', { class: 'card' }, title ? el('h2', {}, title) : null, ...children);
}

function notice(text, kind = '') {
  return el('div', { class: `notice ${kind ? 'notice-' + kind : ''}` }, text);
}

function chip(text, kind = '') {
  return el('span', { class: `chip ${kind ? 'chip-' + kind : ''}` }, text);
}

function field(labelText, input, hint) {
  return el('label', {}, labelText,
    hint ? el('span', { class: 'hint' }, hint) : null, input);
}

function statBlock(pairs) {
  return el('div', { class: 'stats' }, pairs.map(([value, label]) =>
    el('div', { class: 'stat' },
      el('span', { class: 'stat-value' }, value),
      el('span', { class: 'stat-label' }, label))));
}

/* ------------------------------------------------------------------- routing */

function render() {
  const nav = document.getElementById('nav');

  // The nav itself always shows on this tab. Hiding the whole bar until a
  // project existed also hid Settings — and Settings is where you put the
  // contact email that every search wants, so it is the one screen you need
  // *before* starting a paper. Only the steps that operate on an open project
  // come and go.
  // Tied to whether this half's view is showing, rather than to `shell.tab`:
  // `shell` is declared in shell.js, which loads *after* this file, so reading
  // it here would be a load-order inversion waiting to throw. The DOM already
  // knows which half is active.
  nav.hidden = document.getElementById('view').hidden;
  document.getElementById('switch-project').hidden = !state.project;
  document.getElementById('project-label').textContent =
    state.project ? state.project.topic : '';
  for (const button of nav.querySelectorAll('button')) {
    const view = button.dataset.view;
    button.classList.toggle('is-active', view === state.view);
    button.hidden = VIEWS_NEEDING_A_PROJECT.has(view) && !state.project;
  }

  const host = document.getElementById('view');
  host.replaceChildren();

  // Nothing can be drawn before /api/config answers, and shell.js calls
  // render() the moment the scripts load — before the fetch has finished, and
  // again if it failed. Every view reads state.config, so without this the
  // first paint throws "Cannot read properties of null (reading 'settings')"
  // and the real cause — usually a stale token — never reaches the screen.
  if (!state.config) {
    host.append(configGate());
    return;
  }

  if (VIEWS_NEEDING_A_PROJECT.has(state.view) && !state.project) {
    host.append(el('section', { class: 'stack' },
      el('h1', {}, 'Open a project first'),
      notice('That step works on one paper’s sources, claims and documents, so '
        + 'it needs a project open. Pick one below or start a new one.', 'warn'),
      viewProjects()));
    return;
  }

  // Wrapped, because the failure mode without it is the worst one this
  // interface has: a view that throws leaves `#view` empty — the nav still
  // highlights, the page is simply blank, and nothing says why. A visible
  // error is recoverable; a blank screen is not.
  try {
    host.append((VIEWS[state.view] || viewProjects)());
  } catch (error) {
    host.replaceChildren(el('section', { class: 'stack' },
      el('h1', {}, 'That screen failed to draw'),
      notice(`${error.message}. Nothing has been lost — your project is on `
        + 'disk. Try another step, or reload the page.', 'bad'),
      el('button', { class: 'button', onclick: () => go('projects') },
        'Back to projects')));
    throw error;                      // still surfaces in the console
  }
}

/* What to show when the application cannot talk to its own server.

   This is nearly always a stale session token: the token changes every time
   the server restarts, and an open tab or a bookmarked URL still carries the
   old one. The old behaviour was a toast that faded after nine seconds and a
   thrown TypeError underneath it — so the screen said "That screen failed to
   draw. Cannot read properties of null" and the actual answer was gone. */

function configGate() {
  if (!state.configError) {
    return el('section', { class: 'stack' },
      el('h1', {}, 'Connecting…'),
      el('p', { class: 'hint' }, 'Loading settings from the local server.'));
  }

  const stale = /token/i.test(state.configError);
  return el('section', { class: 'stack' },
    el('h1', {}, stale ? 'This link has an old session token'
      : 'Cannot reach the local server'),
    notice(state.configError, 'bad'),
    stale
      ? el('div', { class: 'stack' },
        notice('The token is now stable across restarts, so this should not '
          + 'recur — but a URL saved before that change, or from a different '
          + 'checkout, still carries the old one. Nothing is lost: your '
          + 'projects are files on disk.', 'warn'),
        el('h3', {}, 'What to do'),
        el('ol', { class: 'plain-list' },
          el('li', {}, 'Look at the terminal running the app.'),
          el('li', {}, 'Copy the whole Open: line, including everything after '
            + 'the # — that part is the token.'),
          el('li', {}, 'Paste it into the address bar.')),
        el('p', { class: 'hint' }, 'If the terminal shows no banner, the app '
          + 'is not running. Start it with bash run.sh and leave it running.'))
      : el('p', { class: 'hint' }, 'The server may have stopped. Start it with '
        + 'bash run.sh, then reload from the URL it prints.'),
    tokenBox());
}

function tokenBox() {
  const input = el('input', {
    type: 'text',
    placeholder: 'Paste the whole Open: URL, or just the token',
  });
  const status = el('div', {});

  const attempt = () => guard(async () => {
    const token = tokenFromPaste(input.value);
    if (!token) {
      status.replaceChildren(notice('That does not look like a token. Copy the '
        + 'whole Open: line from the terminal — the token is the part after '
        + 'the #.', 'warn'));
      return;
    }
    setToken(token);
    try {
      state.config = await api('/api/config');
      state.configError = '';
      render();
    } catch (error) {
      forgetToken();
      status.replaceChildren(notice(`${error.message} — that token was not `
        + 'accepted either. Check the terminal is showing a current banner.',
        'bad'));
    }
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') attempt();
  });

  return el('div', { class: 'stack' },
    field('Token', input),
    el('button', { class: 'button', onclick: attempt }, 'Use this token'),
    status);
}

const VIEWS = {
  projects: viewProjects,
  question: viewQuestion,
  sources: viewSources,
  screen: viewScreen,
  fulltext: viewFulltext,
  appraise: viewAppraise,
  write: viewWrite,
  check: viewCheck,
  export: viewExport,
  apa: viewApa,
  compliance: viewCompliance,
  settings: viewSettings,
};

/* Steps that read the open project. Question, APA 7, Compliance and Settings
   are deliberately absent: framing a question, reading the formatting rules,
   parsing a rubric or a journal's guidelines, and setting your contact email
   are all things worth doing before a project exists. APA 7 in particular is
   the standard the whole application exists to meet, and it degrades to its
   reference half rather than disappearing. */
const VIEWS_NEEDING_A_PROJECT = new Set([
  'sources', 'screen', 'fulltext', 'appraise', 'write', 'check', 'export',
]);

function go(view) {
  state.view = view;
  render();
}

/* ------------------------------------------------------------------ projects */

function viewProjects() {
  const section = document.getElementById('tpl-projects').content
    .cloneNode(true).firstElementChild;

  section.querySelector('#create-project').addEventListener('click', () => guard(async () => {
    const topic = section.querySelector('#new-topic').value.trim();
    if (!topic) { toast('A topic is required.', true); return; }
    const result = await post('/api/projects', {
      topic,
      question: section.querySelector('#new-question').value.trim(),
      academic_level: section.querySelector('#new-level').value,
    });
    state.project = result.project;
    go('sources');
  }));

  const list = section.querySelector('#project-list');
  list.append(el('p', { class: 'hint' }, 'Loading…'));
  api('/api/projects').then((data) => {
    list.replaceChildren();
    if (!data.projects.length) {
      list.append(el('p', { class: 'hint' }, 'No projects yet.'));
      return;
    }
    for (const summary of data.projects) {
      list.append(el('div', { class: 'row' },
        el('div', { class: 'row-head' },
          el('span', { class: 'row-title' }, summary.topic),
          chip(`${summary.sources} source${summary.sources === 1 ? '' : 's'}`),
          chip(`${summary.claims} claim${summary.claims === 1 ? '' : 's'}`),
          el('span', { class: 'row-meta' }, summary.updated_at.slice(0, 16).replace('T', ' '))),
        summary.question ? el('div', { class: 'row-meta' }, summary.question) : null,
        el('div', { class: 'row-actions' },
          el('button', {
            class: 'button button-small',
            onclick: () => guard(async () => {
              const data = await api(`/api/projects/${summary.project_id}`);
              state.project = data.project;
              go('sources');
            }),
          }, 'Open'),
          el('button', {
            class: 'button button-quiet button-small',
            onclick: () => guard(async () => {
              if (!confirm(`Move "${summary.topic}" aside? A dated copy is kept.`)) return;
              await api(`/api/projects/${summary.project_id}`, { method: 'DELETE' });
              toast('Moved aside. A dated copy remains in the data directory.');
              render();
            }),
          }, 'Remove'))));
    }
  }).catch((error) => {
    list.replaceChildren(notice(error.message, 'bad'));
  });

  return section;
}

/* ------------------------------------------------------------------- sources */

function viewSources() {
  const project = state.project;
  const derived = project._derived;
  const apiSources = state.config.sources.filter((s) => s.kind === 'api');
  const importOnly = state.config.sources.filter((s) => s.kind === 'import-only');

  const queryInput = el('input', { type: 'text', value: project.question || project.topic });
  const limitInput = el('input', { type: 'number', value: '30', min: '5', max: '100' });
  const yearsInput = el('input', { type: 'number', value: '0', min: '0', max: '50' });
  const checkboxes = apiSources.map((source) => {
    const box = el('input', {
      type: 'checkbox', value: source.key,
      checked: source.available && ['pubmed', 'europepmc', 'crossref'].includes(source.key),
      disabled: !source.available,
    });
    return { source, box };
  });

  const searchCard = card('Search the databases with an API',
    field('Query', queryInput,
      'PubMed field tags work here — "nurse staffing"[tiab] AND falls[mh]'),
    el('div', { class: 'card-row' },
      field('Results per source', limitInput),
      field('Published within (years)', yearsInput, '0 for no limit')),
    el('div', {},
      el('h3', {}, 'Sources'),
      el('div', { class: 'list' }, checkboxes.map(({ source, box }) =>
        el('label', { class: 'inline' }, box,
          el('span', {}, source.label,
            source.available ? null : chip('unavailable', 'warn'),
            el('div', { class: 'row-meta' },
              source.requires ? `Needs ${source.requires}. ${source.note}` : source.note)))))),
    el('button', {
      class: 'button',
      onclick: (event) => guard(async () => {
        event.target.disabled = true;
        try {
          const result = await post(`/api/projects/${project.id || project.project_id}/search`, {
            query: queryInput.value.trim(),
            sources: checkboxes.filter((c) => c.box.checked).map((c) => c.source.key),
            limit: Number(limitInput.value) || 30,
            years_back: Number(yearsInput.value) || 0,
          });
          state.project = result.project;
          const failures = result.searches.filter((s) => s.error);
          toast(`${result.found} record(s) retrieved, ${result.merged} duplicate(s) merged.`
            + (failures.length ? ` ${failures.length} source(s) failed — see the log below.` : ''));
          render();
        } finally {
          event.target.disabled = false;
        }
      }),
    }, 'Run search'));

  const fileInput = el('input', { type: 'file', accept: '.ris,.nbib,.bib,.bibtex,.txt,.xml,.csv,.tsv,.enw' });
  const hintInput = el('input', { type: 'text', placeholder: 'CINAHL Complete' });
  const importCard = card('Import from a database with no API',
    notice('This is how CINAHL, PsycINFO, Embase, Scopus, the Cochrane Library '
      + 'and JBI records get in. None of them sells API access to an individual, '
      + 'so run the search in the database itself, export the results, and drop '
      + 'the file here. Imported records go through the same deduplication, '
      + 'level classification, appraisal and APA formatting as anything '
      + 'retrieved automatically.'),
    field('Citation export (RIS, NBIB, BibTeX, EndNote XML, or CSV)', fileInput),
    field('Database name', hintInput, 'Recorded in the audit document as the source'),
    el('button', {
      class: 'button',
      onclick: () => guard(async () => {
        if (!fileInput.files.length) { toast('Choose a file first.', true); return; }
        const form = new FormData();
        form.append('file', fileInput.files[0]);
        form.append('source_hint', hintInput.value.trim());
        const result = await api(`/api/projects/${project.project_id}/import`,
          { method: 'POST', body: form });
        state.project = result.project;
        toast(`${result.imported} record(s) imported, ${result.merged} duplicate(s) merged.`);
        render();
      }),
    }, 'Import file'),
    el('details', {},
      el('summary', {}, 'Databases that need this route'),
      el('div', { class: 'list' }, importOnly.map((source) =>
        el('div', { class: 'row' },
          el('div', { class: 'row-head' }, el('span', { class: 'row-title' }, source.label)),
          el('div', { class: 'row-meta' }, source.note))))));

  const searchLog = (project.searches || []).slice().reverse().slice(0, 12);
  const logCard = card('Search history',
    el('p', { class: 'hint' }, 'Every query is recorded verbatim and reproduced in '
      + 'the audit document, so the search can be re-run and checked.'),
    searchLog.length ? el('div', { class: 'table-wrap' }, el('table', {},
      el('thead', {}, el('tr', {}, ['Source', 'Query', 'Run', 'Hits', 'Kept', ''].map((h) => el('th', {}, h)))),
      el('tbody', {}, searchLog.map((entry) => el('tr', {},
        el('td', {}, entry.source || ''),
        el('td', {}, el('code', { class: 'overlap-phrase' }, (entry.query || '').slice(0, 160))),
        el('td', {}, (entry.run_at || '').slice(0, 10)),
        el('td', {}, entry.total_available || '—'),
        el('td', {}, entry.retrieved || '—'),
        el('td', {}, entry.error ? chip('failed', 'bad')
          : entry.coverage_note ? chip('limited', 'warn') : chip('ok', 'good')))))))
      : el('p', { class: 'hint' }, 'No searches yet.'),
    searchLog.filter((e) => e.error).map((e) =>
      notice(`${e.source}: ${e.error}`, 'bad')),
    searchLog.filter((e) => e.coverage_note).map((e) =>
      notice(`${e.source}: ${e.coverage_note}`, 'warn')));

  return el('section', { class: 'stack' },
    el('h1', {}, 'Find the evidence'),
    statBlock([
      [derived.sources_total, 'sources found'],
      [derived.unscreened, 'not yet screened'],
      [derived.retracted, 'retracted'],
    ]),
    el('div', { class: 'grid-2' }, searchCard, importCard),
    logCard,
    el('button', { class: 'button', onclick: () => go('screen') }, 'Next: screen the sources →'));
}

/* -------------------------------------------------------------------- screen */

function viewScreen() {
  const project = state.project;
  const derived = project._derived;
  const pending = [];

  const levelOptions = state.config.levels.filter((l) => l.value !== 'not-evidence');

  const rows = (project.works || []).map((work) => {
    const included = el('select', {},
      el('option', { value: '', selected: work.included === null }, 'undecided'),
      el('option', { value: 'yes', selected: work.included === true }, 'include'),
      el('option', { value: 'no', selected: work.included === false }, 'exclude'));
    const reason = el('input', { type: 'text', value: work.screen_reason || '',
      placeholder: 'reason (required when excluding)' });
    const level = el('select', {},
      el('option', { value: '' }, `keep: ${work.level}`),
      levelOptions.map((l) => el('option', { value: l.value }, l.label)),
      el('option', { value: 'not-evidence' }, 'Not evidence-based'));

    const record = () => {
      pending.push({
        key: work.key,
        included: included.value === '' ? null : included.value === 'yes',
        reason: reason.value,
        level: level.value || undefined,
        level_note: level.value ? 'reviewed by hand during screening' : undefined,
      });
    };
    for (const input of [included, reason, level]) {
      input.addEventListener('change', record);
    }

    const authors = (work.authors || []).map((a) => a.family).filter(Boolean);
    const byline = authors.length
      ? (authors.length > 2 ? `${authors[0]} et al.` : authors.join(' & '))
      : 'No author';

    return el('div', { class: 'row' },
      el('div', { class: 'row-head' },
        el('span', { class: 'row-title' }, work.title || '(untitled)'),
        chip(`Level ${work.level}`, work.level === 'not-evidence' ? 'bad'
          : work.level === 'ungraded' ? 'warn' : 'good'),
        work.retracted ? chip('⚠ retracted', 'bad') : null,
        work.peer_reviewed === false ? chip('not peer reviewed', 'warn') : null),
      el('div', { class: 'row-meta' },
        `${byline} (${work.year || 'n.d.'}) · ${work.container || work.publisher || ''} · ${work.source_db}`),
      el('div', { class: 'row-meta' }, `Why this level: ${work.level_reason}`),
      work.retraction_note ? notice(`Retraction: ${work.retraction_note}`, 'bad') : null,
      el('div', { class: 'card-row' },
        field('Decision', included), field('Level override', level), field('Note', reason)));
  });

  return el('section', { class: 'stack' },
    el('h1', {}, 'Screen and grade'),
    statBlock([
      [derived.sources_total, 'total'],
      [derived.sources_included, 'included'],
      [derived.unscreened, 'undecided'],
      [Object.entries(derived.level_counts || {}).map(([k, v]) => `${k}:${v}`).join('  ') || '—',
        'levels'],
    ]),
    notice('A level of "ungraded" means the design could not be determined from '
      + 'the publication type or abstract — read the methods section and set it '
      + 'by hand. An ungraded source does not pass the minimum-level filter, '
      + 'which is deliberate: it means "decide", not "include quietly".', 'warn'),
    card('Retraction check',
      el('p', { class: 'hint' }, 'Checks every source against Crossref retraction '
        + 'notices, MEDLINE retraction records and the OpenAlex flag. Negative '
        + 'results are recorded too, so the audit document can state that the '
        + 'check was run.'),
      el('button', {
        class: 'button button-quiet',
        onclick: () => guard(async () => {
          const result = await post(`/api/projects/${project.project_id}/retractions`);
          state.project = result.project;
          toast(`Checked ${result.checked} source(s); ${result.retracted} retraction(s) found.`);
          render();
        }),
      }, 'Run retraction check')),
    card(`Sources (${rows.length})`, rows.length ? el('div', { class: 'list' }, rows)
      : el('p', { class: 'hint' }, 'No sources yet — search or import first.')),
    el('div', { class: 'card-row' },
      el('button', {
        class: 'button',
        onclick: () => guard(async () => {
          if (!pending.length) { toast('No changes to save.'); return; }
          const result = await post(`/api/projects/${project.project_id}/screen`, pending);
          state.project = result.project;
          pending.length = 0;
          toast('Screening saved.');
          render();
        }),
      }, 'Save screening decisions'),
      el('button', { class: 'button button-quiet', onclick: () => go('fulltext') },
        'Next: full text →')));
}

/* ----------------------------------------------------------------- full text */

const fulltextState = { extractions: {} };

function viewFulltext() {
  const project = state.project;
  const host = el('div', { class: 'stack' }, el('p', { class: 'hint' }, 'Loading…'));

  const refresh = () => {
    api(`/api/projects/${project.project_id}/fulltext`).then((data) => {
      host.replaceChildren();

      if (!data.pdf) {
        host.append(notice('PDFs cannot be parsed on this machine — pypdf did '
          + 'not load. Paste the text of each article instead; everything '
          + 'downstream is identical either way. To turn PDF reading on: '
          + 'pip install pypdf.', 'warn'));
      }

      host.append(card(`Ingested (${data.ingested.length})`,
        data.ingested.length
          ? el('div', { class: 'table-wrap' }, el('table', {},
            el('thead', {}, el('tr', {}, ['Source', 'Pages', 'Paragraphs', 'Words', 'From', '']
              .map((h) => el('th', {}, h)))),
            el('tbody', {}, data.ingested.map((row) => el('tr', {},
              el('td', {}, row.label || row.work_key),
              el('td', {}, row.pages),
              el('td', {}, row.passages),
              el('td', {}, row.words),
              el('td', {}, el('span', { class: 'hint' }, row.source)),
              el('td', {},
                el('button', {
                  class: 'button button-quiet',
                  onclick: () => guard(async () => {
                    fulltextState.extractions[row.work_key] = await post(
                      `/api/projects/${project.project_id}/fulltext/${encodeURIComponent(row.work_key)}/extract`,
                      { apply: false });
                    refresh();
                  }),
                }, 'Read it'),
                el('button', {
                  class: 'button button-quiet',
                  onclick: () => guard(async () => {
                    await api(
                      `/api/projects/${project.project_id}/fulltext/${encodeURIComponent(row.work_key)}`,
                      { method: 'DELETE' });
                    delete fulltextState.extractions[row.work_key];
                    toast('Removed.');
                    refresh();
                  }),
                }, 'Remove')))))))
          : el('p', { class: 'hint' }, 'Nothing ingested yet. Until a source’s '
            + 'full text is here, its claims cannot be anchored to it and the '
            + 'Check screen will say so rather than pass them.')));

      for (const row of data.ingested) {
        const extracted = fulltextState.extractions[row.work_key];
        if (extracted) host.append(extractionCard(row, extracted, refresh));
      }

      const pending = data.missing;
      if (pending.length) {
        const select = el('select', {}, pending.map((w) =>
          el('option', { value: w.key }, w.label)));
        const fileInput = el('input', { type: 'file', accept: '.pdf,.txt,.text' });
        const textInput = el('textarea', {
          rows: 6,
          placeholder: '…or paste the article text here. Keep the headings on '
            + 'their own lines — that is how Methods and Results get told apart.',
        });
        host.append(card(`Add full text (${pending.length} source${pending.length === 1 ? '' : 's'} without it)`,
          field('Source', select),
          field('PDF or text file', fileInput,
            data.pdf ? 'The file is read and discarded. Nothing is copied into '
              + 'the data directory.'
              : 'PDF parsing is unavailable here — a .txt file still works.'),
          field('Or paste the text', textInput),
          el('button', {
            class: 'button',
            onclick: () => guard(async () => {
              const form = new FormData();
              form.append('work_key', select.value);
              if (fileInput.files && fileInput.files[0]) {
                form.append('file', fileInput.files[0]);
              }
              form.append('text', textInput.value);
              const out = await api(
                `/api/projects/${project.project_id}/fulltext`,
                { method: 'POST', body: form });
              toast(out.note, !out.ok);
              if (out.ok) { textInput.value = ''; fileInput.value = ''; refresh(); }
            }),
          }, 'Read this source')));
      }

      if (data.ingested.length) host.append(locateCard());
      host.append(capabilityCard());

      host.append(el('button', { class: 'button button-quiet', onclick: () => go('appraise') },
        'Next: appraise →'));
    }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));
  };
  refresh();

  return el('section', { class: 'stack' },
    el('h1', {}, 'Full text'),
    notice('Reading a source’s full text does two things. It lets the evidence '
      + 'matrix be filled from the article rather than from its abstract — '
      + 'sample size, design, analysis and results, each with the page and the '
      + 'sentence it came from. And it lets every claim you write be anchored '
      + 'to the paragraph it came out of, so a sentence attributed to a source '
      + 'that does not contain it can be caught before a marker catches it.'),
    notice('This is a reader, not a model. It reports patterns it matched and '
      + 'never fills a cell it cannot point at, because a plausible unsourced '
      + 'number in a matrix is worse than an empty one: the empty cell gets '
      + 'checked.'),
    host);
}

function locateCard() {
  const project = state.project;
  const input = el('textarea', {
    rows: 3,
    placeholder: 'Paste a sentence from your draft to find the paragraph it '
      + 'came from.',
  });
  const results = el('div', { class: 'stack' });

  return card('Where did this sentence come from?',
    el('p', { class: 'hint' }, 'The same check the Check screen runs over the '
      + 'whole claim ledger, on one sentence at a time — useful while you are '
      + 'still writing it.'),
    field('Sentence', input),
    el('button', {
      class: 'button',
      onclick: () => guard(async () => {
        const out = await post(`/api/projects/${project.project_id}/locate`,
          { sentence: input.value });
        results.replaceChildren();
        if (out.note) results.append(notice(out.note, 'warn'));
        if (!out.matches.length) return;
        results.append(el('div', { class: 'table-wrap' }, el('table', {},
          el('thead', {}, el('tr', {}, ['Source', 'Where', 'Match', 'The paragraph']
            .map((h) => el('th', {}, h)))),
          el('tbody', {}, out.matches.map((match) => el('tr', {},
            el('td', {}, match.label || match.work_key),
            el('td', {}, el('code', { class: 'anchor' }, match.anchor),
              match.section ? el('span', { class: 'hint' }, ` ${match.section}`) : null),
            el('td', {}, chip(match.basis,
              match.basis === 'verbatim' ? 'bad'
                : match.basis === 'close paraphrase' ? 'good' : 'warn')),
            el('td', {}, el('span', { class: 'quoted-source' }, match.excerpt))))))));
      }),
    }, 'Find it'),
    results);
}

function capabilityCard() {
  const host = el('div', { class: 'stack' }, el('p', { class: 'hint' }, 'Checking…'));
  api('/api/fulltext/status').then((status) => {
    host.replaceChildren(
      notice(status.note, status.pdf ? 'good' : 'warn'),
      el('h3', {}, 'What this cannot do'),
      el('ul', { class: 'plain-list' },
        status.limits.map((line) => el('li', {}, line))));
  }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));
  return card('Reading PDFs', host);
}

function extractionCard(row, extracted, refresh) {
  const project = state.project;
  const fields = extracted.fields || {};
  const order = ['design', 'analysis', 'sample_size', 'response_rate',
    'follow_up', 'attrition', 'statistics', 'ethical_approval', 'funding',
    'conflicts', 'limitations'];
  const present = order.filter((name) => (fields[name] || []).length);

  const body = el('div', { class: 'stack' });

  if (present.length) {
    body.append(el('div', { class: 'table-wrap' }, el('table', {},
      el('thead', {}, el('tr', {}, ['Field', 'Read as', 'Where', 'From the article']
        .map((h) => el('th', {}, h)))),
      el('tbody', {}, present.flatMap((name) => (fields[name] || []).map((hit, index) =>
        el('tr', {},
          el('td', {}, index === 0 ? name.replace(/_/g, ' ') : ''),
          el('td', {}, el('strong', {}, hit.value)),
          el('td', {}, el('code', { class: 'anchor' }, hit.anchor),
            hit.section ? el('span', { class: 'hint' }, ` ${hit.section}`) : null),
          el('td', {}, el('span', { class: 'quoted-source' }, hit.sentence)))))))));
  }

  if ((extracted.missing || []).length) {
    body.append(notice(extracted.missing_note, 'warn'));
  }

  body.append(notice(extracted.note));

  if (extracted.applied_note) {
    body.append(notice(extracted.applied_note, 'good'));
  } else {
    body.append(el('button', {
      class: 'button',
      onclick: () => guard(async () => {
        fulltextState.extractions[row.work_key] = await post(
          `/api/projects/${project.project_id}/fulltext/${encodeURIComponent(row.work_key)}/extract`,
          { apply: true });
        toast('Written into the evidence matrix.');
        state.project = (await api(`/api/projects/${project.project_id}`)).project;
        refresh();
      }),
    }, 'Fill the empty matrix cells with this'));
    body.append(el('p', { class: 'hint' }, 'Only cells you have left empty are '
      + 'written to. Anything you typed wins.'));
  }

  return card(`What the article says — ${row.label || row.work_key}`, body);
}

/* ------------------------------------------------------------------ appraise */

function viewAppraise() {
  const project = state.project;
  const included = (project.works || []).filter((w) => w.included !== false);
  const appraisals = new Map((project.appraisals || []).map((a) => [a.work_key, a]));
  const extractions = new Map((project.extractions || []).map((e) => [e.work_key, e]));

  const host = el('div', { class: 'list' });

  for (const work of included) {
    const appraisal = appraisals.get(work.key);
    const extraction = extractions.get(work.key) || {};

    const body = el('div', { class: 'stack' });
    const row = el('div', { class: 'row' },
      el('div', { class: 'row-head' },
        el('span', { class: 'row-title' }, work.title || '(untitled)'),
        chip(`Level ${work.level}`),
        appraisal ? chip(appraisal.overall || 'not rated',
          appraisal.overall === 'high' ? 'good'
            : appraisal.overall === 'low' || appraisal.overall === 'very-low' ? 'bad' : 'warn')
          : chip('not appraised', 'warn')),
      body);

    const details = el('details', {}, el('summary', {}, 'Appraise and extract'));
    body.append(details);
    details.addEventListener('toggle', () => {
      if (!details.open || details.dataset.loaded) return;
      details.dataset.loaded = '1';
      details.append(buildAppraisalForm(work, appraisal, extraction));
    });
    host.append(row);
  }

  return el('section', { class: 'stack' },
    el('h1', {}, 'Appraise the evidence'),
    notice('Each appraisal follows the methodological domains of a published '
      + 'instrument — CASP, JBI, AGREE II or AMSTAR 2 — and names which one. The '
      + 'question wording is this tool’s own, because those instruments are '
      + 'copyrighted and their item text is not reproduced here. If a course or '
      + 'journal requires a specific completed instrument, complete that '
      + 'instrument; this is a working appraisal and an audit record, not a '
      + 'substitute for a form someone else specified.'),
    card(`Included sources (${included.length})`, host),
    el('button', { class: 'button', onclick: () => go('write') }, 'Next: write →'));
}

function buildAppraisalForm(work, appraisal, extraction) {
  const wrap = el('div', { class: 'stack' });

  if (!appraisal) {
    const templateSelect = el('select', {},
      el('option', { value: '' }, 'choose automatically from the design'),
      state.config.appraisal_templates.map((t) =>
        el('option', { value: t.name }, `${t.name} — follows ${t.follows}`)));
    wrap.append(field('Appraisal template', templateSelect),
      el('button', {
        class: 'button button-small',
        onclick: () => guard(async () => {
          const result = await post(
            `/api/projects/${state.project.project_id}/appraisal/blank`,
            { key: work.key, template: templateSelect.value });
          const data = await api(`/api/projects/${state.project.project_id}`);
          state.project = data.project;
          toast(`Appraisal created following ${result.appraisal.instrument}.`);
          render();
        }),
      }, 'Create appraisal'));
    return wrap;
  }

  const itemInputs = appraisal.items.map((item) => {
    const answer = el('select', {},
      ['yes', 'no', 'unclear', 'n/a'].map((value) =>
        el('option', { value, selected: item.answer === value }, value)));
    const note = el('input', { type: 'text', value: item.note || '', placeholder: 'note' });
    wrap.append(el('div', { class: 'row' },
      el('div', {}, item.question),
      el('div', { class: 'card-row' }, field('Answer', answer), field('Note', note))));
    return { answer, note };
  });

  const strengths = el('textarea', {}, appraisal.strengths || '');
  const limitations = el('textarea', {}, appraisal.limitations || '');
  wrap.append(field('Strengths', strengths), field('Limitations', limitations));
  wrap.append(el('p', { class: 'hint' }, appraisal.instrument_citation));

  wrap.append(el('button', {
    class: 'button button-small',
    onclick: () => guard(async () => {
      const result = await post(`/api/projects/${state.project.project_id}/appraisal`, {
        work_key: work.key,
        items: itemInputs.map((i) => ({ answer: i.answer.value, note: i.note.value })),
        strengths: strengths.value,
        limitations: limitations.value,
      });
      toast(`Rated ${result.appraisal.overall}. ${result.appraisal.overall_reason}`);
      const data = await api(`/api/projects/${state.project.project_id}`);
      state.project = data.project;
    }),
  }, 'Save appraisal'));

  wrap.append(el('h3', {}, 'Evidence matrix row'));
  const fields = {};
  for (const [name, label] of [
    ['design', 'Design'], ['setting', 'Setting'],
    ['sample_description', 'Sample'], ['sample_size', 'Sample size'],
    ['intervention', 'Intervention'], ['comparator', 'Comparator'],
    ['outcomes', 'Outcomes'], ['key_findings', 'Key findings'],
    ['statistics', 'Statistics'], ['strengths', 'Strengths'],
    ['limitations', 'Limitations'], ['relevance', 'Relevance to the question'],
  ]) {
    fields[name] = el('input', { type: 'text', value: extraction[name] || '' });
    wrap.append(field(label, fields[name]));
  }
  wrap.append(el('button', {
    class: 'button button-small',
    onclick: () => guard(async () => {
      const payload = { work_key: work.key };
      for (const [name, input] of Object.entries(fields)) payload[name] = input.value;
      await post(`/api/projects/${state.project.project_id}/extraction`, payload);
      toast('Matrix row saved.');
      const data = await api(`/api/projects/${state.project.project_id}`);
      state.project = data.project;
    }),
  }, 'Save matrix row'));

  return wrap;
}

/* --------------------------------------------------------------------- write */

function viewWrite() {
  const project = state.project;
  const derived = project._derived;
  const byKey = new Map((project.works || []).map((w) => [w.key, w]));

  const claimRows = (project.claims || []).map((claim) => {
    const kind = claim.support_type === 'no-citation' ? 'own'
      : claim.support_type === 'direct-quote' ? 'quote'
        : (claim.work_keys || []).length ? '' : 'unsupported';
    const sources = (claim.work_keys || []).map((key) => {
      const work = byKey.get(key);
      if (!work) return chip(`⚠ unknown source ${key}`, 'bad');
      const authors = (work.authors || []).map((a) => a.family).filter(Boolean);
      return chip(`${authors[0] || 'Anon'}${authors.length > 2 ? ' et al.' : ''} (${work.year || 'n.d.'})`);
    });
    return el('div', { class: `claim ${kind ? 'claim-' + kind : ''}` },
      el('div', { class: 'claim-text' }, claim.text),
      el('div', { class: 'claim-meta' },
        chip(claim.section || 'unsectioned'),
        chip(claim.support_type),
        sources.length ? sources : chip(kind === 'own' ? 'author’s own analysis' : '⚠ no source', kind === 'own' ? '' : 'bad'),
        claim.locus ? chip(claim.locus) : null,
        claim.verified ? chip('✓ verified', 'good') : chip('unverified', 'warn')),
      claim.rationale ? el('div', { class: 'row-meta' }, `Why this source: ${claim.rationale}`) : null);
  });

  const sectionSelect = el('select', {},
    el('option', { value: '' }, 'all sections'),
    ['Introduction', 'Review of the Literature', 'Methodological Quality of the Evidence',
      'Discussion', 'Implications for Practice', 'Limitations', 'Conclusion']
      .map((name) => el('option', { value: name }, name)));

  const draftCard = card('Draft a claim ledger',
    state.config.drafting_available
      ? notice('The model produces one claim per sentence, each bound to a source, '
        + 'a locus in that source, the passage relied on, and why that source was '
        + 'chosen. It only sees the sources you screened in — it is never asked to '
        + 'recall literature, which is how fabricated citations get in. Any key it '
        + 'invents is dropped and reported.')
      : notice('No Anthropic API key is configured, so drafting is unavailable. '
        + 'Everything else works: add claims by hand below, or write in Word and '
        + 'paste sentences in. Add a key on the Settings page to enable drafting.', 'warn'),
    notice(state.config.integrity_notice, 'warn'),
    field('Section', sectionSelect, 'Leave as "all" to draft the whole paper'),
    el('button', {
      class: 'button', disabled: !state.config.drafting_available,
      onclick: (event) => guard(async () => {
        event.target.disabled = true;
        event.target.textContent = 'Drafting…';
        try {
          const result = await post(`/api/projects/${project.project_id}/draft`, {
            section: sectionSelect.value, replace: true,
          });
          state.project = result.project;
          for (const note of result.notes) toast(note, true);
          toast(`${result.claims_added} claim(s) drafted.`);
          render();
        } finally {
          event.target.disabled = false;
          event.target.textContent = 'Draft';
        }
      }),
    }, 'Draft'));

  const styleCard = card('Your writing voice',
    project.style.word_count
      ? el('div', {}, statBlock([
        [project.style.word_count.toLocaleString(), 'sample words'],
        [project.style.mean_sentence_words, 'mean sentence length'],
        [project.style.sentence_words_sd, 'sentence-length spread'],
        [Math.round(project.style.passive_rate * 100) + '%', 'passive sentences'],
        [project.style.flesch_kincaid_grade, 'reading grade'],
      ]), el('p', { class: 'hint' }, project.style.notes))
      : notice('No writing samples yet. Add two or three of your own finished '
        + 'papers on the Settings page — under about 1,500 words the measurements '
        + 'are noise, and the drafting step falls back on generic academic prose.', 'warn'),
    el('button', {
      class: 'button button-quiet',
      onclick: () => guard(async () => {
        const result = await post(`/api/projects/${project.project_id}/style`);
        const data = await api(`/api/projects/${project.project_id}`);
        state.project = data.project;
        toast(result.style.notes);
        render();
      }),
    }, 'Rebuild style profile from samples'));

  const editor = el('textarea', { rows: '10' },
    (project.claims || []).map((c) =>
      `[${c.section}] (${c.support_type}${c.locus ? ', ' + c.locus : ''}) `
      + `{${(c.work_keys || []).join(' ')}} ${c.text}`).join('\n'));

  return el('section', { class: 'stack' },
    el('h1', {}, 'Write'),
    statBlock([
      [derived.word_count.toLocaleString(), 'words'],
      [(project.claims || []).length, 'claims'],
      [derived.sources_cited, 'sources cited'],
      [(project.claims || []).filter((c) =>
        c.support_type !== 'no-citation' && !(c.work_keys || []).length).length,
        'claims with no source'],
    ]),
    el('div', { class: 'grid-2' }, draftCard, styleCard),
    card(`Claim ledger (${claimRows.length})`,
      el('p', { class: 'hint' }, 'Every sentence of the paper, with what supports '
        + 'it. Citations are inserted from these keys when the document is built, '
        + 'so they can never disagree with the reference list.'),
      claimRows.length ? el('div', { class: 'list' }, claimRows)
        : el('p', { class: 'hint' }, 'No claims yet.')),
    card('Edit claims as text',
      el('p', { class: 'hint' }, 'One claim per line: '
        + '[Section] (support_type, locus) {source keys} the sentence. '
        + 'Source keys come from the screened sources.'),
      editor,
      el('button', {
        class: 'button button-quiet',
        onclick: () => guard(async () => {
          const parsed = editor.value.split('\n').map((line) => line.trim())
            .filter(Boolean).map((line) => {
              const match = /^\[([^\]]*)\]\s*\(([^)]*)\)\s*\{([^}]*)\}\s*(.*)$/.exec(line);
              if (!match) return { section: 'Body', support_type: 'paraphrase', text: line };
              const [, section, meta, keys, text] = match;
              const parts = meta.split(',').map((p) => p.trim());
              return {
                section, support_type: parts[0] || 'paraphrase',
                locus: parts.slice(1).join(', '),
                work_keys: keys.split(/\s+/).filter(Boolean), text,
              };
            });
          const result = await post(`/api/projects/${project.project_id}/claims`, parsed);
          state.project = result.project;
          toast(`${parsed.length} claim(s) saved.`);
          render();
        }),
      }, 'Save claims')),
    el('button', { class: 'button', onclick: () => go('check') }, 'Next: check →'),
    statisticsCard());
}

/* --------------------------------------------------------------------- check */

function viewCheck() {
  const project = state.project;
  const host = el('div', { class: 'stack' }, el('p', { class: 'hint' }, 'Checking…'));

  api(`/api/projects/${project.project_id}/integrity`).then((report) => {
    host.replaceChildren();

    host.append(card('Originality',
      notice(report.summary, report.blockers.length ? 'warn' : 'good'),
      notice('No similarity percentage is reported, because there is no '
        + 'defensible number to report. A correct APA paper always shows '
        + 'measurable similarity — its reference list matches the original '
        + 'articles exactly, its quotations are supposed to match verbatim, and '
        + 'the standard phrasing of the field recurs in thousands of papers. What '
        + 'matters is whether each matched passage is quoted, cited or reworded.'),
      report.overlaps.length ? el('div', { class: 'table-wrap' }, el('table', {},
        el('thead', {}, el('tr', {}, ['Passage', 'Words', 'Matches', 'State'].map((h) => el('th', {}, h)))),
        el('tbody', {}, report.overlaps.map((o) => el('tr', {},
          el('td', {}, el('code', { class: 'overlap-phrase' }, o.phrase)),
          el('td', {}, o.words),
          el('td', {}, o.source),
          el('td', {}, o.quoted ? chip('quoted — fine', 'good')
            : o.severity === 'serious' ? chip('reword or quote', 'bad')
              : chip('review', 'warn')))))))
        : el('p', { class: 'hint' }, 'No unmarked verbatim passage of 12 words or '
          + 'more was found against the cited sources.'),
      notice(report.external.interpretation)));

    host.append(card('Citation defects',
      report.blockers.length
        ? el('div', { class: 'list' }, report.blockers.map((b) => notice(b, 'bad')))
        : notice('No citation defects. Every borrowed claim names a source, every '
          + 'direct quotation has a locator, and every cited source is in the '
          + 'project.', 'good'),
      report.warnings.length
        ? el('div', {}, el('h3', {}, 'Worth fixing, but not blocking'),
          el('div', { class: 'list' }, report.warnings.map((w) => notice(w, 'warn'))))
        : null));

    if (report.style && report.style.comparable) {
      host.append(card('Does it sound like you?',
        el('p', { class: 'hint' }, report.style.note),
        el('div', { class: 'table-wrap' }, el('table', {},
          el('thead', {}, el('tr', {}, ['Feature', 'Your writing', 'This draft', 'Difference']
            .map((h) => el('th', {}, h)))),
          el('tbody', {}, Object.entries(report.style.metrics).map(([name, values]) =>
            el('tr', {},
              el('td', {}, name.replace(/_/g, ' ')),
              el('td', {}, values.target),
              el('td', {}, values.draft),
              el('td', {}, report.style.drifted.includes(name)
                ? chip(`${values.difference > 0 ? '+' : ''}${values.difference}`, 'warn')
                : `${values.difference > 0 ? '+' : ''}${values.difference}`))))))));
    }

    host.append(groundingCard());
    host.append(proofCardResearch());

    host.append(el('button', { class: 'button', onclick: () => go('export') },
      'Next: export →'));
  }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));

  return el('section', { class: 'stack' }, el('h1', {}, 'Check'), host);
}

/* The paper's own grammar and spelling pass. `writing/proof.py` was written and
   tested and then imported by nothing at all — the charting tab got its
   proofreader wired up and the research side, which is where "zero grammatical
   errors" was actually asked for, did not. */

function proofCardResearch() {
  const project = state.project;
  const host = el('div', { class: 'stack' }, el('p', { class: 'hint' }, 'Checking…'));

  api(`/api/projects/${project.project_id}/proof`).then((report) => {
    host.replaceChildren();

    if (!report.available) {
      host.append(notice(report.note, 'warn'));
      host.append(el('details', {}, el('summary', {}, 'Why not Grammarly?'),
        el('p', { class: 'hint' }, report.grammarly.summary),
        el('p', { class: 'hint' }, report.grammarly.manual_route),
        el('pre', { class: 'macro-output' }, report.grammarly.in_pipeline)));
      return;
    }

    host.append(notice(`${report.engine} checked ${report.checked_words.toLocaleString()} `
      + `words across the claim ledger.`,
      report.issues.length ? 'warn' : 'good'));

    if (!report.issues.length) {
      host.append(notice('No spelling or grammar issues found.', 'good'));
    } else {
      const counts = Object.entries(report.by_category)
        .sort((a, b) => b[1] - a[1]);
      host.append(el('div', { class: 'chip-row' },
        counts.map(([name, count]) => chip(`${name}: ${count}`))));
      host.append(el('div', { class: 'list' }, report.issues.map((issue) =>
        el('div', { class: 'flag flag-warn' },
          el('div', { class: 'flag-head' },
            chip(issue.category || 'issue'),
            el('span', { class: 'flag-code' },
              `${issue.section || 'body'} · ${issue.claim_id || ''}`)),
          el('p', { class: 'flag-message' }, issue.message),
          issue.context ? el('p', { class: 'flag-excerpt' }, issue.context) : null,
          issue.replacements.length
            ? el('p', { class: 'flag-suggestion' },
              `Suggested: ${issue.replacements.slice(0, 4).join(' · ')}`)
            : null))));
    }

    host.append(el('p', { class: 'hint' }, report.note));
  }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));

  return card('Spelling and grammar', host);
}

function groundingCard() {
  const project = state.project;
  const host = el('div', { class: 'stack' }, el('p', { class: 'hint' }, 'Anchoring…'));

  api(`/api/projects/${project.project_id}/grounding`).then((report) => {
    host.replaceChildren();

    if (!report.ingested.length) {
      host.append(notice('No full text has been ingested, so no claim could be '
        + 'anchored to the paragraph it came from. Read the articles in on the '
        + 'Full text screen and this becomes a real check rather than a blank '
        + 'one.', 'warn'));
      host.append(el('button', { class: 'button button-quiet', onclick: () => go('fulltext') },
        'Go to Full text'));
      return;
    }

    const kind = { 'anchored': 'good', 'verbatim overlap': 'bad',
      'not found in source': 'bad', 'no full text': 'warn' };

    host.append(statBlock([
      [report.checked, 'claims checked'],
      [report.unsupported.length, 'not found in source'],
      [report.verbatim.length, 'verbatim overlap'],
      [report.unchecked.length, 'no full text yet'],
    ]));

    if (report.unsupported.length) {
      host.append(notice('A claim not found in the source it cites is either '
        + 'attributed to the wrong article or was never in any article. Both '
        + 'read identically in a finished draft, which is why this check '
        + 'exists.', 'bad'));
    }

    host.append(el('div', { class: 'list' }, report.claims.map((row) =>
      el('div', { class: 'row' },
        el('div', { class: 'row-head' },
          el('span', { class: 'row-title' }, row.text),
          chip(row.status, kind[row.status] || '')),
        el('div', { class: 'stack' },
          el('p', { class: 'hint' }, row.detail),
          row.matches.length
            ? el('div', { class: 'table-wrap' }, el('table', {},
              el('thead', {}, el('tr', {}, ['Source', 'Where', 'Match', 'The paragraph']
                .map((h) => el('th', {}, h)))),
              el('tbody', {}, row.matches.map((match) => el('tr', {},
                el('td', {}, match.label || match.work_key),
                el('td', {}, el('code', { class: 'anchor' }, match.anchor),
                  match.section ? el('span', { class: 'hint' }, ` ${match.section}`) : null),
                el('td', {}, chip(match.basis,
                  match.basis === 'verbatim' ? 'bad'
                    : match.basis === 'close paraphrase' ? 'good' : 'warn')),
                el('td', {}, el('span', { class: 'quoted-source' }, match.excerpt)))))))
            : null)))));

    if (report.not_ingested.length) {
      host.append(notice(`Cited but not ingested: ${report.not_ingested.join(', ')}. `
        + 'Claims resting on those sources were not checked — which is not the '
        + 'same as their having passed.', 'warn'));
    }

    host.append(notice(report.note));
  }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));

  return card('Is every claim actually in the source it cites?', host);
}

/* -------------------------------------------------------------------- export */

function viewExport() {
  const project = state.project;
  const page = project.title_page || {};

  const inputs = {
    variant: el('select', {},
      el('option', { value: 'student', selected: page.variant === 'student' }, 'Student paper'),
      el('option', { value: 'professional', selected: page.variant === 'professional' }, 'Professional paper')),
    title: el('input', { type: 'text', value: page.title || project.topic }),
    authors: el('input', { type: 'text', value: (page.authors || []).join('; ') }),
    affiliations: el('input', { type: 'text', value: (page.affiliations || []).join('; ') }),
    course: el('input', { type: 'text', value: page.course || '' }),
    instructor: el('input', { type: 'text', value: page.instructor || '' }),
    due_date: el('input', { type: 'text', value: page.due_date || '' }),
    running_head: el('input', { type: 'text', value: page.running_head || '', maxlength: '50' }),
    author_note: el('textarea', {}, page.author_note || ''),
  };

  const abstractInput = el('textarea', { rows: '5' }, '');
  const keywordsInput = el('input', { type: 'text',
    value: (project._derived.suggested_keywords || []).join(', ') });
  const fontSelect = el('select', {}, state.config.fonts.map((f) =>
    el('option', { value: f, selected: f === state.config.settings.default_font }, f)));
  const wantPaper = el('input', { type: 'checkbox', checked: true });
  const wantAudit = el('input', { type: 'checkbox', checked: true });
  const wantSlides = el('input', { type: 'checkbox' });
  const forceBox = el('input', { type: 'checkbox' });

  const files = el('div', { class: 'list' });
  const refreshFiles = () => api(`/api/projects/${project.project_id}/files`)
    .then((data) => {
      files.replaceChildren();
      if (!data.files.length) {
        files.append(el('p', { class: 'hint' }, 'Nothing exported yet.'));
        return;
      }
      for (const file of data.files) {
        files.append(el('div', { class: 'row' },
          el('div', { class: 'row-head' },
            el('a', {
              href: `/api/projects/${project.project_id}/files/${encodeURIComponent(file.name)}?token=${encodeURIComponent(state.token)}`,
              class: 'row-title',
            }, file.name),
            chip(`${Math.round(file.bytes / 1024)} KB`))));
      }
    }).catch(() => { /* nothing exported yet */ });
  refreshFiles();

  return el('section', { class: 'stack' },
    el('h1', {}, 'Export'),
    card('Title page',
      el('p', { class: 'hint' }, 'APA 7 distinguishes student and professional '
        + 'title pages. A student page carries the course, instructor and due '
        + 'date; a professional page carries an author note and a running head.'),
      field('Paper type', inputs.variant),
      field('Title', inputs.title),
      field('Author(s)', inputs.authors, 'separate with a semicolon'),
      field('Affiliation(s)', inputs.affiliations, 'Department, Institution'),
      field('Course', inputs.course),
      field('Instructor', inputs.instructor),
      field('Due date', inputs.due_date),
      field('Running head', inputs.running_head, 'professional papers only; 50 characters maximum'),
      field('Author note', inputs.author_note, 'professional papers only'),
      el('button', {
        class: 'button button-quiet',
        onclick: () => guard(async () => {
          const result = await post(`/api/projects/${project.project_id}/settings`, {
            title_page: {
              variant: inputs.variant.value,
              title: inputs.title.value,
              authors: inputs.authors.value.split(';').map((s) => s.trim()).filter(Boolean),
              affiliations: inputs.affiliations.value.split(';').map((s) => s.trim()).filter(Boolean),
              course: inputs.course.value,
              instructor: inputs.instructor.value,
              due_date: inputs.due_date.value,
              running_head: inputs.running_head.value,
              author_note: inputs.author_note.value,
            },
          });
          state.project = result.project;
          toast('Title page saved.');
        }),
      }, 'Save title page')),
    card('Documents',
      field('Abstract', abstractInput, 'APA 7 §2.9: 150–250 words. Leave blank to omit.'),
      field('Keywords', keywordsInput, 'suggested from the MeSH terms of your cited sources'),
      field('Typeface', fontSelect, 'APA 7 §2.19 pairs each typeface with its own size'),
      el('label', { class: 'inline' }, wantPaper, 'APA 7 paper (.docx)'),
      el('label', { class: 'inline' }, wantAudit, 'Rationale and source mapping document (.docx)'),
      el('label', { class: 'inline' }, wantSlides, 'Slide deck (.pptx)'),
      el('label', { class: 'inline' }, forceBox,
        'Export even with citation defects (produces a draft for your own review)'),
      el('button', {
        class: 'button',
        onclick: (event) => guard(async () => {
          event.target.disabled = true;
          try {
            const result = await post(`/api/projects/${project.project_id}/export`, {
              paper: wantPaper.checked, audit: wantAudit.checked,
              slides: wantSlides.checked, abstract: abstractInput.value,
              keywords: keywordsInput.value.split(',').map((s) => s.trim()).filter(Boolean),
              font: fontSelect.value, force: forceBox.checked,
            });
            if (!result.exported.length) {
              for (const blocker of result.blockers) toast(blocker, true);
              toast(result.message || 'Export stopped.', true);
            } else {
              toast(`Exported ${result.exported.length} file(s) to ${result.directory}.`);
            }
            refreshFiles();
          } finally {
            event.target.disabled = false;
          }
        }),
      }, 'Export')),
    card('Files', files),
    figuresCard(),
    prismaCard());
}

/* ---------------------------------------------------------------------- APA 7 */

/* The formatting is the point of this application, and it was the least
   visible thing in it: four thousand lines across app/apa/, cited to the
   manual section by section, surfaced only as a .docx at the very end. You met
   PICO(T) first and the APA work never — which is backwards. This screen puts
   the rules, the current setup and the citations *this* project will actually
   produce in front of you. */

function viewApa() {
  /* Readable with no project open. The rules, the heading levels and the
     worked examples are the same whether or not a paper has been started, and
     making someone create a project before they could read the formatting was
     the same mistake as hiding the formatting behind an export button. With a
     project open the screen adds what *this* paper does; without one it is
     still the whole formatting reference. */
  const project = state.project;
  const path = !state.project
    ? '/api/apa'
    : `/api/projects/${project.project_id}/apa`;

  const host = el('div', { class: 'stack' }, el('p', { class: 'hint' }, 'Loading…'));

  const refresh = () => api(path)
    .then((report) => {
      host.replaceChildren();

      if (report.scope === 'project') {
        host.append(card('This paper’s setup',
          settingsTable(report.setup),
          el('p', { class: 'hint' }, 'Change the paper type, title page and '
            + 'typeface on the Export screen — they are written into the '
            + 'document, not applied afterwards.')));

        host.append(card('Still to supply',
          report.outstanding.length
            ? el('div', { class: 'list' },
              report.outstanding.map((line) => notice(line, 'warn')))
            : notice('Nothing outstanding: the title page, author and sources '
              + 'APA requires are all present.', 'good'),
          el('p', { class: 'hint' }, 'Listed as what is missing rather than as a '
            + 'score. A percentage invites treating 90% as good enough when the '
            + 'missing tenth is the title.')));

        if (report.previews.length) {
          host.append(card('What your citations will look like',
            el('p', { class: 'hint' }, 'Generated by the same engine that writes '
              + 'the document, from the sources this project actually cites — so '
              + 'what you see here is what lands in the .docx.'),
            el('div', { class: 'list' }, report.previews.map(citationRow))));
        } else {
          host.append(card('What your citations will look like',
            notice('No source is cited yet. Add sources and attach them to '
              + 'claims, and the exact in-text citations and reference entries '
              + 'will appear here.', 'warn')));
        }
      } else {
        host.append(card('The defaults every paper starts from',
          settingsTable(report.setup),
          el('p', { class: 'hint' }, 'Open a project to see this paper’s own '
            + 'setup, its outstanding items, and the citations its sources '
            + 'actually produce.')));
      }

      /* Worked examples of the reference types that get marked wrong most
         often. Rendered by the same engine, so they are a live demonstration
         rather than a copied-out list: if the engine regresses, these break
         here before a paper does. */
      host.append(card('Worked examples of the nine hardest reference types',
        el('p', { class: 'hint' }, 'Not sources — nothing here is retrievable '
          + 'and nothing here enters a project. They are run through the same '
          + 'citation engine as your own references, so what they show is what '
          + 'the code does.'),
        el('div', { class: 'list' }, report.examples.map((row) =>
          citationRow(row, row.point)))));

      host.append(card('The five heading levels (§2.27)',
        el('div', { class: 'table-wrap' }, el('table', {},
          el('thead', {}, el('tr', {}, ['Level', 'Format', 'Example']
            .map((h) => el('th', {}, h)))),
          el('tbody', {}, report.headings.map((row) => el('tr', {},
            el('td', {}, `Level ${row.level}`),
            el('td', {}, row.format),
            el('td', {}, el('span', { class: `apa-h${row.level}` },
              headingExample(row.level))))))))));

      host.append(card('Approved typefaces (§2.19)',
        el('p', { class: 'hint' }, 'APA names a short list and the exporter '
          + 'refuses anything outside it, at the size the manual gives for that '
          + 'face — a 12 pt Calibri paper is not an APA paper.'),
        el('div', { class: 'list' }, report.fonts.map((font) =>
          el('div', { class: 'row' }, el('span', {}, font))))));

      const groups = [];
      for (const rule of report.rules) {
        let group = groups.find((g) => g.name === rule.group);
        if (!group) { group = { name: rule.group, rules: [] }; groups.push(group); }
        group.rules.push(rule);
      }
      host.append(card('Every rule the exporter enforces',
        el('p', { class: 'hint' }, report.note),
        el('div', { class: 'stack' }, groups.map((group) =>
          el('div', { class: 'subcard' },
            el('h3', {}, group.name.replace(/^./, (c) => c.toUpperCase())),
            el('div', { class: 'table-wrap' }, el('table', {},
              el('tbody', {}, group.rules.map((rule) => el('tr', {},
                el('th', {}, rule.rule),
                el('td', {}, rule.detail),
                el('td', {}, el('span', { class: 'hint' }, rule.section))))))))))));

      if (project) {
        host.append(el('button', { class: 'button', onclick: () => go('export') },
          'Go to Export →'));
      }
    }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));
  refresh();

  return el('section', { class: 'stack' },
    el('h1', {}, 'APA 7'),
    notice('The document is built to the Publication Manual, 7th edition, and '
      + 'every rule below is enforced by the exporter rather than left as '
      + 'advice. The margins, the double spacing, the hanging indent and the '
      + 'page-number field are written into the .docx itself, and the tests '
      + 'assert them against the saved file rather than against the builder.'),
    host);
}

function settingsTable(rows) {
  return el('div', { class: 'table-wrap' }, el('table', {},
    el('thead', {}, el('tr', {}, ['Setting', 'Value', 'Manual']
      .map((h) => el('th', {}, h)))),
    el('tbody', {}, rows.map((row) => el('tr', {},
      el('td', {}, row.name),
      el('td', {}, row.value),
      el('td', {}, el('span', { class: 'hint' }, row.section)))))));
}

/* One source rendered the three ways it appears in a paper. `point` is the
   rule a worked example exists to demonstrate; a project's own sources have
   no such note and pass nothing. */
function citationRow(row, point) {
  return el('div', { class: 'row' },
    el('div', { class: 'row-head' },
      el('span', { class: 'row-title' }, row.label)),
    point ? el('p', { class: 'hint' }, point) : null,
    el('div', { class: 'stack' },
      el('div', { class: 'table-wrap' }, el('table', {},
        el('tbody', {},
          el('tr', {}, el('th', {}, 'Parenthetical'),
            el('td', {}, el('code', {}, row.parenthetical))),
          el('tr', {}, el('th', {}, 'Narrative'),
            el('td', {}, el('code', {}, `${row.narrative} (…)`))),
          el('tr', {}, el('th', {}, 'Reference'),
            el('td', {}, el('span', { class: 'reference-entry' },
              row.reference))))))));
}

function headingExample(level) {
  return [
    'Method',
    'Participants and Setting',
    'Inclusion Criteria',
    'Data extraction.',
    'Second reviewer.',
  ][level - 1] || 'Heading';
}

/* -------------------------------------------------------------------- figures */

/* The figure builder. `apa/figures.py` had a forest plot, an incidence curve
   and two bar charts — every figure type the specification named, all with a
   colourblind-safe palette and greyscale-safe secondary encoding — and nothing
   in the interface could reach any of them. Only the level-distribution chart
   had a button. A feature nobody can click is a feature that does not exist. */

const FIGURE_KINDS = [
  ['forest', 'Forest plot — odds or risk ratios with confidence intervals'],
  ['line', 'Incidence curve — a measure over time'],
  ['bar', 'Bar chart — one value per category'],
  ['grouped_bar', 'Grouped bar chart — several series per category'],
];

const figureState = { kind: 'forest', rows: 3, series: 2, output: null };

function repeatRow(...cells) {
  return el('div', { class: 'repeat-row' }, ...cells);
}

function numberInput(placeholder) {
  return el('input', { type: 'text', inputmode: 'decimal', placeholder });
}

function figuresCard() {
  const project = state.project;
  const host = el('div', { class: 'stack' });

  const kindSelect = el('select', {
    onchange: () => { figureState.kind = kindSelect.value; paint(); },
  }, FIGURE_KINDS.map(([value, label]) =>
    el('option', { value, selected: figureState.kind === value }, label)));

  const titleInput = el('input', { type: 'text', placeholder: 'Odds of falling by staffing ratio' });
  const captionInput = el('input', { type: 'text', placeholder: 'optional caption for the audit document' });
  const output = el('div', { class: 'stack' });

  const existing = el('div', { class: 'list' });
  const refreshFigures = () => api(`/api/projects/${project.project_id}/figures`)
    .then((data) => {
      existing.replaceChildren();
      if (!data.figures.length) {
        existing.append(el('p', { class: 'hint' }, 'No figures attached yet. '
          + 'Anything built here is placed in the paper as a numbered APA '
          + 'figure and on a slide in the deck.'));
        return;
      }
      for (const figure of data.figures) {
        existing.append(el('div', { class: 'row' },
          el('div', { class: 'row-head' },
            el('span', { class: 'row-title' }, figure.title || figure.kind),
            chip(figure.kind)),
          el('div', { class: 'stack' },
            el('img', {
              src: `/api/projects/${project.project_id}/files/${encodeURIComponent(figure.path)}?token=${encodeURIComponent(state.token)}`,
              alt: figure.title || 'Figure',
              class: 'figure-preview',
            }),
            el('p', { class: 'hint' }, figure.note))));
      }
    }).catch(() => { /* nothing built yet */ });
  refreshFigures();

  const build = (payload) => guard(async () => {
    const out = await post(`/api/projects/${project.project_id}/figure`,
      Object.assign({ title: titleInput.value, caption: captionInput.value },
        payload));
    output.replaceChildren(
      el('img', {
        src: `/api/projects/${project.project_id}/files/${encodeURIComponent(out.path)}?token=${encodeURIComponent(state.token)}`,
        alt: titleInput.value || 'Figure',
        class: 'figure-preview',
      }),
      notice(out.placement, 'good'),
      el('p', { class: 'hint' }, 'Figure note: ' + out.note),
      out.table ? el('div', { class: 'table-wrap' }, el('table', {},
        el('thead', {}, el('tr', {}, out.table.headers.map((h) => el('th', {}, h)))),
        el('tbody', {}, out.table.rows.map((row) =>
          el('tr', {}, row.map((cell) => el('td', {}, cell))))))) : null,
      el('p', { class: 'hint' }, 'APA 7 asks that a figure not be the only '
        + 'place a number appears. The table above is the same data in text, '
        + 'ready to paste.'));
    refreshFigures();
  });

  function paint() {
    host.replaceChildren();
    const kind = figureState.kind;

    if (kind === 'forest') {
      const measure = el('select', {},
        ['Odds ratio', 'Risk ratio', 'Hazard ratio', 'Mean difference',
          'Standardised mean difference'].map((m) => el('option', { value: m }, m)));
      const rows = [];
      const rowHost = el('div', { class: 'stack' });
      const addRow = () => {
        const cells = {
          label: el('input', { type: 'text', placeholder: 'Smith et al. (2023)' }),
          estimate: numberInput('0.62'),
          lower: numberInput('0.45'),
          upper: numberInput('0.85'),
          weight: numberInput('weight %'),
          subgroup: el('input', { type: 'text', placeholder: 'subgroup (optional)' }),
        };
        rows.push(cells);
        rowHost.append(repeatRow(cells.label, cells.estimate, cells.lower,
          cells.upper, cells.weight, cells.subgroup));
      };
      for (let i = 0; i < 3; i += 1) addRow();

      host.append(
        field('Measure', measure),
        el('p', { class: 'hint' }, 'Study, estimate, lower and upper confidence '
          + 'limit, weight, subgroup. A ratio measure is drawn on a log scale '
          + 'with the line of no effect at 1, which is what makes a forest plot '
          + 'readable.'),
        rowHost,
        el('button', { class: 'button button-quiet', onclick: addRow }, '+ Another study'),
        el('button', {
          class: 'button',
          onclick: () => build({
            kind: 'forest',
            measure: measure.value,
            estimates: rows
              .filter((r) => r.label.value.trim() && r.estimate.value.trim())
              .map((r) => ({
                label: r.label.value, estimate: r.estimate.value,
                lower: r.lower.value, upper: r.upper.value,
                weight: r.weight.value || 0, subgroup: r.subgroup.value,
              })),
          }),
        }, 'Draw the forest plot'));

    } else if (kind === 'bar') {
      const categories = el('input', { type: 'text', placeholder: 'Ward A, Ward B, Ward C' });
      const values = el('input', { type: 'text', placeholder: '3.1, 4.8, 2.2' });
      const yLabel = el('input', { type: 'text', placeholder: 'Falls per 1,000 patient-days' });
      host.append(
        field('Categories', categories, 'separate with commas'),
        field('Values', values, 'one per category, in the same order'),
        field('Y-axis label', yLabel),
        el('button', {
          class: 'button',
          onclick: () => build({
            kind: 'bar',
            categories: splitList(categories.value),
            values: splitList(values.value),
            y_label: yLabel.value,
          }),
        }, 'Draw the bar chart'));

    } else {
      const xLabels = el('input', { type: 'text', placeholder: 'Q1, Q2, Q3, Q4' });
      const xLabel = el('input', { type: 'text', placeholder: 'Quarter' });
      const yLabel = el('input', { type: 'text', placeholder: 'Incidence per 1,000 patient-days' });
      const seriesRows = [];
      const seriesHost = el('div', { class: 'stack' });
      const addSeries = () => {
        const cells = {
          name: el('input', { type: 'text', placeholder: 'Intervention' }),
          values: el('input', { type: 'text', placeholder: '4.1, 3.6, 2.9, 2.4' }),
        };
        seriesRows.push(cells);
        seriesHost.append(repeatRow(cells.name, cells.values));
      };
      addSeries(); addSeries();

      host.append(
        field(kind === 'line' ? 'Time points' : 'Categories', xLabels,
          'separate with commas'),
        kind === 'line' ? field('X-axis label', xLabel) : null,
        field('Y-axis label', yLabel),
        el('p', { class: 'hint' }, 'Each series is a name and its values, in '
          + 'the same order as the labels above. Every series gets a distinct '
          + 'marker and line style as well as a colour, so the figure survives '
          + 'being printed in greyscale.'),
        seriesHost,
        el('button', { class: 'button button-quiet', onclick: addSeries }, '+ Another series'),
        el('button', {
          class: 'button',
          onclick: () => build({
            kind,
            x_labels: splitList(xLabels.value),
            categories: splitList(xLabels.value),
            x_label: xLabel.value,
            y_label: yLabel.value,
            series: seriesRows
              .filter((s) => s.name.value.trim() && s.values.value.trim())
              .map((s) => [s.name.value, splitList(s.values.value)]),
          }),
        }, kind === 'line' ? 'Draw the incidence curve' : 'Draw the grouped bars'));
    }
  }
  paint();

  return card('Figures',
    el('p', { class: 'hint' }, 'Every figure is drawn at 300 dpi with a '
      + 'colourblind-safe palette, and every series carries a second encoding — '
      + 'a marker shape or a line style — so it is still readable in greyscale '
      + 'and in print. Each one is attached to the project and placed in the '
      + 'paper as a numbered APA figure with its note beneath.'),
    field('Figure type', kindSelect),
    field('Title', titleInput),
    field('Caption', captionInput, 'appears in the audit document'),
    host,
    output,
    el('h3', {}, 'Evidence levels'),
    el('p', { class: 'hint' }, 'A bar chart of the JBI/AACN levels across the '
      + 'included studies, built from the project rather than typed in.'),
    el('button', {
      class: 'button button-quiet',
      onclick: () => guard(async () => {
        const out = await post(`/api/projects/${project.project_id}/figure/levels`, {});
        output.replaceChildren(
          el('img', {
            src: `/api/projects/${project.project_id}/files/${encodeURIComponent(out.path)}?token=${encodeURIComponent(state.token)}`,
            alt: 'Distribution of evidence levels',
            class: 'figure-preview',
          }),
          el('p', { class: 'hint' }, 'Figure note: ' + out.note));
        refreshFigures();
      }),
    }, 'Chart the evidence levels'),
    el('h3', {}, 'Attached to this paper'),
    existing);
}

function splitList(text) {
  return String(text || '').split(',').map((s) => s.trim()).filter(Boolean);
}

/* ------------------------------------------------------------------ settings */

function viewSettings() {
  const config = state.config.settings;
  const emailInput = el('input', { type: 'email', value: config.contact_email || '' });
  const samples = el('div', { class: 'list' });

  const refreshSamples = () => api('/api/samples').then((data) => {
    samples.replaceChildren();
    if (!data.samples.length) {
      samples.append(el('p', { class: 'hint' }, 'No samples yet.'));
      return;
    }
    for (const sample of data.samples) {
      samples.append(el('div', { class: 'row' },
        el('div', { class: 'row-head' },
          el('span', { class: 'row-title' }, sample.name),
          chip(`${sample.words.toLocaleString()} words`,
            sample.words >= 1500 ? 'good' : 'warn')),
        el('div', { class: 'row-actions' },
          el('button', {
            class: 'button button-quiet button-small',
            onclick: () => guard(async () => {
              await api(`/api/samples/${encodeURIComponent(sample.name)}`, { method: 'DELETE' });
              refreshSamples();
            }),
          }, 'Remove'))));
    }
  }).catch(() => {});
  refreshSamples();

  const sampleName = el('input', { type: 'text', placeholder: 'nurs5100-paper' });
  const sampleFile = el('input', { type: 'file', accept: '.txt,.md' });
  const sampleText = el('textarea', { rows: '6', placeholder: 'or paste your own writing here' });

  return el('section', { class: 'stack' },
    el('h1', {}, 'Settings'),
    accessNotice(),

    card('Contact email',
      el('p', { class: 'hint' }, 'NCBI’s usage policy asks every client to '
        + 'identify itself, Crossref and OpenAlex give faster service to clients '
        + 'that do, and Unpaywall requires an address. It is sent to those APIs '
        + 'in the User-Agent header and nowhere else.'),
      field('Email', emailInput),
      el('button', {
        class: 'button button-quiet',
        onclick: () => guard(async () => {
          await post('/api/config/general', { contact_email: emailInput.value });
          state.config = await api('/api/config');
          toast('Saved.');
          render();
        }),
      }, 'Save')),

    card('API keys',
      el('p', { class: 'hint' }, `Stored in ${config.keyring_available
        ? 'your operating system keychain' : 'a .env file with owner-only permissions'}`
        + ', never in the repository. Every key is optional.'),
      el('div', { class: 'list' }, config.keys.map((key) => {
        const input = el('input', { type: 'password', placeholder: key.configured ? key.hint : 'not set' });
        return el('div', { class: 'row' },
          el('div', { class: 'row-head' },
            el('span', { class: 'row-title' }, key.label),
            key.configured ? chip('✓ set', 'good') : chip('not set'),
            el('a', { href: key.get, target: '_blank', rel: 'noreferrer' }, 'get a key')),
          el('div', { class: 'row-meta' }, `Enables: ${key.enables}`),
          el('div', { class: 'row-meta' }, `Without it: ${key.without}`),
          el('div', { class: 'card-row' }, field('Key', input),
            el('button', {
              class: 'button button-quiet button-small',
              onclick: () => guard(async () => {
                const result = await post('/api/config/key',
                  { name: key.name, value: input.value });
                input.value = '';
                state.config = await api('/api/config');
                toast(`Saved to ${result.stored}.`);
                render();
              }),
            }, 'Save')));
      }))),

    card('Writing samples',
      el('p', { class: 'hint' }, 'Your own finished academic writing, so the '
        + 'drafting step can match your sentence shapes, hedging and vocabulary. '
        + 'Aim for 1,500 words or more in total — below that the measurements are '
        + 'noise. Use only text you wrote.'),
      samples,
      field('Name', sampleName),
      field('File', sampleFile, '.txt or .md'),
      field('Or paste', sampleText),
      el('button', {
        class: 'button button-quiet',
        onclick: () => guard(async () => {
          const form = new FormData();
          form.append('name', sampleName.value || 'sample');
          if (sampleFile.files.length) form.append('file', sampleFile.files[0]);
          form.append('text', sampleText.value);
          await api('/api/samples', { method: 'POST', body: form });
          sampleText.value = '';
          sampleName.value = '';
          refreshSamples();
          toast('Sample saved.');
        }),
      }, 'Add sample')),

    grammarlyCard(),

    card('Where things are',
      el('div', { class: 'table-wrap' }, el('table', {},
        el('tbody', {},
          [['Projects', config.data_dir], ['Exports', config.export_dir],
            ['Secrets', config.keyring_available ? 'OS keychain' : (config.env_file || 'not written yet')]]
            .map(([label, value]) => el('tr', {}, el('th', {}, label), el('td', {}, value))))))));
}

/* You asked for the grammar checking to be "maybe linked to my Grammarly". It
   cannot be, and the honest answer with the working alternative belongs where
   you would go looking for it rather than buried in a README. */

/* Where this is actually reachable. The old text said "Localhost only — not
   reachable from your network" whenever the bind address was 127.0.0.1, which
   is exactly what it is inside a GitHub Codespace while the app is in fact
   served over HTTPS on a forwarded public hostname. A reassurance that is false
   is worse than none. */

function accessNotice() {
  const access = (state.config && state.config.access) || {};
  const settings = state.config.settings;

  if (access.codespace) {
    return el('div', { class: 'stack' },
      notice(`Served in a GitHub Codespace at ${access.url} — not on localhost, `
        + 'even though it binds to 127.0.0.1 inside the container.', 'warn'),
      notice('Who can reach it is set by the port’s visibility in the Ports '
        + 'panel. Private, the default, means your GitHub account only — that '
        + 'is the setting you want. Public means anyone with the URL, leaving '
        + 'the session token as the only protection, and a token in a URL leaks '
        + 'into history and logs.', 'warn'),
      notice('Your API keys and projects live in the codespace and go when it '
        + 'does. Export anything you want to keep.'));
  }

  if (access.local_only !== false) {
    return notice(`Bound to ${settings.host}:${settings.port}. Localhost only — `
      + 'not reachable from your network. The security boundary is your '
      + 'operating system account: anything running as you can read the project '
      + 'data and the API keys.');
  }

  const named = access.allowed_hosts || [];
  return el('div', { class: 'stack' },
    notice(`Bound to ${settings.host}:${settings.port}. ⚠ Not localhost. `
      + 'This is reachable from your network — put an authenticating proxy in '
      + 'front of it.', 'bad'),
    named.length
      ? notice(`Answering to ${named.join(', ')} as well as localhost. Any `
        + 'other address is refused with a 421 — the bind decides which '
        + 'interface accepts a connection, this list decides who is answered.')
      : notice('No host names are allowlisted, so a browser on another machine '
        + 'is refused with a 421 even though the port is open. Set '
        + 'RESEARCH_SUITE_ALLOWED_HOSTS to the address you type — for example '
        + 'RESEARCH_SUITE_ALLOWED_HOSTS=pi-3bplus.local — and restart.', 'warn'));
}

function grammarlyCard() {
  const host = el('div', { class: 'stack' }, el('p', { class: 'hint' }, 'Loading…'));

  api('/api/grammarly').then((status) => {
    host.replaceChildren(
      notice(status.summary, 'warn'),
      el('h3', {}, 'What to do instead'),
      el('p', { class: 'hint' }, status.manual_route),
      el('h3', {}, 'What runs here'),
      el('pre', { class: 'macro-output' }, status.in_pipeline),
      el('h3', {}, 'Every alternative that returns something actionable'),
      el('div', { class: 'table-wrap' }, el('table', {},
        el('thead', {}, el('tr', {}, ['Tool', 'Licence', 'Returns', 'Runs locally']
          .map((h) => el('th', {}, h)))),
        el('tbody', {}, status.alternatives.map((row) => el('tr', {},
          el('td', {}, row.name),
          el('td', {}, row.licence),
          el('td', {}, row.returns),
          el('td', {}, row.local ? chip('yes', 'good') : chip('sends your draft out', 'warn'))))))));
  }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));

  return card('Grammarly', host);
}

/* ---------------------------------------------------------------- bootstrap */

document.getElementById('nav').addEventListener('click', (event) => {
  const view = event.target.dataset && event.target.dataset.view;
  if (view) go(view);
});
document.getElementById('switch-project').addEventListener('click', () => {
  state.project = null;
  go('projects');
});

takeToken();
(async () => {
  // Deliberately not wrapped in guard(): guard turns a failure into a toast
  // that fades, and this failure has to stay on screen — it is the one the
  // user most needs to read, and every view depends on the result.
  try {
    state.config = await api('/api/config');
    state.configError = '';
    for (const warning of state.config.warnings) toast(warning, true);
  } catch (error) {
    state.configError = error.message || String(error);
    // A token the server refused must not be replayed on the next reload.
    if (/token/i.test(state.configError)) forgetToken();
  }
  render();
})();

/* ============================================================ question framing */

/*
 * The PICO(T) / SPIDER builder. Concept blocks in, database-specific Boolean
 * strings out. The strings are shown rather than run, for every database except
 * the two the tool can actually query, because a systematic review is appraised
 * on the string you ran and pasting one you can see is the honest path.
 */
const questionState = {
  framework: 'pico',
  question_text: '',
  years: 5,
  languages: [],
  humans_only: true,
  peer_reviewed_only: true,
  concepts: {},
  frameworks: null,
  report: null,
};

function viewQuestion() {
  const section = el('section', { class: 'stack' }, el('h1', {}, 'Frame the question'));

  if (!questionState.frameworks) {
    guard(async () => {
      const data = await api('/api/frameworks');
      questionState.frameworks = data.frameworks;
      render();
    });
    return el('section', { class: 'stack' }, el('p', { class: 'hint' }, 'Loading…'));
  }

  const framework = questionState.frameworks.find(
    (f) => f.key === questionState.framework) || questionState.frameworks[0];

  const picker = el('select', {
    onchange: (event) => {
      questionState.framework = event.target.value;
      questionState.concepts = {};
      questionState.report = null;
      render();
    },
  }, questionState.frameworks.map((f) =>
    el('option', { value: f.key, selected: f.key === questionState.framework },
      f.label)));

  const questionText = el('input', {
    type: 'text',
    placeholder: 'Does hourly nurse rounding reduce inpatient falls in adult acute care?',
    oninput: (event) => { questionState.question_text = event.target.value; },
  });
  questionText.value = questionState.question_text;

  const years = el('input', {
    type: 'number', min: 1, max: 50,
    oninput: (event) => {
      questionState.years = event.target.value ? Number(event.target.value) : null;
    },
  });
  years.value = questionState.years || '';

  const output = el('div', {});

  const build = () => guard(async () => {
    const payload = {
      framework: questionState.framework,
      question_text: questionState.question_text,
      years: questionState.years,
      languages: questionState.languages,
      humans_only: questionState.humans_only,
      peer_reviewed_only: questionState.peer_reviewed_only,
      concepts: questionState.concepts,
    };
    const report = await post('/api/pico/translate', payload);
    questionState.report = report;
    output.replaceChildren(questionReport(report));
  });

  section.append(
    card('Framework',
      el('p', { class: 'hint' }, framework.use_when),
      el('div', { class: 'grid-fields' },
        field('Framework', picker),
        field('Publication window', years, 'years; leave blank for none')),
      field('Question in prose', questionText,
        'Optional. It goes into the methods section alongside the concept table.')),
  );

  for (const slot of framework.slots) {
    const stored = questionState.concepts[slot.key]
      || (questionState.concepts[slot.key] = { terms: [], mesh: [], expand: false });

    const terms = el('textarea', {
      rows: 2,
      placeholder: 'one term per line, or comma separated',
      oninput: (event) => {
        stored.terms = event.target.value
          .split(/[,\n;]/).map((s) => s.trim()).filter(Boolean);
      },
    });
    terms.value = (stored.terms || []).join('\n');

    const expand = el('input', { type: 'checkbox' });
    expand.checked = !!stored.expand;
    expand.addEventListener('change', () => {
      stored.expand = expand.checked;
    });

    section.append(card(slot.label + (slot.required ? ' *' : ''),
      el('p', { class: 'hint' }, slot.guidance),
      field('Terms', terms),
      el('label', { class: 'inline-check' }, expand,
        ' Expand with synonyms and MeSH headings from the built-in thesaurus'),
      el('button', {
        class: 'button button-quiet button-small',
        onclick: () => guard(async () => {
          if (!(stored.terms || []).length) {
            toast('Enter a term first.'); return;
          }
          const found = await post('/api/pico/expand', { term: stored.terms[0] });
          if (!found.synonyms.length && !found.mesh.length) {
            toast('Nothing in the thesaurus for that term — add synonyms yourself.');
            return;
          }
          toast(`Synonyms: ${found.synonyms.join(', ') || 'none'}. `
            + `MeSH: ${found.mesh.join(', ') || 'none'}.`);
        }),
      }, 'Preview expansion for the first term')));
  }

  section.append(
    el('div', { class: 'row-actions' },
      el('button', { class: 'button', onclick: build }, 'Build search strings'),
      el('button', {
        class: 'button button-quiet',
        onclick: () => guard(async () => {
          if (!state.project) { toast('Open a project first.', true); return; }
          const payload = {
            framework: questionState.framework,
            question_text: questionState.question_text,
            years: questionState.years,
            concepts: questionState.concepts,
          };
          await post(`/api/projects/${state.project.project_id}/question`, payload);
          toast('Saved to the project. The audit document reports it as the '
            + 'search strategy — PRISMA item 7 asks for exactly this.');
        }),
      }, 'Save to the project')),
    output);

  if (questionState.report) output.replaceChildren(questionReport(questionState.report));
  return section;
}

function questionReport(report) {
  const children = [];
  if (report.missing_required.length) {
    children.push(notice('Still needed: ' + report.missing_required.join(', ')
      + '. The strings below are built from what is filled in.', 'warn'));
  }
  children.push(notice(report.reporting_note, 'good'));

  for (const row of report.queries) {
    const box = el('pre', { class: 'macro-output' }, row.query || '(nothing yet)');
    children.push(el('div', { class: 'subcard' },
      el('h3', {}, row.label),
      el('p', { class: 'hint' }, row.how_to_run),
      ...row.caveats.map((c) => notice(c, 'warn')),
      box,
      el('button', {
        class: 'button button-quiet button-small',
        onclick: () => navigator.clipboard.writeText(row.query).then(
          () => toast('Copied.'), () => toast('Could not copy.', true)),
      }, 'Copy')));
  }
  return card('Search strings', ...children);
}

/* ================================================================ compliance */

const complianceState = { extracted: null, results: null, journal: '', journals: null };

function viewCompliance() {
  const section = el('section', { class: 'stack' }, el('h1', {}, 'Compliance'));

  const rubricText = el('textarea', {
    rows: 8,
    placeholder: 'Paste your rubric, syllabus or assignment brief here.',
  });

  section.append(card('Rubric and syllabus',
    el('p', { class: 'hint' },
      'Extraction separates requirements a program can verify — counts, dates, '
      + 'named sections, formatting — from criteria no program can score, like '
      + '"demonstrates critical analysis". Both are listed; only the first kind '
      + 'is checked, because a green tick on a judgement would be inventing a '
      + 'grade.'),
    field('Rubric text', rubricText),
    el('div', { class: 'row-actions' },
      el('button', {
        class: 'button',
        onclick: () => guard(async () => {
          const out = await post('/api/rubric/extract', { text: rubricText.value });
          complianceState.extracted = out;
          render();
        }),
      }, 'Extract requirements'),
      complianceState.extracted ? el('button', {
        class: 'button button-quiet',
        onclick: () => guard(async () => {
          if (!state.project) { toast('Open a project first.', true); return; }
          await post(`/api/projects/${state.project.project_id}/rubric`,
            { requirements: complianceState.extracted.requirements });
          toast('Attached. The checks now run against your draft.');
          const results = await api(
            `/api/projects/${state.project.project_id}/compliance`);
          complianceState.results = results;
          render();
        }),
      }, 'Attach to this project') : null)));

  if (complianceState.extracted) {
    const out = complianceState.extracted;
    section.append(card('Extracted',
      notice(out.summary, 'good'),
      el('p', { class: 'hint' }, out.caveat),
      el('div', { class: 'list' }, out.requirements.map((r) =>
        el('div', { class: `claim ${r.checkable ? '' : 'claim-own'}` },
          el('div', { class: 'claim-meta' },
            chip(r.checkable ? 'checkable' : 'not scorable',
              r.checkable ? 'good' : ''),
            el('span', { class: 'flag-code' }, r.kind_label)),
          el('div', { class: 'claim-text' }, r.describe),
          el('p', { class: 'hint' }, '“' + r.source_text + '”'),
          r.note ? el('p', { class: 'hint' }, r.note) : null)))));
  }

  const results = el('div', {});
  if (state.project) {
    guard(async () => {
      const out = await api(`/api/projects/${state.project.project_id}/compliance`);
      results.replaceChildren(complianceResults(out));
    });
  }
  section.append(results);

  section.append(journalCard());
  return section;
}

function complianceResults(out) {
  if (!out.results || !out.results.length) {
    return card('Checks against your draft',
      el('p', { class: 'hint' }, out.no_score_note || out.headline));
  }
  const icon = { met: 'good', not_met: 'bad', partial: 'warn', cannot_check: '' };
  return card('Checks against your draft',
    notice(out.headline, 'good'),
    el('p', { class: 'hint' }, out.no_score_note),
    el('div', { class: 'list' }, out.results.map((r) =>
      el('div', { class: 'claim' },
        el('div', { class: 'claim-meta' },
          chip({ met: 'met', not_met: 'not met', partial: 'partly',
                 cannot_check: 'cannot check' }[r.status], icon[r.status]),
          el('span', { class: 'row-title' }, r.label)),
        r.observed ? el('p', { class: 'hint' }, 'In the draft: ' + r.observed) : null,
        r.gap ? el('p', { class: 'hint' }, 'Gap: ' + r.gap) : null,
        r.advice ? el('p', { class: 'hint' }, r.advice) : null))));
}

function journalCard() {
  const output = el('div', {});
  const picker = el('select', {}, [el('option', { value: '' }, 'Choose a journal…')]);
  const guidelines = el('textarea', {
    rows: 5, placeholder: 'Or paste the author guidelines from any journal.',
  });
  const abstractBox = el('textarea', {
    rows: 5,
    placeholder: 'Paste your abstract so the structured-heading check can run.',
  });

  guard(async () => {
    const data = await api('/api/journals');
    complianceState.journals = data.journals;
    for (const journal of data.journals) {
      picker.append(el('option', { value: journal.key }, journal.name));
    }
  });

  return card('Journal submission guidelines',
    el('p', { class: 'hint' },
      'A paper in perfect APA 7 is still desk rejected if the journal wants a '
      + '4,000-word ceiling, a structured abstract with named headings, and a '
      + 'reporting checklist. Those live in a different document from the style '
      + 'guide and they are what an editor checks first.'),
    el('div', { class: 'grid-fields' },
      field('Journal', picker, 'or paste guidelines below'),
      field('Abstract', abstractBox)),
    field('Author guidelines', guidelines),
    el('button', {
      class: 'button button-quiet',
      onclick: () => guard(async () => {
        const profile = await post('/api/journals/parse',
          { text: guidelines.value, name: 'Pasted guidelines' });
        const rows = [
          ['Word limit', profile.word_limit],
          ['Abstract limit', profile.abstract_limit],
          ['Reference limit', profile.reference_limit],
          ['Structured abstract', profile.abstract_structured ? 'yes' : 'not stated'],
          ['Citation style', profile.style],
          ['Blinded submission', profile.blinded ? 'yes' : 'not stated'],
          ['Reporting checklist', profile.reporting_guideline],
          ['Required statements', (profile.required_statements || []).join(', ')],
        ].filter(([, value]) => value !== null && value !== undefined && value !== '');
        output.replaceChildren(
          notice('This is what the parser found in the text you pasted. A blank '
            + 'means it was not stated — nothing here is inferred, because an '
            + 'invented word limit is worse than a missing one.', 'warn'),
          el('div', { class: 'table-wrap' }, el('table', {},
            el('tbody', {}, rows.map(([name, value]) => el('tr', {},
              el('th', {}, name), el('td', {}, String(value))))))),
          (profile.abstract_headings || []).length
            ? el('p', { class: 'hint' },
              `Abstract headings: ${profile.abstract_headings.join(' · ')}`)
            : null);
      }),
    }, 'Read the pasted guidelines'),
    el('button', {
      class: 'button',
      onclick: () => guard(async () => {
        if (!state.project) { toast('Open a project first.', true); return; }
        const out = await post(
          `/api/projects/${state.project.project_id}/journal-check`,
          { journal: picker.value, guidelines: guidelines.value,
            abstract: abstractBox.value });
        output.replaceChildren(
          notice(out.headline, 'good'),
          out.notes ? notice(out.notes, 'warn') : null,
          el('p', { class: 'hint' }, out.verify),
          el('div', { class: 'list' }, out.findings.map((f) =>
            el('div', { class: 'claim' },
              el('div', { class: 'claim-meta' },
                chip({ met: 'met', not_met: 'not met',
                       cannot_check: 'confirm yourself' }[f.status],
                  { met: 'good', not_met: 'bad', cannot_check: '' }[f.status]),
                el('span', { class: 'row-title' }, f.label)),
              el('p', { class: 'hint' }, `${f.observed} — required: ${f.expected}`),
              f.advice ? el('p', { class: 'hint' }, f.advice) : null))));
      }),
    }, 'Check against the journal'),
    output);
}

/* ================================================================= statistics */

function statisticsCard() {
  const output = el('div', {});
  const input = el('textarea', {
    rows: 6,
    placeholder: 'Paste an SPSS table or R output block, including its header line.',
  });
  const variables = el('input', {
    type: 'text', placeholder: 'fall rates between the two units',
  });

  return card('Statistical narrative',
    el('p', { class: 'hint' },
      'Paste SPSS or R output and get APA 7 results prose. The value is not the '
      + 'typing — it is the dozen statistical-style rules that are individually '
      + 'trivial and collectively impossible at 2 a.m.: no leading zero on p and '
      + 'r but a leading zero on M and t, exact p rather than a threshold, '
      + 'p < .001 rather than SPSS’s impossible p = .000, italic Roman '
      + 'symbols but upright Greek.'),
    field('Output', input),
    field('What was compared', variables, 'goes into the sentence'),
    el('button', {
      class: 'button',
      onclick: () => guard(async () => {
        const out = await post('/api/statistics/translate',
          { text: input.value, variables: variables.value });
        const children = [];
        if (!out.results.length) children.push(notice(out.note, 'warn'));
        else children.push(notice(out.note, 'good'));
        for (const result of out.results) {
          children.push(el('div', { class: 'subcard' },
            el('h3', {}, result.label || result.kind),
            el('pre', { class: 'macro-output' }, result.sentence),
            result.note ? el('p', { class: 'hint' }, result.note) : null,
            result.confidence === 'ambiguous'
              ? notice('The parser could not fully identify this table. Check '
                + 'every number against your output — and on an SPSS '
                + 'independent-samples table there are two rows, and only one '
                + 'of them is yours.', 'warn')
              : null,
            el('button', {
              class: 'button button-quiet button-small',
              onclick: () => navigator.clipboard.writeText(result.sentence).then(
                () => toast('Copied.'), () => toast('Could not copy.', true)),
            }, 'Copy')));
        }
        for (const issue of out.issues) {
          children.push(el('div', { class: 'flag flag-warn' },
            el('p', { class: 'flag-message' }, issue.message),
            issue.excerpt
              ? el('p', { class: 'flag-excerpt' }, issue.excerpt) : null,
            el('p', { class: 'flag-suggestion' }, issue.suggestion)));
        }
        output.replaceChildren(...children);
      }),
    }, 'Translate to APA'),
    output,
    manualStatistics());
}

/* Typing the numbers in by hand, for the output the parser cannot read — an R
   package it does not know, a table copied out of a PDF, a figure from a paper
   you are reporting. The formatting rules are the point of this tool and they
   apply the same either way; without this, an unparseable table meant losing
   them entirely. */

function manualStatistics() {
  const host = el('div', { class: 'stack' }, el('p', { class: 'hint' }, 'Loading…'));

  api('/api/statistics/supported').then((data) => {
    host.replaceChildren();
    const output = el('div', {});
    const variables = el('input', {
      type: 'text', placeholder: 'fall rates between the two units',
    });
    const fieldHost = el('div', { class: 'stack' });
    let inputs = {};

    const kindSelect = el('select', {}, data.tests.map((test) =>
      el('option', { value: test.kind }, test.label)));

    const paintFields = () => {
      const test = data.tests.find((t) => t.kind === kindSelect.value);
      inputs = {};
      fieldHost.replaceChildren(
        el('p', { class: 'hint' }, `Renders as: ${test.apa}`),
        el('div', { class: 'repeat-row' }, test.fields.map((name) => {
          inputs[name] = numberInput(name);
          return el('label', { class: 'tight' }, name, inputs[name]);
        })));
    };
    kindSelect.addEventListener('change', paintFields);
    paintFields();

    host.append(
      field('Test', kindSelect),
      fieldHost,
      field('What was compared', variables, 'goes into the sentence'),
      el('button', {
        class: 'button button-quiet',
        onclick: () => guard(async () => {
          const values = {};
          for (const [name, node] of Object.entries(inputs)) {
            if (node.value.trim()) values[name] = node.value.trim();
          }
          const out = await post('/api/statistics/manual',
            { kind: kindSelect.value, values, variables: variables.value });
          output.replaceChildren(
            el('pre', { class: 'macro-output' }, out.sentence),
            el('button', {
              class: 'button button-quiet button-small',
              onclick: () => navigator.clipboard.writeText(out.sentence).then(
                () => toast('Copied.'), () => toast('Could not copy.', true)),
            }, 'Copy'));
        }),
      }, 'Format these values'),
      output);
  }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));

  return el('div', { class: 'subcard' },
    el('h3', {}, 'Or type the numbers in'),
    el('p', { class: 'hint' }, 'For output the parser cannot read — an R package '
      + 'it does not know, or a result you are reporting from someone else’s '
      + 'paper. The APA formatting rules are the same either way.'),
    host);
}

/* ===================================================================== PRISMA */

const PRISMA_FIELDS = [
  ['records_databases', 'Records identified — databases'],
  ['records_registers', 'Records identified — registers'],
  ['duplicates_removed', 'Duplicates removed'],
  ['removed_ineligible_automation', 'Removed by automation tools'],
  ['removed_other_reasons', 'Removed for other reasons'],
  ['records_screened', 'Records screened'],
  ['records_excluded', 'Records excluded at title and abstract'],
  ['reports_sought', 'Reports sought for retrieval'],
  ['reports_not_retrieved', 'Reports not retrieved'],
  ['reports_assessed', 'Reports assessed for eligibility'],
  ['records_websites', 'Other methods — websites'],
  ['records_organisations', 'Other methods — organisations'],
  ['records_citation_searching', 'Other methods — citation searching'],
  ['other_reports_sought', 'Other methods — reports sought'],
  ['other_reports_not_retrieved', 'Other methods — not retrieved'],
  ['other_reports_assessed', 'Other methods — assessed'],
  ['studies_included', 'Studies included in review'],
  ['reports_of_included', 'Reports of included studies'],
];

function prismaCard() {
  const values = {};
  const reasons = el('textarea', {
    rows: 3,
    placeholder: 'Wrong population: 61\nWrong outcome: 44\nNot primary research: 29',
  });
  const output = el('div', {});

  const inputs = PRISMA_FIELDS.map(([key, label]) => {
    const input = el('input', {
      type: 'number', min: 0,
      oninput: (event) => { values[key] = event.target.value; },
    });
    return field(label, input);
  });

  return card('PRISMA 2020 flow diagram',
    el('p', { class: 'hint' },
      'Drawn from your counts in the layout the 2020 statement describes, rather '
      + 'than reproduced from the PRISMA group’s template files. The '
      + 'arithmetic is checked the way a reader checks it — identified minus '
      + 'removed equals screened, and so on down — and a mismatch is reported '
      + 'rather than corrected, because silently adjusting the numbers would be '
      + 'fabricating a flow diagram.'),
    el('div', { class: 'grid-fields' }, inputs),
    field('Full-text exclusion reasons', reasons,
      'one per line, as "reason: count". PRISMA 2020 requires these.'),
    el('button', {
      class: 'button',
      onclick: () => guard(async () => {
        const parsed = {};
        for (const line of reasons.value.split('\n')) {
          const match = /^(.+?)\s*[:=]\s*(\d+)\s*$/.exec(line.trim());
          if (match) parsed[match[1].trim()] = Number(match[2]);
        }
        const counts = Object.assign({}, values);
        if (Object.keys(parsed).length) counts.reports_excluded_reasons = parsed;
        const out = await post(`/api/projects/${state.project.project_id}/prisma`,
          { counts });
        const children = [];
        if (out.problems.length) {
          children.push(notice(
            'The counts do not subtract. Reported rather than corrected — the '
            + 'numbers below are exactly what you entered.', 'bad'));
          for (const problem of out.problems) {
            children.push(el('div', { class: 'flag flag-block' },
              el('div', { class: 'flag-head' }, chip('check', 'bad'),
                el('span', { class: 'flag-code' }, problem.check)),
              el('p', { class: 'flag-message' },
                `Expected ${problem.expected}, entered ${problem.entered}.`),
              el('p', { class: 'flag-suggestion' }, problem.explanation)));
          }
        } else {
          children.push(notice('Every subtraction checks out.', 'good'));
        }
        if (out.path) {
          children.push(el('img', {
            src: `/api/projects/${state.project.project_id}/files/`
              + encodeURIComponent(out.path)
              + `?token=${encodeURIComponent(state.token)}`,
            alt: 'PRISMA 2020 flow diagram',
            style: 'max-width:100%;border:1px solid var(--border);'
              + 'border-radius:var(--radius);background:#fff',
          }));
        }
        children.push(el('p', { class: 'hint citation' }, out.citation));
        children.push(el('p', { class: 'hint' }, out.licensing));
        children.push(el('p', { class: 'hint' }, 'Figure note: ' + out.figure_note));
        output.replaceChildren(...children);
      }),
    }, 'Validate and draw'),
    output);
}

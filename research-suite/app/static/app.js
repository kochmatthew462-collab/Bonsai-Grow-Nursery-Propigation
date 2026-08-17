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
  project: null,
  view: 'projects',
  busy: false,
};

/* ------------------------------------------------------------------ plumbing */

function takeToken() {
  const match = /(?:^|[#&])token=([^&]+)/.exec(location.hash || '');
  if (match) {
    state.token = decodeURIComponent(match[1]);
    try {
      sessionStorage.setItem('research_token', state.token);
    } catch (error) { /* private browsing — memory only, which still works */ }
    history.replaceState(null, '', location.pathname);
    return;
  }
  try {
    state.token = sessionStorage.getItem('research_token') || '';
  } catch (error) {
    state.token = '';
  }
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
  nav.hidden = !state.project;
  document.getElementById('switch-project').hidden = !state.project;
  document.getElementById('project-label').textContent =
    state.project ? state.project.topic : '';
  for (const button of nav.querySelectorAll('button')) {
    button.classList.toggle('is-active', button.dataset.view === state.view);
  }

  const host = document.getElementById('view');
  host.replaceChildren();
  const views = {
    projects: viewProjects,
    question: viewQuestion,
    sources: viewSources,
    screen: viewScreen,
    appraise: viewAppraise,
    write: viewWrite,
    check: viewCheck,
    export: viewExport,
    compliance: viewCompliance,
    settings: viewSettings,
  };
  host.append((views[state.view] || viewProjects)());
}

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
      el('button', { class: 'button button-quiet', onclick: () => go('appraise') },
        'Next: appraise →')));
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

    host.append(el('button', { class: 'button', onclick: () => go('export') },
      'Next: export →'));
  }).catch((error) => host.replaceChildren(notice(error.message, 'bad')));

  return el('section', { class: 'stack' }, el('h1', {}, 'Check'), host);
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
    prismaCard());
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
    notice(`Bound to ${config.host}:${config.port}. `
      + (config.host === '127.0.0.1'
        ? 'Localhost only — not reachable from your network. The security '
          + 'boundary is your operating system account: anything running as you '
          + 'can read the project data and the API keys.'
        : '⚠ Not localhost. This is reachable from your network — put an '
          + 'authenticating proxy in front of it.'),
    config.host === '127.0.0.1' ? '' : 'bad'),

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

    card('Where things are',
      el('div', { class: 'table-wrap' }, el('table', {},
        el('tbody', {},
          [['Projects', config.data_dir], ['Exports', config.export_dir],
            ['Secrets', config.keyring_available ? 'OS keychain' : (config.env_file || 'not written yet')]]
            .map(([label, value]) => el('tr', {}, el('th', {}, label), el('td', {}, value))))))));
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
guard(async () => {
  state.config = await api('/api/config');
  for (const warning of state.config.warnings) toast(warning, true);
  render();
});

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
    output);
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

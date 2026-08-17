/*
 * Clinical charting tab — front end.
 *
 * Shares the plumbing in app.js (api, post, guard, toast, el, card, field, chip,
 * notice) rather than duplicating it. Both files are classic scripts, so their
 * top-level declarations are visible to each other; there is no build step here
 * and the CSP forbids third-party script anyway.
 *
 * Three things about this UI are deliberate:
 *
 * 1. **The Save button's state comes from the server.** Every edit debounces a
 *    /preview call, and `blocked` from that response is what disables Save. The
 *    front end never decides on its own that a note is complete — it asks. That
 *    means a stale or bypassed front end cannot save something the interlocks
 *    would refuse, because /entries runs the same evaluation again.
 *
 * 2. **The language checker underlines in place.** Flags come back with character
 *    offsets, so the flagged text is highlighted under the textarea with the
 *    suggestion attached, the way a spell-checker works. Quoted speech is exempt
 *    server-side, so quoting a patient never trips it.
 *
 * 3. **The disclosure banner is not dismissible.** It renders above every
 *    charting screen. See app/charting/disclosure.py for why.
 */
'use strict';

const chartState = {
  ref: null,
  encounter: null,
  view: 'note',
  draft: null,
  scaleDraft: { scaleId: '', responses: {} },
  macroDraft: { macroId: '', values: {} },
  moduleDraft: {},
  bundleDraft: { bundleId: '', values: {} },
  handoffDraft: { route: '', values: {} },
  preview: null,
  author: '',
  credential: '',
};

/* ------------------------------------------------------------------ plumbing */

const chartApi = (path, body) =>
  body === undefined ? api('/api/charting' + path)
    : post('/api/charting' + path, body);

function blankDraft(kind) {
  return {
    kind: kind || 'focused_update',
    event_at: localNow(),
    subjective: '',
    objective: '',
    assessment: '',
    plan: '',
    labs: '',
    pending: '',
    narrative: '',
    narrativeEdited: false,
    vitals: {},
    systems: {},
    scales: [],
    medications: [],
    interventions: [],
    notifications: [],
    module_data: {},
    override_reason: '',
    acknowledged: [],
  };
}

function localNow() {
  // datetime-local wants a naive local string. Trimming the ISO string keeps the
  // browser's own clock, which is what the nurse is reading off the wall.
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
    + `T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function toIso(localValue) {
  if (!localValue) return '';
  const parsed = new Date(localValue);
  return Number.isNaN(parsed.getTime()) ? '' : parsed.toISOString();
}

function clock(iso) {
  if (!iso) return '—';
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return '—';
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

function draftPayload() {
  const draft = chartState.draft;
  const systems = Object.entries(draft.systems).map(([systemId, value]) => ({
    system: systemId,
    within_defined_limits: !!value.wdl,
    findings: value.findings || {},
    exceptions: value.exceptions || [],
    not_assessed: !!value.notAssessed,
    not_assessed_reason: value.notAssessedReason || '',
  }));
  return {
    kind: draft.kind,
    author_initials: chartState.author,
    author_credential: chartState.credential,
    event_at: toIso(draft.event_at),
    subjective: draft.subjective,
    objective: draft.objective,
    assessment: draft.assessment,
    plan: draft.plan,
    labs: draft.labs,
    pending: draft.pending,
    narrative: draft.narrativeEdited ? draft.narrative : '',
    vitals: draft.vitals,
    systems,
    scales: draft.scales,
    medications: draft.medications,
    interventions: draft.interventions,
    notifications: draft.notifications,
    module_data: draft.module_data,
    override_reason: draft.override_reason,
    acknowledged_warnings: draft.acknowledged,
  };
}

let previewTimer = null;

function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    refreshPreview().catch(() => { /* a failed preview must not block typing */ });
  }, 450);
}

async function refreshPreview() {
  if (!chartState.encounter) return;
  const result = await chartApi(
    `/encounters/${chartState.encounter.encounter_id}/preview`, draftPayload());
  chartState.preview = result;
  paintGate();
}

/* ------------------------------------------------------------------- banner */

function disclosureBanner() {
  const d = (chartState.ref && chartState.ref.disclosure) || {};
  return el('div', { class: 'disclosure' },
    el('p', {}, el('strong', {}, 'Not the medical record. '), d.not_the_record || ''),
    el('p', {}, el('strong', {}, 'No patient identifiers. '), d.no_phi || ''),
    el('p', { class: 'disclosure-quiet' }, d.local_only || ''),
    el('p', { class: 'disclosure-quiet' }, d.not_clinical_advice || ''));
}

/* -------------------------------------------------------------- flag display */

const SEVERITY_LABEL = { block: 'Blocked', warn: 'Check', info: 'Note' };

function flagRow(flag, options = {}) {
  const acknowledged = chartState.draft
    && chartState.draft.acknowledged.includes(flag.code);
  const children = [
    el('div', { class: 'flag-head' },
      chip(SEVERITY_LABEL[flag.severity] || flag.severity, flag.severity),
      el('span', { class: 'flag-code' }, flag.code.replace(/_/g, ' ')),
      flag.field_path ? el('span', { class: 'flag-field' }, flag.field_path) : null),
    el('p', { class: 'flag-message' }, flag.message),
  ];
  if (flag.excerpt) {
    children.push(el('p', { class: 'flag-excerpt' }, '“' + flag.excerpt + '”'));
  }
  if (flag.suggestion) {
    children.push(el('p', { class: 'flag-suggestion' }, flag.suggestion));
  }
  if (options.acknowledgeable && flag.severity === 'warn') {
    children.push(el('button', {
      class: 'button button-quiet button-small',
      onclick: () => {
        const list = chartState.draft.acknowledged;
        const index = list.indexOf(flag.code);
        if (index >= 0) list.splice(index, 1); else list.push(flag.code);
        renderChart();
      },
    }, acknowledged ? 'Acknowledged — undo' : 'I have considered this'));
  }
  return el('div', {
    class: `flag flag-${flag.severity}${acknowledged ? ' flag-ack' : ''}`,
  }, ...children);
}

function paintGate() {
  const host = document.getElementById('gate-panel');
  if (!host) return;
  host.replaceChildren(gatePanel());
}

function gatePanel() {
  const preview = chartState.preview;
  if (!preview) {
    return el('div', { class: 'card' }, el('p', { class: 'hint' },
      'Start typing and the checks will run.'));
  }
  const gate = preview.gate || {};
  const flags = gate.flags || [];
  const blocks = flags.filter((f) => f.severity === 'block');
  const warns = flags.filter((f) => f.severity === 'warn');
  const infos = flags.filter((f) => f.severity === 'info');
  const nonOverridable = (chartState.ref.non_overridable || []);
  const hard = blocks.filter((f) => nonOverridable.includes(f.code));

  const children = [];

  children.push(statBlock([
    [String(blocks.length), 'blocking'],
    [String(warns.length), 'to check'],
    [String((preview.phi || []).length), 'identifiers'],
    [gate.blocked ? 'No' : 'Yes', 'saveable'],
  ]));

  if (preview.late_entry) {
    children.push(notice(
      `This will be tagged [LATE ENTRY] — the event was ${preview.late_by_minutes} `
      + 'minutes before now. That is correct and defensible. What is not '
      + 'defensible is a timestamp that disagrees with the medication scanner, '
      + 'which is why the documentation time is taken from the server clock and '
      + 'cannot be changed.', 'warn'));
  }

  if ((gate.critical_values || []).length) {
    children.push(notice(
      'Critical values recorded: ' + gate.critical_values.join('; ')
      + '. Provider notification is required before this note can be saved.',
      'bad'));
  }

  for (const flag of blocks) children.push(flagRow(flag));
  for (const flag of warns) children.push(flagRow(flag, { acknowledgeable: true }));
  for (const flag of infos) children.push(flagRow(flag));

  for (const identifier of preview.phi || []) {
    children.push(flagRow(identifier));
  }
  for (const hint of preview.quote_suggestions || []) {
    children.push(flagRow(hint));
  }

  if ((gate.loops || []).length) {
    children.push(el('div', { class: 'subcard' },
      el('h3', {}, 'Reassessments this note will open'),
      el('ul', { class: 'plain-list' }, (gate.loops || []).map((loop) =>
        el('li', {}, `${loop.trigger} — due ${clock(loop.due_at)} `
          + `(${loop.window_minutes} min)`)))));
  }

  if (blocks.length && !hard.length) {
    const reason = el('input', {
      type: 'text',
      value: chartState.draft.override_reason,
      placeholder: 'Rapid response in progress — will complete notification after',
      oninput: (event) => {
        chartState.draft.override_reason = event.target.value;
        schedulePreview();
      },
    });
    children.push(el('div', { class: 'subcard' },
      el('h3', {}, 'Override'),
      el('p', { class: 'hint' },
        'A block can be overridden with a reason, and the reason is written into '
        + 'the note and the audit trail. This exists because a nurse managing an '
        + 'emergency has to be able to save now and complete in four minutes — '
        + 'and a recorded override showing a person deciding under pressure is a '
        + 'stronger artefact than a block that got worked around.'),
      field('Reason for saving without the missing element', reason)));
  } else if (hard.length) {
    children.push(notice(
      'This cannot be overridden. ' + hard.map((f) => f.code.replace(/_/g, ' '))
        .join(', ') + '. There is no clinical circumstance in which these belong '
      + 'in a chart note.', 'bad'));
  }

  return card('Checks', ...children);
}

/* --------------------------------------------------------------- text fields */

function checkedTextarea(label, key, placeholder, hint) {
  const area = el('textarea', {
    rows: 4, placeholder: placeholder || '',
    oninput: (event) => {
      chartState.draft[key] = event.target.value;
      schedulePreview();
    },
  });
  area.value = chartState.draft[key] || '';
  return field(label, area, hint);
}

/* ------------------------------------------------------------------- vitals */

const VITAL_FIELDS = [
  ['systolic', 'Systolic', 'mmHg'],
  ['diastolic', 'Diastolic', 'mmHg'],
  ['map_mmhg', 'MAP if measured', 'from an arterial line only'],
  ['heart_rate', 'Heart rate', 'per minute'],
  ['respiratory_rate', 'Respiratory rate', 'per minute'],
  ['spo2', 'SpO₂', '%'],
  ['temperature_c', 'Temperature', '°C'],
  ['pain_score', 'Pain score', '0–10'],
  ['blood_glucose', 'Glucose', 'mg/dL'],
  ['end_tidal_co2', 'EtCO₂', 'mmHg'],
];

function vitalsCard() {
  const draft = chartState.draft;
  const grid = el('div', { class: 'grid-fields' }, VITAL_FIELDS.map(([key, label, unit]) => {
    const input = el('input', {
      type: 'number', step: 'any', inputmode: 'decimal',
      oninput: (event) => {
        const value = event.target.value;
        if (value === '') delete draft.vitals[key];
        else draft.vitals[key] = value;
        schedulePreview();
      },
    });
    if (draft.vitals[key] !== undefined) input.value = draft.vitals[key];
    return field(label, input, unit);
  }));

  const rhythm = el('input', {
    type: 'text', placeholder: 'sinus tachycardia',
    oninput: (e) => { draft.vitals.rhythm = e.target.value; schedulePreview(); },
  });
  rhythm.value = draft.vitals.rhythm || '';
  const oxygen = el('input', {
    type: 'text', placeholder: '2 L/min nasal cannula',
    oninput: (e) => { draft.vitals.oxygen_delivery = e.target.value; schedulePreview(); },
  });
  oxygen.value = draft.vitals.oxygen_delivery || '';
  const taken = el('input', {
    type: 'datetime-local',
    oninput: (e) => { draft.vitals.taken_at = toIso(e.target.value); schedulePreview(); },
  });

  return card('Vital signs',
    el('p', { class: 'hint' },
      'The time these were taken is separate from the time of the note, because a '
      + 'note written at 1420 routinely quotes vitals taken at 1405. Conflating '
      + 'them is how a chart drifts out of agreement with the flowsheet. Crossing '
      + 'a critical threshold requires a provider notification before this note '
      + 'will save — see Reference for the thresholds.'),
    grid,
    el('div', { class: 'grid-fields' },
      field('Rhythm', rhythm),
      field('Oxygen delivery', oxygen),
      field('Time taken', taken, 'defaults to now if left blank')));
}

/* ----------------------------------------------------------- repeatable lists */

function repeatable(title, hint, list, columns, blank, onChange) {
  const rows = list.map((item, index) => el('div', { class: 'repeat-row' },
    el('div', { class: 'grid-fields' }, columns.map((column) => {
      let input;
      if (column.kind === 'textarea') {
        input = el('textarea', { rows: 2, placeholder: column.placeholder || '' });
      } else if (column.kind === 'select') {
        input = el('select', {}, [el('option', { value: '' }, '—')].concat(
          (column.options || []).map((option) =>
            el('option', { value: option }, option))));
      } else if (column.kind === 'checkbox') {
        input = el('input', { type: 'checkbox' });
        input.checked = !!item[column.key];
      } else {
        input = el('input', {
          type: column.kind === 'time' ? 'datetime-local'
            : (column.kind === 'number' ? 'number' : 'text'),
          step: column.kind === 'number' ? 'any' : undefined,
          placeholder: column.placeholder || '',
        });
      }
      if (column.kind !== 'checkbox' && item[column.key] !== undefined) {
        input.value = column.kind === 'time'
          ? (item[column.key] ? new Date(item[column.key]).toISOString().slice(0, 16) : '')
          : item[column.key];
      }
      input.addEventListener(column.kind === 'checkbox' ? 'change' : 'input', (event) => {
        item[column.key] = column.kind === 'checkbox' ? event.target.checked
          : (column.kind === 'time' ? toIso(event.target.value) : event.target.value);
        if (onChange) onChange();
        schedulePreview();
      });
      return field(column.label, input, column.hint);
    })),
    el('button', {
      class: 'button button-quiet button-small',
      onclick: () => { list.splice(index, 1); renderChart(); },
    }, 'Remove')));

  return card(title,
    hint ? el('p', { class: 'hint' }, hint) : null,
    ...rows,
    el('button', {
      class: 'button button-quiet',
      onclick: () => { list.push(blank()); renderChart(); },
    }, 'Add'));
}

/* ------------------------------------------------------------- encounter list */

function viewEncounters() {
  const label = el('input', { type: 'text', placeholder: 'Bed 12' });
  const initials = el('input', { type: 'text', placeholder: 'AB', maxlength: 4 });
  const setting = el('select', {}, (chartState.ref.settings || []).map((s) =>
    el('option', { value: s.value }, s.label)));
  const ageBand = el('input', { type: 'text', placeholder: 'adult, or 8 y, or preterm' });
  ageBand.value = 'adult';
  const author = el('input', { type: 'text', placeholder: 'MK' });
  author.value = chartState.author;
  const credential = el('input', { type: 'text', placeholder: 'RN, BSN' });
  credential.value = chartState.credential;

  const list = el('div', { class: 'list' }, el('p', { class: 'hint' }, 'Loading…'));
  refreshEncounterList(list);

  return el('section', { class: 'stack' },
    el('h1', {}, 'Clinical charting'),
    disclosureBanner(),

    card('You',
      el('p', { class: 'hint' },
        'Your initials and credential go on every note you compose here. Nothing '
        + 'is sent anywhere — they are written into the note text and the audit '
        + 'trail so the document is attributable.'),
      el('div', { class: 'grid-fields' },
        field('Your initials', author),
        field('Credential', credential))),

    card('Start an encounter',
      el('p', { class: 'hint' },
        'An encounter is one patient for one shift, identified by bed or room. '
        + 'There is no field for a name, a record number or a date of birth, and '
        + 'the label you type here is checked for identifiers before it is '
        + 'accepted.'),
      el('div', { class: 'grid-fields' },
        field('Bed or room', label, 'Bed 12, Room 415-A, Trauma 2'),
        field('Initials', initials, 'optional'),
        field('Setting', setting, 'chooses the specialty module and scale order'),
        field('Age band', ageBand, 'not a date of birth')),
      el('button', {
        class: 'button',
        onclick: () => guard(async () => {
          chartState.author = author.value.trim();
          chartState.credential = credential.value.trim();
          const result = await chartApi('/encounters', {
            local_label: label.value.trim(),
            initials: initials.value.trim(),
            setting: setting.value,
            age_band: ageBand.value.trim() || 'adult',
            author_initials: chartState.author,
          });
          chartState.encounter = result.encounter;
          chartState.draft = blankDraft();
          goChart('note');
        }),
      }, 'Start encounter')),

    card('Open encounters', list),

    card('Purge',
      el('p', { class: 'hint' },
        'Deletes every encounter file on this machine. The correct end of a shift '
        + 'is an empty data directory: nothing here is the legal record, so '
        + 'nothing here needs to survive you going home.'),
      el('button', {
        class: 'button button-danger',
        onclick: () => guard(async () => {
          if (!window.confirm('Delete every encounter? This cannot be undone.')) return;
          const result = await chartApi('/purge', {});
          chartState.encounter = null;
          toast(result.message);
          renderChart();
        }),
      }, 'Purge all charting data')),

    card('What this tab cannot do',
      el('div', { class: 'list' }, (chartState.ref.cannot_do || []).map((item) =>
        el('div', { class: 'claim' },
          el('div', { class: 'claim-text' }, el('strong', {}, item.claim)),
          el('p', { class: 'hint' }, item.reality))))));
}

function refreshEncounterList(host) {
  guard(async () => {
    const result = await chartApi('/encounters');
    const rows = result.encounters || [];
    host.replaceChildren();
    if (!rows.length) {
      host.append(el('p', { class: 'hint' }, 'No encounters yet.'));
      return;
    }
    for (const row of rows) {
      host.append(el('div', { class: 'list-row' },
        el('div', {},
          el('strong', {}, row.local_label || row.encounter_id),
          row.initials ? el('span', { class: 'hint' }, ' · ' + row.initials) : null,
          el('div', { class: 'hint' },
            `${row.entry_count} note${row.entry_count === 1 ? '' : 's'}`
            + (row.untranscribed
              ? ` · ${row.untranscribed} not transcribed into the EHR` : '')
            + ` · ${row.setting.replace(/_/g, '-')}`)),
        el('div', { class: 'row-actions' },
          el('button', {
            class: 'button button-quiet button-small',
            onclick: () => guard(async () => {
              const loaded = await chartApi(`/encounters/${row.encounter_id}`);
              chartState.encounter = loaded.encounter;
              chartState.draft = blankDraft();
              goChart('note');
            }),
          }, 'Open'),
          el('button', {
            class: 'button button-quiet button-small',
            onclick: () => guard(async () => {
              if (!window.confirm(`Delete ${row.local_label}?`)) return;
              await api(`/api/charting/encounters/${row.encounter_id}`,
                { method: 'DELETE' });
              refreshEncounterList(host);
            }),
          }, 'Delete'))));
    }
  });
}

/* ------------------------------------------------------------------ the note */

function viewNote() {
  const draft = chartState.draft;
  const encounter = chartState.encounter;
  const derived = encounter._derived || {};

  const kind = el('select', {
    onchange: (event) => { draft.kind = event.target.value; schedulePreview(); },
  }, (chartState.ref.entry_kinds || []).map((k) =>
    el('option', { value: k.value, selected: k.value === draft.kind }, k.label)));

  const eventAt = el('input', {
    type: 'datetime-local',
    oninput: (event) => { draft.event_at = event.target.value; schedulePreview(); },
  });
  eventAt.value = draft.event_at;

  const composed = el('textarea', {
    rows: 16,
    oninput: (event) => {
      draft.narrative = event.target.value;
      draft.narrativeEdited = true;
      schedulePreview();
    },
  });
  composed.value = draft.narrativeEdited
    ? draft.narrative
    : ((chartState.preview && chartState.preview.narrative) || '');

  const saveButton = el('button', {
    class: 'button',
    onclick: () => guard(async () => {
      const result = await chartApi(
        `/encounters/${encounter.encounter_id}/entries`, draftPayload());
      chartState.encounter = result.encounter;
      chartState.draft = blankDraft(draft.kind);
      chartState.preview = null;
      const opened = (result.loops_opened || []).length;
      toast('Note saved.' + (opened
        ? ` ${opened} reassessment${opened === 1 ? '' : 's'} opened — see Loops.`
        : '') + ' Transcribe it into the EHR and mark it transcribed.');
      goChart('timeline');
    }),
  }, 'Save note');
  if (chartState.preview && chartState.preview.gate
      && chartState.preview.gate.blocked) {
    saveButton.setAttribute('disabled', '');
    saveButton.classList.add('button-blocked');
  }

  return el('section', { class: 'stack' },
    disclosureBanner(),
    encounterStrip(),

    card('This note',
      el('div', { class: 'grid-fields' },
        field('Kind', kind),
        field('When it happened', eventAt,
          'The documentation time is the server clock and cannot be set. If this '
          + 'is more than an hour ago the note is tagged [LATE ENTRY].'))),

    vitalsCard(),

    card('S — Subjective',
      el('p', { class: 'hint' },
        'The patient\'s own words, in quotation marks. Everything inside quotes '
        + 'is exempt from the objective-language checks: what the patient said is '
        + 'data, not your characterisation, and a verbatim quote is the strongest '
        + 'sentence in a nursing note.'),
      checkedTextarea('What the patient reports', 'subjective',
        'Patient stated, "It feels like an elephant is sitting on my chest."')),

    card('B/O — Background and objective',
      checkedTextarea('Objective findings', 'objective',
        'Ambulated 40 feet with a front-wheel walker and one-person assist.'),
      checkedTextarea('Pertinent labs', 'labs', 'Lactate 2.4, WBC 14.2')),

    card('A — Assessment',
      el('p', { class: 'hint' },
        'The only section where interpretation belongs. Keeping it separate is '
        + 'what lets the objective section stay clean.'),
      checkedTextarea('Clinical impression and risk identified', 'assessment')),

    card('R/P — Response and plan',
      checkedTextarea('Plan', 'plan'),
      checkedTextarea('Outstanding at the time of this note', 'pending',
        'Blood cultures pending; second unit to hang at 1800')),

    repeatable('Medications',
      'Route, site and the two-identifier check are separate fields because these '
      + 'are what a deposition asks about one at a time. Anything given for pain, '
      + 'fever, blood pressure, agitation or glucose opens a reassessment loop.',
      draft.medications, [
        { key: 'name', label: 'Medication' },
        { key: 'dose', label: 'Dose' },
        { key: 'route', label: 'Route' },
        { key: 'site', label: 'Site' },
        { key: 'given_at', label: 'Given at', kind: 'time' },
        { key: 'indication', label: 'Indication' },
        { key: 'pre_assessment', label: 'Pre-administration assessment', kind: 'textarea' },
        { key: 'two_identifiers_verified', label: 'Two identifiers verified', kind: 'checkbox' },
        { key: 'high_alert', label: 'High-alert medication', kind: 'checkbox' },
        { key: 'second_nurse_verified', label: 'Double check done', kind: 'checkbox' },
        { key: 'second_nurse_initials', label: 'Second nurse initials' },
        { key: 'wasted_amount', label: 'Amount wasted' },
        { key: 'waste_witness_initials', label: 'Waste witness' },
        { key: 'held', label: 'Held', kind: 'checkbox' },
        { key: 'hold_reason', label: 'Reason held' },
        { key: 'provider_notified_of_hold', label: 'Prescriber told of hold', kind: 'checkbox' },
        { key: 'refused', label: 'Patient declined', kind: 'checkbox' },
        { key: 'effect', label: 'Effect on reassessment', kind: 'textarea' },
        { key: 'effect_checked_at', label: 'Reassessed at', kind: 'time' },
      ], () => ({ name: '', dose: '', route: '', given_at: '' })),

    repeatable('Interventions',
      'An intervention with no documented response reads, to a reviewer, as an '
      + 'intervention nobody followed up.',
      draft.interventions, [
        { key: 'action', label: 'What you did' },
        { key: 'performed_at', label: 'Performed at', kind: 'time' },
        { key: 'equipment', label: 'Equipment' },
        { key: 'patient_tolerance', label: 'Patient tolerance' },
        { key: 'evaluated_at', label: 'Re-evaluated at', kind: 'time' },
        { key: 'response', label: 'Response', kind: 'textarea' },
      ], () => ({ action: '', performed_at: '' })),

    repeatable('Provider notification',
      'The single most load-bearing record in this tool. In a case where a patient '
      + 'deteriorated, the question is almost never whether the nurse noticed — it '
      + 'is whether the nurse escalated and what came back. "MD aware" answers '
      + 'none of it.',
      draft.notifications, [
        { key: 'notified_at', label: 'Exact time notified', kind: 'time' },
        { key: 'provider_name', label: 'Provider name' },
        { key: 'provider_role', label: 'Role' },
        {
          key: 'method', label: 'Method', kind: 'select',
          options: ['paged', 'phone', 'secure text', 'in person', 'bedside', 'overhead'],
        },
        { key: 'reason', label: 'Reason — the change in status' },
        { key: 'information_given', label: 'Data reported', kind: 'textarea' },
        { key: 'response_at', label: 'Time of response', kind: 'time' },
        { key: 'response', label: 'What they said', kind: 'textarea' },
        { key: 'orders_received', label: 'Orders received', kind: 'textarea' },
        { key: 'read_back', label: 'Orders read back', kind: 'checkbox' },
        { key: 'no_new_orders', label: 'No new orders', kind: 'checkbox' },
        { key: 'no_response', label: 'No response received', kind: 'checkbox' },
        { key: 'escalated_to', label: 'Escalated to' },
        { key: 'escalated_at', label: 'Escalated at', kind: 'time' },
        { key: 'escalation_response', label: 'Escalation response', kind: 'textarea' },
      ], () => ({ notified_at: toIso(localNow()), provider_name: '', method: '' })),

    draft.scales.length ? card('Scores attached to this note',
      el('div', { class: 'list' }, draft.scales.map((scale, index) =>
        el('div', { class: 'list-row' },
          el('div', {}, el('strong', {}, scale.scale_name),
            el('div', { class: 'hint' }, scale.narrative)),
          el('button', {
            class: 'button button-quiet button-small',
            onclick: () => { draft.scales.splice(index, 1); renderChart(); },
          }, 'Remove')))) ) : null,

    card('Composed note',
      el('p', { class: 'hint' },
        'Assembled from the sections above in SBAR-SOAP order: observation before '
        + 'impression. Edit it freely — your words win, and the checker follows '
        + 'your edit rather than double-reporting the same sentence.'),
      composed,
      el('div', { class: 'row-actions' },
        el('button', {
          class: 'button button-quiet',
          onclick: () => {
            draft.narrativeEdited = false;
            draft.narrative = '';
            renderChart();
            schedulePreview();
          },
        }, 'Rebuild from sections'),
        el('button', {
          class: 'button button-quiet',
          onclick: () => guard(async () => {
            const text = draft.narrativeEdited
              ? draft.narrative
              : (chartState.preview && chartState.preview.narrative) || '';
            const result = await chartApi('/phi-redact', { text });
            draft.narrative = result.text;
            draft.narrativeEdited = true;
            toast(result.redacted
              ? `Redacted ${result.redacted} identifier(s).`
              : 'No identifiers found.');
            renderChart();
            schedulePreview();
          }),
        }, 'Redact identifiers'),
        el('button', {
          class: 'button button-quiet',
          onclick: () => {
            const text = draft.narrativeEdited
              ? draft.narrative
              : (chartState.preview && chartState.preview.narrative) || '';
            navigator.clipboard.writeText(text).then(
              () => toast('Copied. Paste it into the EHR, then mark it transcribed.'),
              () => toast('Could not copy — select the text and copy manually.', true));
          },
        }, 'Copy for the EHR'))),

    el('div', { id: 'gate-panel' }, gatePanel()),

    el('div', { class: 'sticky-actions' }, saveButton,
      el('span', { class: 'hint' },
        chartState.preview && chartState.preview.gate.blocked
          ? 'Save is disabled by an interlock — see Checks above.'
          : 'The server runs the same checks again on save.')));
}

function encounterStrip() {
  const encounter = chartState.encounter;
  const derived = encounter._derived || {};
  const bits = [
    chip(encounter.local_label || encounter.encounter_id),
    encounter.initials ? chip(encounter.initials) : null,
    chip(encounter.setting.replace(/_/g, '-')),
    encounter.code_status ? chip('code: ' + encounter.code_status) : null,
    encounter.allergies ? chip('allergy: ' + encounter.allergies, 'warn') : null,
    derived.weight_recorded
      ? chip(encounter.weight_kg + ' kg')
      : (derived.requires_weight ? chip('no weight — medications blocked', 'bad') : null),
    derived.overdue_count ? chip(derived.overdue_count + ' overdue', 'bad') : null,
    (derived.untranscribed || []).length
      ? chip((derived.untranscribed || []).length + ' untranscribed', 'warn') : null,
  ];
  return el('div', { class: 'encounter-strip' }, bits.filter(Boolean));
}

/* -------------------------------------------------------------- head to toe */

function viewAssess() {
  const draft = chartState.draft;
  const cards = (chartState.ref.systems || []).map((system) => {
    const stored = draft.systems[system.system_id]
      || (draft.systems[system.system_id] = { wdl: false, findings: {}, exceptions: [] });

    const wdl = el('input', { type: 'checkbox' });
    wdl.checked = !!stored.wdl;
    wdl.addEventListener('change', () => {
      stored.wdl = wdl.checked;
      if (stored.wdl) stored.notAssessed = false;
      renderChart();
      schedulePreview();
    });

    const notAssessed = el('input', { type: 'checkbox' });
    notAssessed.checked = !!stored.notAssessed;
    notAssessed.addEventListener('change', () => {
      stored.notAssessed = notAssessed.checked;
      if (stored.notAssessed) stored.wdl = false;
      renderChart();
      schedulePreview();
    });

    const reason = el('input', {
      type: 'text', placeholder: 'patient off the unit for imaging',
      oninput: (e) => { stored.notAssessedReason = e.target.value; schedulePreview(); },
    });
    reason.value = stored.notAssessedReason || '';

    const elementFields = system.elements.map((element) => {
      if (element.free_text) {
        const area = el('textarea', {
          rows: 2,
          oninput: (e) => {
            stored.findings[element.element_id] = e.target.value;
            schedulePreview();
          },
        });
        area.value = stored.findings[element.element_id] || '';
        return field(element.label, area, element.hint);
      }
      const select = el('select', {
        onchange: (e) => {
          if (e.target.value) stored.findings[element.element_id] = e.target.value;
          else delete stored.findings[element.element_id];
          schedulePreview();
        },
      }, [el('option', { value: '' }, '—')].concat(element.options.map((option) =>
        el('option', {
          value: option,
          selected: stored.findings[element.element_id] === option,
        }, option))));
      const marker = element.normal && stored.findings[element.element_id]
        && stored.findings[element.element_id] !== element.normal
        ? ' · abnormal' : '';
      return field(element.label + marker, select, element.hint);
    });

    return card(system.label,
      el('div', { class: 'toggle-row' },
        el('label', { class: 'inline-check' }, wdl, ' Within defined limits'),
        el('label', { class: 'inline-check' }, notAssessed, ' Not assessed')),
      stored.notAssessed ? field('Why not', reason,
        'Recorded as not assessed rather than left blank. A blank system and a '
        + 'skipped system look identical in a chart, and only one is defensible.')
        : null,
      stored.wdl ? el('p', { class: 'wdl-statement' },
        el('strong', {}, 'WDL for this system asserts: '), system.wdl_statement)
        : null,
      stored.notAssessed ? null : el('div', { class: 'grid-fields' }, elementFields));
  });

  return el('section', { class: 'stack' },
    disclosureBanner(),
    encounterStrip(),
    card('Charting by exception',
      el('p', { class: 'hint' },
        'Marking a system within defined limits prints the full defined-limits '
        + 'statement into the note, verbatim. That is what makes charting by '
        + 'exception defensible: "Neuro WDL" on its own is worth nothing in a '
        + 'deposition, because the question is always what you actually checked. '
        + 'Selecting an abnormal finding while WDL is on renders as "within '
        + 'defined limits except …", which is the ordinary case.')),
    ...cards);
}

/* ------------------------------------------------------------------- scales */

function viewScales() {
  const derived = chartState.encounter._derived || {};
  const priority = derived.priority_scales || [];
  const all = chartState.ref.scales || [];
  const ordered = priority.map((id) => all.find((s) => s.scale_id === id))
    .filter(Boolean)
    .concat(all.filter((s) => !priority.includes(s.scale_id)));

  const picker = el('select', {
    onchange: (event) => {
      chartState.scaleDraft = { scaleId: event.target.value, responses: {} };
      renderChart();
    },
  }, [el('option', { value: '' }, 'Choose a scale…')].concat(ordered.map((scale) =>
    el('option', {
      value: scale.scale_id,
      selected: scale.scale_id === chartState.scaleDraft.scaleId,
    }, `${scale.name}${priority.includes(scale.scale_id) ? ' ★' : ''}`))));

  const children = [
    card('Scoring scales',
      el('p', { class: 'hint' },
        'Scales marked ★ are the ones this setting reaches for first. Every score '
        + 'is computed from your selections and shown to you — none of them '
        + 'returns an action, and the Emergency Severity Index in particular '
        + 'computes a level from the decision points you answer and shows the '
        + 'working rather than reading your vitals and proposing one.'),
      field('Scale', picker)),
  ];

  const scale = ordered.find((s) => s.scale_id === chartState.scaleDraft.scaleId);
  if (scale) children.push(scaleCard(scale));

  return el('section', { class: 'stack' },
    disclosureBanner(), encounterStrip(), ...children);
}

function scaleCard(scale) {
  const responses = chartState.scaleDraft.responses;
  const result = el('div', { class: 'score-result' });

  const compute = () => guard(async () => {
    const payload = await chartApi('/score', {
      scale_id: scale.scale_id, responses,
    });
    const r = payload.result;
    result.replaceChildren(
      el('div', { class: 'score-headline' },
        r.score === null ? '—' : String(r.score),
        el('span', { class: 'score-band' }, r.band || '')),
      el('p', {}, r.narrative),
      r.incomplete.length
        ? notice('Not scored: ' + r.incomplete.join(', '), 'warn') : null,
      el('button', {
        class: 'button',
        onclick: () => {
          chartState.draft.scales.push(r);
          toast('Added to the note.');
          goChart('note');
          schedulePreview();
        },
      }, 'Add to the note'));
  });

  const items = scale.items.map((item) => {
    const select = el('select', {
      onchange: (event) => {
        if (event.target.value) responses[item.item_id] = event.target.value;
        else delete responses[item.item_id];
        compute();
      },
    }, [el('option', { value: '' }, '—')].concat(item.options.map((option) =>
      el('option', {
        value: option.key,
        selected: responses[item.item_id] === option.key,
      }, `${option.label}${option.points ? ` (${option.points})` : ''}`))));
    return field(item.label + (item.optional ? ' (optional)' : ''), select,
      item.source_hint);
  });

  const prefill = el('button', {
    class: 'button button-quiet',
    onclick: () => guard(async () => {
      const payload = await chartApi('/scale-prefill', {
        scale_id: scale.scale_id, vitals: chartState.draft.vitals,
      });
      const suggested = payload.prefill || {};
      if (!Object.keys(suggested).length) {
        toast('Nothing on this scale can be answered from the vitals you recorded.');
        return;
      }
      Object.assign(responses, suggested);
      toast(payload.caveat);
      renderChart();
      compute();
    }),
  }, 'Fill from recorded vitals');

  return card(`${scale.name}${scale.abbreviation ? ` (${scale.abbreviation})` : ''}`,
    el('p', {}, scale.purpose),
    scale.note ? notice(scale.note, 'warn') : null,
    el('p', { class: 'hint citation' }, scale.citation),
    ['qsofa', 'mews', 'news2', 'nrs', 'wong_baker'].includes(scale.scale_id)
      ? prefill : null,
    scale.scale_id === 'esi' ? esiHelper() : null,
    el('div', { class: 'grid-fields' }, items),
    result,
    scale.bands.length ? el('div', { class: 'table-wrap' }, el('table', {},
      el('thead', {}, el('tr', {}, el('th', {}, 'Range'), el('th', {}, 'Band'),
        el('th', {}, 'What the instrument associates with it'))),
      el('tbody', {}, scale.bands.map((band) => el('tr', {},
        el('td', {}, `${band.low}–${band.high}`),
        el('td', {}, band.label),
        el('td', {}, band.detail)))))) : null);
}

function esiHelper() {
  const bands = chartState.ref.esi_vital_limits || [];
  const picker = el('select', {}, bands.map((b) =>
    el('option', { value: b.key }, b.label)));
  const out = el('div', {});
  return el('div', { class: 'subcard' },
    el('h3', {}, 'Decision point D — danger-zone vitals'),
    el('p', { class: 'hint' },
      'The published thresholds are shown so your answer is informed rather than '
      + 'remembered. You answer the question; the tool does not assign a level '
      + 'from vital signs, because a triage acuity a tool assigned is not one '
      + 'anybody can defend.'),
    el('div', { class: 'grid-fields' }, field('Age band', picker)),
    el('button', {
      class: 'button button-quiet button-small',
      onclick: () => guard(async () => {
        const payload = await chartApi('/esi-danger-zone', {
          age_band: picker.value, vitals: chartState.draft.vitals,
        });
        out.replaceChildren(
          payload.exceeded.length
            ? el('ul', { class: 'plain-list' },
              payload.exceeded.map((line) => el('li', {}, line)))
            : el('p', { class: 'hint' },
              'No recorded vital exceeds the thresholds for this age band.'),
          el('div', { class: 'table-wrap' }, el('table', {},
            el('thead', {}, el('tr', {}, el('th', {}, 'Age band'),
              el('th', {}, 'HR above'), el('th', {}, 'RR above'))),
            el('tbody', {}, (payload.limits || []).map((limit) => el('tr', {},
              el('td', {}, limit.label),
              el('td', {}, String(limit.heart_rate_above)),
              el('td', {}, String(limit.respiratory_rate_above))))))));
      }),
    }, 'Compare recorded vitals'),
    out);
}

/* ------------------------------------------------------------------- macros */

function viewMacros() {
  const macros = chartState.ref.macros || [];
  const picker = el('select', {
    onchange: (event) => {
      chartState.macroDraft = { macroId: event.target.value, values: {} };
      renderChart();
    },
  }, [el('option', { value: '' }, 'Choose a template…')].concat(macros.map((macro) =>
    el('option', {
      value: macro.macro_id,
      selected: macro.macro_id === chartState.macroDraft.macroId,
    }, macro.label))));

  const children = [card('Templates',
    el('p', { class: 'hint' },
      'Six situations where the words are hard to find under pressure and the cost '
      + 'of getting them wrong is high. They are filled from fields rather than '
      + 'pasted as snippets, so a template cannot carry the previous patient\'s '
      + 'numbers into this note — which is the failure mode of every snippet '
      + 'library in every EHR.'),
    field('Template', picker))];

  const macro = macros.find((m) => m.macro_id === chartState.macroDraft.macroId);
  if (macro) children.push(macroCard(macro));
  return el('section', { class: 'stack' },
    disclosureBanner(), encounterStrip(), ...children);
}

function macroCard(macro) {
  const values = chartState.macroDraft.values;
  const output = el('div', {});

  const render = () => guard(async () => {
    const payload = await chartApi('/macro', {
      macro_id: macro.macro_id, values,
    });
    output.replaceChildren(
      payload.missing_required.length
        ? notice('Still needed: ' + payload.missing_required.join(', ')
          + '. Whichever element is missing is the one counsel will ask about.',
          'warn')
        : null,
      el('pre', { class: 'macro-output' }, payload.text),
      ...(payload.flags || []).map((flag) => flagRow(flag)),
      el('div', { class: 'row-actions' },
        el('button', {
          class: 'button',
          onclick: () => {
            const draft = chartState.draft;
            draft.plan = (draft.plan ? draft.plan + '\n\n' : '') + payload.text;
            const kindFor = {
              refusal: 'refusal', restraint: 'restraint', fall: 'fall_event',
              blood_product: 'blood_product', education: 'education',
              chain_of_command: 'provider_notification',
            }[macro.macro_id];
            if (kindFor) draft.kind = kindFor;
            // The interlocks for these note kinds read module_data, so the filled
            // values travel with the note rather than only its rendered text.
            const slot = { fall_event: 'fall', refusal: 'refusal',
              restraint: 'restraint', blood_product: 'blood_product',
              education: 'education' }[kindFor];
            if (slot) draft.module_data[slot] = Object.assign({}, values);
            toast('Added to the note\'s plan section.');
            goChart('note');
            schedulePreview();
          },
        }, 'Add to the note'),
        el('button', {
          class: 'button button-quiet',
          onclick: () => navigator.clipboard.writeText(payload.text).then(
            () => toast('Copied.'), () => toast('Could not copy.', true)),
        }, 'Copy')));
  });

  const fields = macro.fields.map((f) => {
    let input;
    if (f.type === 'textarea') input = el('textarea', { rows: 3 });
    else if (f.type === 'select') {
      input = el('select', {}, [el('option', { value: '' }, '—')].concat(
        (f.options || []).map((o) => el('option', { value: o }, o))));
    } else if (f.type === 'time') {
      input = el('input', { type: 'text', placeholder: '1412', inputmode: 'numeric' });
    } else input = el('input', { type: 'text' });
    if (values[f.key] !== undefined) input.value = values[f.key];
    input.addEventListener(f.type === 'select' ? 'change' : 'input', (event) => {
      values[f.key] = event.target.value;
      render();
    });
    return field(f.label + (f.required ? ' *' : ''), input, f.hint);
  });

  return card(macro.label,
    el('p', {}, macro.purpose),
    macro.guidance ? notice(macro.guidance, 'warn') : null,
    el('div', { class: 'grid-fields' }, fields),
    output);
}

/* ----------------------------------------------------------- module & bundles */

function viewModule() {
  const derived = chartState.encounter._derived || {};
  const module = derived.module;
  const children = [];

  if (!module) {
    children.push(card('No specialty module',
      el('p', { class: 'hint' },
        'This encounter\'s setting has no extra module. The note composer and the '
        + 'head-to-toe assessment are the same in every setting.')));
  } else {
    children.push(card(module.label, el('p', {}, module.summary)));
    for (const block of module.blocks) {
      const stored = chartState.draft.module_data[block.block_id]
        || (chartState.draft.module_data[block.block_id] = block.repeatable ? [] : {});

      if (block.repeatable) {
        children.push(repeatable(block.label, block.why, stored,
          block.fields.map((f) => ({
            key: f.key, label: f.label + (f.required ? ' *' : ''),
            kind: f.kind === 'textarea' ? 'textarea'
              : (f.kind === 'select' ? 'select'
                : (f.kind === 'checkbox' ? 'checkbox'
                  : (f.kind === 'number' ? 'number' : 'text'))),
            options: f.options, hint: f.hint,
          })), () => ({})));
      } else {
        const fields = block.fields.map((f) => {
          let input;
          if (f.kind === 'textarea') input = el('textarea', { rows: 2 });
          else if (f.kind === 'select') {
            input = el('select', {}, [el('option', { value: '' }, '—')].concat(
              (f.options || []).map((o) => el('option', { value: o }, o))));
          } else if (f.kind === 'checkbox') {
            input = el('input', { type: 'checkbox' });
            input.checked = !!stored[f.key];
          } else {
            input = el('input', {
              type: f.kind === 'number' ? 'number' : 'text',
              step: f.kind === 'number' ? 'any' : undefined,
            });
          }
          if (f.kind !== 'checkbox' && stored[f.key] !== undefined) {
            input.value = stored[f.key];
          }
          input.addEventListener(
            f.kind === 'checkbox' ? 'change' : (f.kind === 'select' ? 'change' : 'input'),
            (event) => {
              stored[f.key] = f.kind === 'checkbox'
                ? event.target.checked : event.target.value;
              schedulePreview();
            });
          return field(f.label + (f.required ? ' *' : ''), input, f.hint);
        });
        children.push(card(block.label,
          block.why ? el('p', { class: 'hint' }, block.why) : null,
          el('div', { class: 'grid-fields' }, fields)));
      }
    }
  }

  children.push(bundleCard());
  children.push(encounterDetailsCard());
  return el('section', { class: 'stack' },
    disclosureBanner(), encounterStrip(), ...children);
}

function bundleCard() {
  const bundles = chartState.ref.bundles || [];
  const picker = el('select', {
    onchange: (event) => {
      chartState.bundleDraft = { bundleId: event.target.value, values: {} };
      renderChart();
    },
  }, [el('option', { value: '' }, 'Choose a bundle…')].concat(bundles.map((b) =>
    el('option', {
      value: b.bundle_id, selected: b.bundle_id === chartState.bundleDraft.bundleId,
    }, b.label))));

  const bundle = bundles.find((b) => b.bundle_id === chartState.bundleDraft.bundleId);
  const output = el('div', {});
  if (!bundle) {
    return card('Time-critical bundles',
      el('p', { class: 'hint' },
        'Sepsis, stroke and STEMI timing. These cut across settings — sepsis '
        + 'presents to the emergency department, is recognised on a ward and is '
        + 'managed in intensive care — so they live here rather than in one '
        + 'module.'),
      field('Bundle', picker));
  }

  const values = chartState.bundleDraft.values;
  const render = () => guard(async () => {
    const payload = await chartApi('/bundle', {
      bundle_id: bundle.bundle_id, values,
    });
    const status = payload.status;
    output.replaceChildren(
      status.note ? notice(status.note, 'bad') : null,
      status.exceeded.length
        ? notice('Targets exceeded: ' + status.exceeded.join('; ')
          + '. Record it accurately — a bundle element that ran late and is '
          + 'documented honestly is defensible; one that is quietly adjusted is '
          + 'not.', 'warn')
        : null,
      el('pre', { class: 'macro-output' }, payload.text),
      el('button', {
        class: 'button',
        onclick: () => {
          const draft = chartState.draft;
          draft.objective = (draft.objective ? draft.objective + '\n\n' : '')
            + payload.text;
          toast('Added to the note.');
          goChart('note');
          schedulePreview();
        },
      }, 'Add to the note'));
  });

  const fields = bundle.elements.map((element) => {
    const input = el('input', {
      type: 'text', placeholder: '1412', inputmode: 'numeric',
      oninput: (event) => { values[element.key] = event.target.value; render(); },
    });
    if (values[element.key] !== undefined) input.value = values[element.key];
    const label = element.label + (element.required ? ' *' : '')
      + (element.target_minutes ? ` (target ${element.target_minutes} min)` : '');
    return field(label, input, element.hint);
  });

  return card('Time-critical bundles',
    field('Bundle', picker),
    notice(bundle.why, 'warn'),
    el('p', { class: 'hint citation' }, bundle.citation),
    el('div', { class: 'grid-fields' }, fields),
    output);
}

function encounterDetailsCard() {
  const encounter = chartState.encounter;
  const values = {};
  const make = (key, label, hint, type = 'text') => {
    const input = el('input', { type, step: type === 'number' ? 'any' : undefined });
    if (encounter[key] !== null && encounter[key] !== undefined) {
      input.value = encounter[key];
    }
    input.addEventListener('input', (event) => { values[key] = event.target.value; });
    return field(label, input, hint);
  };

  const interpreterUsed = el('input', { type: 'checkbox' });
  interpreterUsed.checked = !!encounter.interpreter_used;
  interpreterUsed.addEventListener('change', () => {
    values.interpreter_used = interpreterUsed.checked;
  });

  return card('Encounter details',
    el('p', { class: 'hint' },
      'Facts that belong to the patient rather than to one note. On a paediatric '
      + 'encounter a weight in kilograms is required before any medication can be '
      + 'documented — that is a hard stop, not a reminder.'),
    el('div', { class: 'grid-fields' },
      make('code_status', 'Code status'),
      make('advance_directive', 'Advance directive'),
      make('allergies', 'Allergies and reactions'),
      make('isolation', 'Isolation'),
      make('diagnosis_summary', 'Working diagnosis'),
      make('age_band', 'Age band', 'not a date of birth'),
      make('weight_kg', 'Weight', 'kilograms only', 'number'),
      make('height_cm', 'Height', 'centimetres', 'number'),
      make('language', 'Language'),
      make('interpreter_id', 'Interpreter identifier'),
      make('baseline_mental_status', 'Baseline mental status',
        'delirium screening is interpreted against this'),
      field('Interpreter used', interpreterUsed)),
    el('button', {
      class: 'button',
      onclick: () => guard(async () => {
        values.author_initials = chartState.author;
        const result = await chartApi(
          `/encounters/${encounter.encounter_id}/details`, values);
        chartState.encounter = result.encounter;
        toast('Details saved.');
        renderChart();
      }),
    }, 'Save details'));
}

/* -------------------------------------------------------------------- loops */

function viewLoops() {
  const derived = chartState.encounter._derived || {};
  const loops = derived.open_loops || [];

  const rows = loops.map((loop) => {
    const finding = el('input', {
      type: 'text',
      placeholder: 'Pain reassessed at 1445: reports 3/10, resting comfortably',
    });
    const notDone = el('input', {
      type: 'text', placeholder: 'patient off the unit for imaging',
    });
    return el('div', { class: `claim ${loop.overdue ? 'claim-unsupported' : ''}` },
      el('div', { class: 'claim-text' }, el('strong', {}, loop.trigger)),
      el('div', { class: 'claim-meta' },
        chip('due ' + clock(loop.due_at)),
        chip(loop.window_minutes + ' min window'),
        loop.overdue ? chip(loop.minutes_late + ' min overdue', 'bad') : chip('open')),
      field('What you found', finding),
      field('Or why it was not done', notDone),
      el('button', {
        class: 'button button-quiet button-small',
        onclick: () => guard(async () => {
          const result = await chartApi(
            `/encounters/${chartState.encounter.encounter_id}/loops/`
            + loop.reassessment_id, {
              finding: finding.value.trim(),
              not_done_reason: notDone.value.trim(),
              author_initials: chartState.author,
            });
          chartState.encounter = result.encounter;
          toast('Loop closed.');
          renderChart();
        }),
      }, 'Close this loop'));
  });

  return el('section', { class: 'stack' },
    disclosureBanner(), encounterStrip(),
    card('Open reassessments',
      el('p', { class: 'hint' },
        'A loop opens automatically when something is given or done whose effect '
        + 'must be documented — an analgesic opens a 30-minute pain reassessment, '
        + 'a pressor titration a 15-minute haemodynamic recheck, a blood product a '
        + '15-minute reaction check. A window that closed with neither a finding '
        + 'nor a reason is the gap a reviewer finds. If you did it and did not '
        + 'chart it, close it now — that is a late entry, which is fine, and the '
        + 'tool labels it.'),
      loops.length ? el('div', { class: 'list' }, rows)
        : el('p', { class: 'hint' }, 'Nothing owed.')),
    card('How loops are opened',
      el('div', { class: 'table-wrap' }, el('table', {},
        el('thead', {}, el('tr', {}, el('th', {}, 'Trigger'),
          el('th', {}, 'Window'), el('th', {}, 'What is owed'))),
        el('tbody', {}, (chartState.ref.loop_rules || []).map((rule) =>
          el('tr', {}, el('td', {}, rule.key.replace(/_/g, ' ')),
            el('td', {}, rule.minutes + ' min'), el('td', {}, rule.what))))))));
}

/* ----------------------------------------------------------------- timeline */

function viewTimeline() {
  const encounter = chartState.encounter;
  const entries = (encounter.entries || []).slice().sort((a, b) =>
    String(a.event_at).localeCompare(String(b.event_at)));

  const rows = entries.map((entry) => {
    const reviseText = el('textarea', { rows: 4 });
    reviseText.value = entry.narrative || '';
    const reason = el('select', {}, [
      'typographical error', 'wrong chart', 'addendum — new information',
      'addendum — completed intervention', 'clarification',
    ].map((r) => el('option', { value: r }, r)));
    const otherReason = el('input', { type: 'text', placeholder: 'or type a reason' });

    return el('div', { class: 'card' },
      el('div', { class: 'claim-meta' },
        el('strong', {}, entry.late_entry ? '[LATE ENTRY] ' : ''),
        chip(clock(entry.event_at) + ' event'),
        chip(clock(entry.documented_at) + ' documented'),
        entry.late_by_minutes
          ? chip(entry.late_by_minutes + ' min gap', 'warn') : null,
        chip(entry.kind.replace(/_/g, ' ')),
        entry.transcribed_at
          ? chip('transcribed ' + clock(entry.transcribed_at), 'good')
          : chip('not transcribed', 'bad'),
        (entry.revisions || []).length
          ? chip((entry.revisions || []).length + ' correction(s)', 'warn') : null),
      el('pre', { class: 'macro-output' }, entry.narrative),
      (entry.revisions || []).length ? el('div', { class: 'subcard' },
        el('h3', {}, 'Corrections'),
        ...(entry.revisions || []).map((revision) => el('div', {},
          el('p', { class: 'hint' },
            `${clock(revision.revised_at)} · ${revision.author_initials || '—'} · `
            + `reason: ${revision.reason}`),
          el('p', { class: 'struck' }, revision.previous_text)))) : null,
      el('div', { class: 'row-actions' },
        el('button', {
          class: 'button',
          onclick: () => guard(async () => {
            const result = await chartApi(
              `/encounters/${encounter.encounter_id}/entries/${entry.entry_id}/transcribed`,
              { author_initials: chartState.author, undo: !!entry.transcribed_at });
            chartState.encounter = result.encounter;
            renderChart();
          }),
        }, entry.transcribed_at ? 'Mark not transcribed' : 'Mark transcribed in the EHR'),
        el('button', {
          class: 'button button-quiet',
          onclick: () => navigator.clipboard.writeText(entry.narrative).then(
            () => toast('Copied.'), () => toast('Could not copy.', true)),
        }, 'Copy')),
      el('details', {}, el('summary', {}, 'Correct this note'),
        el('p', { class: 'hint' },
          'Nothing is overwritten. The previous text is kept and printed struck '
          + 'through in the export, exactly as a single line through an error on a '
          + 'paper chart. A reason is required — an unexplained change to a '
          + 'clinical note is the fact pattern that turns a defensible record into '
          + 'an indefensible one.'),
        field('Corrected text', reviseText),
        field('Reason', reason),
        field('Other reason', otherReason),
        el('button', {
          class: 'button',
          onclick: () => guard(async () => {
            const result = await chartApi(
              `/encounters/${encounter.encounter_id}/entries/${entry.entry_id}/revise`,
              {
                new_text: reviseText.value,
                reason: otherReason.value.trim() || reason.value,
                author_initials: chartState.author,
              });
            chartState.encounter = result.encounter;
            toast('Correction appended. The original text is kept.');
            renderChart();
          }),
        }, 'Append correction')));
  });

  return el('section', { class: 'stack' },
    disclosureBanner(), encounterStrip(),
    card('Notes on this encounter',
      el('p', { class: 'hint' },
        'A note that lives only here is a note that is not in the patient\'s '
        + 'record. Transcribe each one into the EHR and mark it — a draft that '
        + 'disagrees with the chart helps the other side, not you.'),
      entries.length ? null : el('p', { class: 'hint' }, 'No notes yet.')),
    ...rows);
}

/* ------------------------------------------------------------------ handoff */

function viewHandoff() {
  const routes = chartState.ref.handoff_routes || [];
  const picker = el('select', {
    onchange: (event) => {
      chartState.handoffDraft = { route: event.target.value, values: {} };
      renderChart();
    },
  }, [el('option', { value: '' }, 'Choose a transition…')].concat(routes.map((r) =>
    el('option', {
      value: r.route, selected: r.route === chartState.handoffDraft.route,
    }, r.label))));

  const children = [card('Handoff',
    el('p', { class: 'hint' },
      'Required items you have not filled are printed as NOT HANDED OVER rather '
      + 'than omitted. A handoff that silently drops the airway line is worse than '
      + 'one that says the airway was not handed over, because the receiving nurse '
      + 'cannot know what they were not told.'),
    field('Transition', picker))];

  const route = routes.find((r) => r.route === chartState.handoffDraft.route);
  if (route) children.push(handoffCard(route));
  return el('section', { class: 'stack' },
    disclosureBanner(), encounterStrip(), ...children);
}

function handoffCard(route) {
  const output = el('div', {});
  const values = chartState.handoffDraft.values;
  const host = el('div', { class: 'grid-fields' },
    el('p', { class: 'hint' }, 'Loading…'));

  guard(async () => {
    const template = await api('/api/charting/handoff/' + route.route);
    const fields = template.fields.map((f) => {
      const area = el('textarea', {
        rows: 2,
        oninput: (event) => { values[f.key] = event.target.value; },
      });
      if (values[f.key] !== undefined) area.value = values[f.key];
      return field(f.label + (f.required ? ' *' : ''), area);
    });
    host.replaceChildren(...fields);
  });

  return card(route.label,
    notice(route.why, 'warn'),
    host,
    el('button', {
      class: 'button',
      onclick: () => guard(async () => {
        const payload = await chartApi(
          `/encounters/${chartState.encounter.encounter_id}/handoff`,
          { route_name: route.route, values });
        output.replaceChildren(
          el('pre', { class: 'macro-output' }, payload.text),
          payload.untranscribed
            ? notice(`${payload.untranscribed} note(s) on this encounter are not `
              + 'transcribed into the EHR. Transcribe them before you leave — the '
              + 'receiving nurse cannot see this tool.', 'bad')
            : null,
          el('button', {
            class: 'button button-quiet',
            onclick: () => navigator.clipboard.writeText(payload.text).then(
              () => toast('Copied.'), () => toast('Could not copy.', true)),
          }, 'Copy'));
      }),
    }, 'Build handoff'),
    output);
}

/* ------------------------------------------------------------------- export */

function viewChartExport() {
  const encounter = chartState.encounter;
  const derived = encounter._derived || {};
  const files = el('div', { class: 'list' });
  const refreshFiles = () => guard(async () => {
    const result = await api(
      `/api/charting/encounters/${encounter.encounter_id}/files`);
    files.replaceChildren();
    if (!(result.files || []).length) {
      files.append(el('p', { class: 'hint' }, 'Nothing exported yet.'));
      return;
    }
    for (const file of result.files) {
      files.append(el('div', { class: 'list-row' },
        el('div', {}, el('strong', {}, file.name),
          el('div', { class: 'hint' }, Math.round(file.bytes / 1024) + ' KB')),
        el('a', {
          class: 'button button-quiet button-small',
          href: `/api/charting/encounters/${encounter.encounter_id}/files/`
            + encodeURIComponent(file.name)
            + '?token=' + encodeURIComponent(state.token),
        }, 'Download')));
    }
  });
  refreshFiles();

  const audit = el('div', {});
  const refreshAudit = () => guard(async () => {
    const result = await api(
      `/api/charting/encounters/${encounter.encounter_id}/audit`);
    const v = result.verification;
    audit.replaceChildren(
      notice(v.reason, v.intact ? 'good' : 'bad'),
      el('div', { class: 'table-wrap' }, el('table', {},
        el('thead', {}, el('tr', {}, el('th', {}, 'When'), el('th', {}, 'Action'),
          el('th', {}, 'Detail'), el('th', {}, 'By'), el('th', {}, 'Digest'))),
        el('tbody', {}, (result.events || []).map((event) => el('tr', {},
          el('td', {}, clock(event.at)),
          el('td', {}, event.action.replace(/_/g, ' ')),
          el('td', {}, event.detail),
          el('td', {}, event.author_initials || '—'),
          el('td', {}, el('span', { class: 'overlap-phrase' }, event.digest))))))));
  });
  refreshAudit();

  return el('section', { class: 'stack' },
    disclosureBanner(), encounterStrip(),

    (derived.untranscribed || []).length
      ? notice(`${(derived.untranscribed || []).length} note(s) have not been `
        + 'transcribed into the EHR. They will be printed first in the export and '
        + 'marked. The exported file is not the legal record either.', 'bad')
      : null,

    card('Export',
      el('p', { class: 'hint' },
        'Two documents. The shift record is the notes themselves, untranscribed '
        + 'ones first. The audit appendix is the provenance: the timestamp ledger, '
        + 'every correction with its superseded text struck through, every '
        + 'interlock that fired, the instruments cited, and the audit-chain '
        + 'verification.'),
      el('button', {
        class: 'button',
        onclick: () => guard(async () => {
          const result = await chartApi(
            `/encounters/${encounter.encounter_id}/export`,
            { author: [chartState.author, chartState.credential].filter(Boolean).join(', ') });
          if (result.warning) toast(result.warning, true);
          else toast('Exported.');
          refreshFiles();
          refreshAudit();
        }),
      }, 'Export both documents')),

    card('Files', files),
    card('Audit chain', audit));
}

/* ---------------------------------------------------------------- reference */

function viewReference() {
  const ref = chartState.ref;
  return el('section', { class: 'stack' },
    disclosureBanner(),

    card('Objective language filter',
      el('p', { class: 'hint' },
        'The whole rule set, shown deliberately. A nurse who understands why '
        + '"sleeping" is flagged writes better notes everywhere, including in the '
        + 'EHR where this tool cannot follow them. Quoted speech is exempt from '
        + 'every rule — what the patient said is data.'),
      ...(ref.language_rules || []).map((group) => el('div', { class: 'subcard' },
        el('h3', {}, group.label),
        el('div', { class: 'list' }, group.rules.map((rule) =>
          el('div', { class: 'claim' },
            el('div', { class: 'claim-meta' },
              chip(SEVERITY_LABEL[rule.severity] || rule.severity, rule.severity),
              el('span', { class: 'flag-code' }, rule.code.replace(/_/g, ' '))),
            el('p', {}, rule.message),
            el('p', { class: 'hint' }, rule.suggestion))))))),

    card('Critical value thresholds',
      el('p', { class: 'hint' },
        'Crossing one of these requires a provider notification before a note '
        + 'will save. They are common practice rather than your policy — if your '
        + 'unit\'s critical systolic is 85 rather than 90, the values in '
        + 'app/charting/interlocks.py are the ones to change, because a tool that '
        + 'fires on the wrong number either nags or, much worse, stays quiet.'),
      el('div', { class: 'table-wrap' }, el('table', {},
        el('thead', {}, el('tr', {}, el('th', {}, 'Measure'), el('th', {}, 'Low'),
          el('th', {}, 'High'))),
        el('tbody', {}, (ref.critical_thresholds || []).map((t) => el('tr', {},
          el('td', {}, t.label),
          el('td', {}, t.low === null ? '—' : String(t.low)),
          el('td', {}, t.high === null ? '—' : String(t.high)))))))),

    card('Chain of command',
      el('div', { class: 'list' }, (ref.escalation_ladder || []).map((rung, index) =>
        el('div', { class: 'claim' },
          el('div', { class: 'claim-text' },
            el('strong', {}, `${index + 1}. ${rung.rung}`)),
          el('p', { class: 'hint' }, rung.why))))),

    card('Scoring instrument licensing',
      el('p', { class: 'hint' },
        'Most bedside instruments are copyrighted, and several are trademarked and '
        + 'licensed. This tool implements the scoring arithmetic and the published '
        + 'thresholds — which are facts about an instrument — with item wording '
        + 'written fresh, and it reproduces no instrument artwork. Use your unit\'s '
        + 'licensed copy for the definitions; where the wording here is ambiguous '
        + 'against the real instrument, the real instrument governs.'),
      el('div', { class: 'list' }, (ref.scale_licensing || []).map((entry) =>
        el('div', { class: 'claim' },
          el('div', { class: 'claim-text' },
            el('strong', {}, entry.holder),
            el('span', { class: 'hint' }, ' — ' + entry.scales.join(', '))),
          el('p', { class: 'hint' }, entry.note))))),

    card('Identifier detection',
      el('p', { class: 'hint' }, (ref.phi || {}).summary || ''),
      el('div', { class: 'table-wrap' }, el('table', {},
        el('thead', {}, el('tr', {}, el('th', {}, 'Looks for'),
          el('th', {}, 'What to do'))),
        el('tbody', {}, ((ref.phi || {}).detectors || []).map((d) => el('tr', {},
          el('td', {}, d.label), el('td', {}, d.advice))))))),

    card('What this tab cannot do',
      el('div', { class: 'list' }, (ref.cannot_do || []).map((item) =>
        el('div', { class: 'claim' },
          el('div', { class: 'claim-text' }, el('strong', {}, item.claim)),
          el('p', { class: 'hint' }, item.reality))))));
}

/* ------------------------------------------------------------------ routing */

function renderChart() {
  const nav = document.getElementById('chart-nav');
  const host = document.getElementById('chart-view');
  if (!chartState.ref) {
    host.replaceChildren(el('p', { class: 'hint' }, 'Loading…'));
    return;
  }
  nav.hidden = !chartState.encounter;
  document.getElementById('encounter-label').hidden = !chartState.encounter;
  document.getElementById('switch-encounter').hidden = !chartState.encounter;
  document.getElementById('encounter-label').textContent = chartState.encounter
    ? (chartState.encounter.local_label || chartState.encounter.encounter_id) : '';
  for (const button of nav.querySelectorAll('button')) {
    button.classList.toggle('is-active', button.dataset.cview === chartState.view);
  }

  if (!chartState.encounter) {
    host.replaceChildren(viewEncounters());
    return;
  }
  if (!chartState.draft) chartState.draft = blankDraft();

  const views = {
    note: viewNote,
    assess: viewAssess,
    scales: viewScales,
    macros: viewMacros,
    module: viewModule,
    loops: viewLoops,
    timeline: viewTimeline,
    handoff: viewHandoff,
    chartexport: viewChartExport,
    reference: viewReference,
  };
  host.replaceChildren((views[chartState.view] || viewNote)());
}

function goChart(view) {
  chartState.view = view;
  renderChart();
}

async function initCharting() {
  if (chartState.ref) return;
  chartState.ref = await chartApi('/reference');
  chartState.draft = blankDraft();
  renderChart();
}

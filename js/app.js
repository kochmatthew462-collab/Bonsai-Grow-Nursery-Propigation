/*
 * Bonsai Nursery Tracker — routing and views.
 *
 * Five hash routes: the nursery list, a plant detail page, the printable label
 * sheet, sync settings, and backup. A QR label encodes <base>#/p/<id>, so
 * scanning it with any phone camera opens that plant's page directly.
 *
 * Which factors a plant records, and the bands they are judged against, come
 * from its care profile (js/profiles.js) — that is what lets one site carry
 * both an indoor bonsai bench and full-size trees living outdoors.
 */
(function (global) {
  'use strict';

  var store = global.BonsaiStore;
  var charts = global.BonsaiCharts;
  var profiles = global.BonsaiProfiles;
  var sync = global.BonsaiSync;
  var calendar = global.BonsaiCalendar;
  var weather = global.BonsaiWeather;
  var photos = global.BonsaiPhotos;
  var QR = global.BonsaiQR;

  var METRICS = profiles.metrics;
  var STAGES = ['cutting', 'air layer', 'seedling', 'stem graft', 'nursery stock',
    'in training', 'refinement', 'mature specimen', 'exhibition-ready'];
  var GRADES = ['', 'pre-bonsai', 'early refinement', 'refined', 'specimen', 'exhibition-ready'];
  var PROP_METHODS = ['', 'seed', 'cutting — softwood', 'cutting — hardwood', 'cutting — semi-ripe',
    'air layer', 'graft', 'collected (yamadori)', 'nursery stock', 'imported'];
  var FERT_METHODS = ['', 'drench', 'foliar', 'slow-release / pellets', 'organic tea'];
  // Wire bites fast in season — the ficus page says inspect every two weeks.
  var WIRE_INSPECT_DAYS = 14;
  var PESTS = ['spider mites', 'scale', 'mealybugs', 'fungus gnats', 'aphids',
    'citrus leaf miner', 'olive knot', 'peacock spot', 'other'];

  // Metrics grouped for the log form, so a phone-sized form stays readable.
  var FORM_GROUPS = [
    { title: 'Soil', keys: ['ph', 'moisture', 'ec', 'percolation'] },
    { title: 'Air and light', keys: ['tempLow', 'tempHigh', 'humidity', 'light', 'chill'] },
    { title: 'Growth and vigor', keys: ['growth', 'height', 'canopy', 'vigor'] }
  ];

  var STATUS_GLYPH = { good: '✓', warn: '▲', bad: '✕' };

  var BASE_URL_KEY = 'bonsai.labelBase.v1';

  /* ------------------------------------------------------------ DOM helper */

  // Everything user-entered goes in as text, never as markup.
  function h(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      var value = attrs[key];
      if (value == null || value === false) return;
      if (key === 'text') node.textContent = value;
      else if (key === 'html') node.innerHTML = value;
      else if (key === 'class') node.className = value;
      else if (key === 'style') node.setAttribute('style', value);
      else if (key.slice(0, 2) === 'on') node.addEventListener(key.slice(2), value);
      else if (key in node && key !== 'list' && key !== 'form') node[key] = value;
      else node.setAttribute(key, value);
    });
    (children || []).forEach(function (child) {
      if (child == null || child === false) return;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  }

  function field(labelText, control, hint) {
    return h('label', {}, [
      document.createTextNode(labelText),
      control,
      hint ? h('span', { class: 'hint', text: hint }) : null
    ]);
  }

  function download(filename, text, type) {
    var blob = new Blob([text], { type: type });
    var url = URL.createObjectURL(blob);
    var link = h('a', { href: url, download: filename });
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  /* --------------------------------------------------------- label base URL */

  function labelBase() {
    var stored = '';
    try { stored = global.localStorage.getItem(BASE_URL_KEY) || ''; } catch (e) { stored = ''; }
    if (stored) return stored.replace(/#.*$/, '');
    return (global.location.origin === 'null' ? '' : global.location.origin) + global.location.pathname;
  }

  function setLabelBase(value) {
    try { global.localStorage.setItem(BASE_URL_KEY, value.trim()); } catch (e) { /* ignore */ }
  }

  function plantUrl(id) {
    return labelBase() + '#/p/' + id;
  }

  /* ------------------------------------------------------- status & tiles */

  // Status is a glyph plus a word plus a colour, in that order of importance —
  // never colour on its own.
  function statusChip(status) {
    if (!status || status.level === 'none') return null;
    return h('span', { class: 'chip chip-' + status.level }, [
      h('span', { class: 'chip-glyph', 'aria-hidden': 'true', text: STATUS_GLYPH[status.level] }),
      h('span', { text: status.label })
    ]);
  }

  function statTile(label, value, unit, sub, color, status) {
    return h('div', { class: 'stat-tile' }, [
      h('div', { class: 'stat-label' }, [
        color ? h('span', { class: 'stat-key', style: 'background:' + color }) : null,
        h('span', { text: label })
      ]),
      h('div', { class: 'stat-value' }, [
        document.createTextNode(value),
        unit ? h('span', { class: 'unit', text: unit }) : null
      ]),
      status ? statusChip(status) : null,
      h('div', { class: 'stat-sub', text: sub || '' })
    ]);
  }

  // The worst status across everything currently measured on a plant.
  function worstStatus(plantId) {
    var plant = store.getPlant(plantId);
    var profile = profiles.get(plant && plant.profileId);
    var latest = store.latest(plantId);
    var worst = { level: 'none' };
    var rank = { none: 0, good: 1, warn: 2, bad: 3 };
    (profile.track || []).forEach(function (key) {
      var entry = latest[key];
      if (!entry) return;
      var status = profiles.evaluate(profile, key, entry[key]);
      if (rank[status.level] > rank[worst.level]) worst = status;
    });
    return worst;
  }

  /* --------------------------------------------------------- nursery list */

  function renderList(view) {
    var plants = store.listPlants();

    view.appendChild(h('div', { class: 'page-head' }, [
      h('h1', { text: 'Nursery' }),
      h('p', {
        class: 'hint',
        text: plants.length
          ? plants.length + (plants.length === 1 ? ' plant tracked. ' : ' plants tracked. ') +
            'Status compares each plant’s latest readings against its care profile.'
          : 'No plants yet. Add your first below, then print a QR label for its pot.'
      })
    ]));

    if (plants.length) {
      var body = h('tbody');
      plants.forEach(function (plant) {
        var latest = store.latest(plant.id);
        var profile = profiles.get(plant.profileId);
        var wateredDays = latest.watered ? store.daysSince(latest.watered.at) : null;
        var fedDays = latest.fertilised ? store.daysSince(latest.fertilised.at) : null;
        body.appendChild(h('tr', {}, [
          h('td', {}, [
            h('a', { class: 'plant-row-link', href: '#/p/' + plant.id, text: plant.name }),
            plant.species ? h('div', { class: 'hint', text: plant.species }) : null
          ]),
          h('td', { text: profile.id === 'generic' ? '—' : profile.name }),
          h('td', {}, [
            statusChip(worstStatus(plant.id)) || h('span', { class: 'hint', text: '—' }),
            quarantineStatus(plant) ? document.createTextNode(' ') : null,
            quarantineStatus(plant) ? statusChip({ level: 'bad', label: 'quarantine' }) : null
          ]),
          h('td', { class: 'num', text: latest.ph ? charts.trimNumber(latest.ph.ph, 1) : '—' }),
          h('td', { class: 'num', text: latest.moisture ? charts.trimNumber(latest.moisture.moisture, 0) + '%' : '—' }),
          h('td', { class: 'num', text: wateredDays == null ? '—' : wateredDays + 'd ago' }),
          h('td', { class: 'num', text: fedDays == null ? '—' : fedDays + 'd ago' }),
          h('td', { class: 'num', text: String(store.entriesFor(plant.id).length) })
        ]));
      });

      view.appendChild(h('div', { class: 'card' }, [
        h('div', { class: 'table-wrap' }, [
          h('table', {}, [
            h('thead', {}, [h('tr', {}, [
              h('th', { text: 'Plant' }),
              h('th', { text: 'Profile' }),
              h('th', { text: 'Status' }),
              h('th', { class: 'num', text: 'pH' }),
              h('th', { class: 'num', text: 'Moisture' }),
              h('th', { class: 'num', text: 'Watered' }),
              h('th', { class: 'num', text: 'Fed' }),
              h('th', { class: 'num', text: 'Checks' })
            ])]),
            body
          ])
        ])
      ]));
    }

    var lost = store.listLost();
    if (lost.length) {
      var lostBody = h('div', { class: 'watch-list' });
      lost.forEach(function (plant) {
        lostBody.appendChild(h('p', { class: 'hint' }, [
          h('a', { href: '#/p/' + plant.id, text: plant.name }),
          document.createTextNode(' — lost ' + (plant.lostAt ? charts.formatDateLong(plant.lostAt) : '') +
            (plant.propMethod ? ' · ' + plant.propMethod : ''))
        ]));
      });
      view.appendChild(h('details', { class: 'table-view' }, [
        h('summary', { text: 'Lost plants (' + lost.length + ') — kept for the propagation record' }),
        lostBody
      ]));
    }

    view.appendChild(addPlantForm());
  }

  function profileSelect(selectedId) {
    return h('select', { name: 'profileId' }, profiles.all().map(function (p) {
      return h('option', {
        value: p.id, text: p.name, selected: p.id === selectedId
      });
    }));
  }

  function addPlantForm() {
    var form = h('form', { class: 'card' });
    var name = h('input', { type: 'text', name: 'name', required: true, placeholder: 'Shohin juniper #4' });
    var species = h('input', { type: 'text', name: 'species', placeholder: "Juniperus procumbens 'Nana'" });
    var stage = h('select', { name: 'stage' }, STAGES.map(function (s) { return h('option', { value: s, text: s }); }));
    var profile = profileSelect('generic');
    var source = h('input', { type: 'text', name: 'source', placeholder: 'cutting from bench 2' });
    var startedOn = h('input', { type: 'date', name: 'startedOn', value: store.today() });
    var notes = h('textarea', { name: 'notes', placeholder: 'Rooting medium, position, anything worth remembering.' });

    form.appendChild(h('h2', { text: 'Add a plant' }));
    form.appendChild(h('p', {
      class: 'hint',
      text: 'The care profile decides which factors this plant records and the bands they are judged against.'
    }));
    form.appendChild(h('div', { class: 'field-grid' }, [
      field('Name', name),
      field('Species', species),
      field('Care profile', profile),
      field('Stage', stage),
      field('Source', source),
      field('Started on', startedOn)
    ]));
    form.appendChild(field('Notes', notes));

    var parent = h('select', { name: 'parentId' }, [h('option', { value: '', text: '—' })].concat(
      store.listPlants().map(function (p) { return h('option', { value: p.id, text: p.name }); })
    ));
    var propMethod = h('select', { name: 'propMethod' }, PROP_METHODS.map(function (m) {
      return h('option', { value: m, text: m || '—' });
    }));
    var location = h('input', { type: 'text', name: 'location', placeholder: 'Bench 2, top shelf' });
    var quarantine = h('input', { type: 'checkbox', name: 'quarantine' });

    form.appendChild(h('details', { class: 'table-view' }, [
      h('summary', { text: 'Provenance, location and quarantine' }),
      h('div', { class: 'field-grid' }, [
        field('Location', location),
        field('Parent / mother stock', parent, 'links propagation lineage'),
        field('Propagation method', propMethod),
        h('label', { class: 'checkbox' }, [quarantine,
          document.createTextNode('New stock — quarantine 4 weeks (own shelf, own tools)')])
      ])
    ]));

    form.appendChild(h('div', { class: 'button-row' }, [
      h('button', { type: 'submit', class: 'button button-primary', text: 'Add plant' })
    ]));
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var quarantineUntil = '';
      if (quarantine.checked) {
        var until = new Date(Date.now() + 28 * 86400000);
        quarantineUntil = until.getFullYear() + '-' +
          String(until.getMonth() + 1).padStart(2, '0') + '-' +
          String(until.getDate()).padStart(2, '0');
      }
      var plant = store.addPlant({
        name: name.value, species: species.value, stage: stage.value,
        profileId: profile.value, source: source.value,
        startedOn: startedOn.value, notes: notes.value,
        location: location.value, parentId: parent.value,
        propMethod: propMethod.value, quarantineUntil: quarantineUntil
      });
      global.location.hash = '#/p/' + plant.id;
    });
    return form;
  }

  /* --------------------------------------------------------- plant detail */

  function renderPlant(view, id) {
    var plant = store.getPlant(id);
    if (!plant) {
      view.appendChild(h('div', { class: 'card' }, [
        h('h1', { text: 'Plant not found' }),
        h('p', {
          class: 'hint',
          text: 'No plant with id "' + id + '" exists in this browser. If you scanned a ' +
            'label printed from another device, import that device’s backup first.'
        }),
        h('div', { class: 'button-row' }, [
          h('a', { class: 'button', href: '#/', text: 'Back to nursery' }),
          h('a', { class: 'button', href: '#/backup', text: 'Import a backup' })
        ])
      ]));
      return;
    }

    var profile = profiles.get(plant.profileId);
    var entries = store.entriesFor(id);
    var latest = store.latest(id);

    view.appendChild(h('div', { class: 'page-head' }, [
      h('h1', { text: plant.name }),
      h('p', { class: 'hint' }, [
        plant.species ? h('em', { text: plant.species }) : null,
        document.createTextNode(
          (plant.species ? ' · ' : '') + (plant.stage || '') +
          ' · id ' + plant.id +
          (plant.startedOn ? ' · started ' + plant.startedOn : '')
        )
      ]),
      plant.notes ? h('p', { class: 'hint', text: plant.notes }) : null
    ]));

    view.appendChild(profileCard(plant, profile));
    view.appendChild(specimenCard(plant, profile));
    var monthCard = calendarCard(profile);
    if (monthCard) view.appendChild(monthCard);
    var tasks = plantTasksCard(plant, profile);
    if (tasks) view.appendChild(tasks);
    var forecastCard = plantWeatherCard(plant, profile);
    if (forecastCard) view.appendChild(forecastCard);
    view.appendChild(kpiRow(plant, profile, latest));
    var drip = dripCard(plant, profile);
    if (drip) view.appendChild(drip);
    view.appendChild(logForm(plant, profile));

    /* --- trend charts, one per tracked metric */
    var chartGrid = h('div', { class: 'chart-grid-cards' });
    var tracked = profile.track || ['ph', 'moisture', 'growth'];
    var pairedKeys = {};
    profiles.pairedCharts.forEach(function (pair) {
      pair.keys.forEach(function (key) { pairedKeys[key] = pair; });
    });

    var donePairs = {};
    tracked.forEach(function (key) {
      var pair = pairedKeys[key];
      if (pair) {
        if (donePairs[pair.id]) return;
        donePairs[pair.id] = true;
        chartGrid.appendChild(pairedChartCard(id, profile, pair));
        return;
      }
      chartGrid.appendChild(singleChartCard(id, profile, key));
    });
    view.appendChild(chartGrid);

    /* --- care events */
    var careRows = [
      { name: 'Watering', color: 'var(--series-water)', events: store.eventsFor(id, 'watered') },
      { name: 'Fertiliser', color: 'var(--series-fert)', events: store.eventsFor(id, 'fertilised') }
    ];
    var careHolder = h('div', { class: 'chart-holder' });
    view.appendChild(h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: 'Care events' }),
        h('div', { class: 'legend' }, careRows.map(function (row) {
          return h('span', { class: 'legend-item' }, [
            h('span', { class: 'legend-dot', style: 'background:' + row.color }),
            h('span', { text: row.name })
          ]);
        }))
      ]),
      careHolder
    ]));
    charts.careTimeline(careHolder, { rows: careRows });

    view.appendChild(milestoneCard(id));
    view.appendChild(photoCard(plant));
    if (profile.watch && profile.watch.length) view.appendChild(watchCard(profile));
    view.appendChild(historyCard(id, entries, profile));
    view.appendChild(labelCard(plant));

    view.appendChild(h('div', { class: 'card no-print' }, [
      h('h2', { text: 'Manage plant' }),
      h('p', {
        class: 'hint',
        text: 'A dead or discarded tree should be marked lost, not deleted — the record is what makes ' +
          'propagation success rates and the problem log answerable later.'
      }),
      h('div', { class: 'button-row' }, [
        plant.status !== 'lost' ? h('button', {
          class: 'button', text: 'Mark as lost',
          onclick: function () {
            if (global.confirm('Mark "' + plant.name + '" as lost? Its record and readings are kept; it leaves the active list and the label sheet.')) {
              store.markLost(plant.id);
              global.location.hash = '#/';
            }
          }
        }) : h('button', {
          class: 'button', text: 'Restore to active',
          onclick: function () {
            store.updatePlant(plant.id, { status: 'active', lostAt: '' });
            render();
          }
        }),
        h('button', {
          class: 'button button-danger',
          text: 'Delete this plant and its readings',
          onclick: function () {
            if (global.confirm('Delete "' + plant.name + '" and all of its readings? This cannot be undone.')) {
              photos.removeAllFor(plant.id);
              store.deletePlant(plant.id);
              global.location.hash = '#/';
            }
          }
        })
      ])
    ]));
  }

  function profileCard(plant, profile) {
    var select = profileSelect(plant.profileId);
    return h('div', { class: 'card no-print' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: profile.name }),
        profile.scientific ? h('span', { class: 'hint', text: profile.scientific }) : null
      ]),
      profile.summary ? h('p', { class: 'profile-summary', text: profile.summary }) : null,
      profile.winterFloor
        ? h('p', { class: 'floor-note', text: 'Winter floor ' + profile.winterFloor.tempF + ' °F — ' + profile.winterFloor.note })
        : null,
      profile.source ? h('p', { class: 'hint', text: 'Targets from: ' + profile.source }) : null,
      h('div', { class: 'field-grid' }, [
        field('Care profile', select, 'Changing this changes which factors are recorded and the bands they are judged against.')
      ]),
      h('div', { class: 'button-row' }, [
        h('button', {
          class: 'button', text: 'Apply profile',
          onclick: function () {
            store.updatePlant(plant.id, { profileId: select.value });
            render();
          }
        })
      ])
    ]);
  }

  function kpiRow(plant, profile, latest) {
    var row = h('div', { class: 'kpi-row' });
    (profile.track || []).forEach(function (key) {
      var metric = METRICS[key];
      var entry = latest[key];
      if (!metric || !entry) return;
      var value = entry[key];
      var sub = charts.formatDate(entry.at);
      if (key === 'light') sub += lightDerivation(profile, value);
      row.appendChild(statTile(
        metric.label,
        charts.trimNumber(value, metric.decimals),
        metric.unit,
        sub,
        metric.color,
        profiles.evaluate(profile, key, value)
      ));
    });

    var wateredDays = latest.watered ? store.daysSince(latest.watered.at) : null;
    var fedDays = latest.fertilised ? store.daysSince(latest.fertilised.at) : null;
    row.appendChild(statTile('Watered', wateredDays == null ? '—' : String(wateredDays),
      wateredDays == null ? '' : 'd ago',
      latest.watered ? charts.formatDate(latest.watered.at) : 'never logged', 'var(--series-water)'));
    row.appendChild(statTile('Fed', fedDays == null ? '—' : String(fedDays),
      fedDays == null ? '' : 'd ago',
      latest.fertilised ? charts.formatDate(latest.fertilised.at) : 'never logged', 'var(--series-fert)'));

    if (!row.childNodes.length) {
      return h('div', { class: 'card' }, [h('p', { class: 'hint', text: 'No readings yet — log the first check below.' })]);
    }
    return row;
  }

  function singleChartCard(plantId, profile, key) {
    var metric = METRICS[key];
    if (!metric) return h('div');
    var points = store.seriesFor(plantId, key);
    var band = profiles.bandFor(profile, key);
    var holder = h('div', { class: 'chart-holder' });
    var card = h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: metric.label + (metric.unit ? ' (' + metric.unit + ')' : '') }),
        h('span', { class: 'hint', text: points.length + (points.length === 1 ? ' reading' : ' readings') })
      ]),
      band && band.note ? h('p', { class: 'band-note', text: band.note }) : null,
      holder
    ]);
    if (points.length) card.appendChild(valueTableView(metric, points));
    charts.trend(holder, {
      series: [{ name: metric.label, color: metric.color, points: points }],
      bands: band ? [{ good: band.good, label: 'target' }] : [],
      name: metric.label, unit: metric.unit, decimals: metric.decimals
    });
    return card;
  }

  // Low and high temperature on one chart: a range, not two independent series.
  function pairedChartCard(plantId, profile, pair) {
    var holder = h('div', { class: 'chart-holder' });
    var series = pair.keys.map(function (key) {
      return {
        key: key,
        name: METRICS[key].label,
        color: METRICS[key].color,
        points: store.seriesFor(plantId, key)
      };
    });
    // One band per series, each named — a single shaded zone under two lines
    // would not say which line it belongs to.
    var bands = [];
    pair.keys.forEach(function (key) {
      var b = profiles.bandFor(profile, key);
      if (b && b.good) bands.push({ good: b.good, label: METRICS[key].label.toLowerCase() });
    });
    var band = profiles.bandFor(profile, pair.keys[0]);
    var total = series.reduce(function (sum, s) { return sum + s.points.length; }, 0);

    var card = h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: pair.title + ' (' + pair.unit + ')' }),
        h('div', { class: 'legend' }, series.map(function (s) {
          return h('span', { class: 'legend-item' }, [
            h('span', { class: 'legend-dot', style: 'background:' + s.color }),
            h('span', { text: s.name })
          ]);
        }))
      ]),
      band && band.note ? h('p', { class: 'band-note', text: band.note }) : null,
      holder
    ]);

    if (total) {
      var body = h('tbody');
      var byDate = {};
      series.forEach(function (s) {
        s.points.forEach(function (p) {
          byDate[p.at] = byDate[p.at] || {};
          byDate[p.at][s.key] = p.value;
        });
      });
      Object.keys(byDate).sort().reverse().forEach(function (at) {
        body.appendChild(h('tr', {}, [
          h('td', { text: charts.formatDateLong(at) }),
          h('td', { class: 'num', text: byDate[at].tempLow == null ? '—' : charts.trimNumber(byDate[at].tempLow, 0) }),
          h('td', { class: 'num', text: byDate[at].tempHigh == null ? '—' : charts.trimNumber(byDate[at].tempHigh, 0) })
        ]));
      });
      card.appendChild(h('details', { class: 'table-view' }, [
        h('summary', { text: 'Table view' }),
        h('div', { class: 'table-wrap' }, [
          h('table', {}, [
            h('thead', {}, [h('tr', {}, [
              h('th', { text: 'Date' }),
              h('th', { class: 'num', text: 'Low' }),
              h('th', { class: 'num', text: 'High' })
            ])]),
            body
          ])
        ])
      ]));
    }

    charts.trend(holder, {
      series: series, bands: bands, name: pair.title,
      unit: pair.unit, decimals: pair.decimals
    });
    return card;
  }

  // The handbooks all lead with a month-by-month table, and "what am I meant
  // to be doing right now" is the most actionable thing on the page — so this
  // sits directly under the profile, with today's row called out.
  function calendarCard(profile) {
    if (!profile.calendar || !profile.calendar.length) return null;
    var now = new Date();
    var row = profiles.currentMonth(profile, now);
    var resting = profiles.isRestMonth(profile, now);
    if (!row) return null;

    var body = h('tbody');
    profile.calendar.forEach(function (item, index) {
      body.appendChild(h('tr', { class: index === now.getMonth() ? 'row-now' : '' }, [
        h('td', { text: item.month }),
        h('td', { text: item.where }),
        h('td', { text: item.water }),
        h('td', { text: item.feed }),
        h('td', { text: item.action })
      ]));
    });

    function fact(key, value) {
      return h('div', { class: 'month-fact' }, [
        h('span', { class: 'k', text: key }),
        h('span', { class: 'v', text: value })
      ]);
    }

    return h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: 'This month — ' + row.month }),
        resting ? statusChip({ level: 'warn', label: 'winter rest — rest-season targets in force' }) : null
      ]),
      h('p', { class: 'profile-summary', text: row.action }),
      h('div', { class: 'month-facts' }, [
        fact('Where', row.where),
        fact('Water', row.water),
        fact('Feed', row.feed)
      ]),
      h('details', { class: 'table-view' }, [
        h('summary', { text: 'The year on one page' }),
        h('div', { class: 'table-wrap' }, [
          h('table', {}, [
            h('thead', {}, [h('tr', {}, [
              h('th', { text: 'Month' }),
              h('th', { text: 'Where' }),
              h('th', { text: 'Water' }),
              h('th', { text: 'Feed' }),
              h('th', { text: 'Key action' })
            ])]),
            body
          ])
        ])
      ])
    ]);
  }

  function logForm(plant, profile) {
    var form = h('form', { class: 'card no-print' });
    var at = h('input', { type: 'date', name: 'at', value: store.today() });
    var inputs = {};
    var tracked = profile.track || ['ph', 'moisture', 'growth'];

    form.appendChild(h('h2', { text: 'Log a check' }));
    form.appendChild(h('p', {
      class: 'hint',
      text: 'Leave anything you did not measure blank — a blank field records nothing rather than a zero.'
    }));
    form.appendChild(h('div', { class: 'field-grid' }, [field('Date', at)]));

    FORM_GROUPS.forEach(function (group) {
      var keys = group.keys.filter(function (key) { return tracked.indexOf(key) >= 0; });
      if (!keys.length) return;
      form.appendChild(h('h3', { text: group.title }));
      form.appendChild(h('div', { class: 'field-grid' }, keys.map(function (key) {
        var metric = METRICS[key];
        var band = profiles.bandFor(profile, key);
        var input = h('input', { type: 'number', name: key, step: metric.step, placeholder: '' });
        inputs[key] = input;
        var hint = metric.hint;
        if (band && band.good) {
          hint = 'target ' + charts.trimNumber(band.good[0], metric.decimals) + '–' +
            charts.trimNumber(band.good[1], metric.decimals) + (metric.unit ? ' ' + metric.unit : '') +
            ' · ' + metric.hint;
        }
        return field(metric.label + (metric.unit ? ' (' + metric.unit + ')' : ''), input, hint);
      })));
    });

    var watered = h('input', { type: 'checkbox', name: 'watered' });
    var waterMl = h('input', { type: 'number', name: 'waterMl', step: '10', min: '0', placeholder: '250' });
    var fertilised = h('input', { type: 'checkbox', name: 'fertilised' });
    var fertiliser = h('input', { type: 'text', name: 'fertiliser', placeholder: 'Biogold' });
    var fertAmount = h('input', { type: 'text', name: 'fertAmount', placeholder: '2 pellets' });

    form.appendChild(h('h3', { text: 'Care' }));
    form.appendChild(h('div', { class: 'field-grid' }, [
      h('label', { class: 'checkbox' }, [watered, document.createTextNode('Watered')]),
      field('Water amount', waterMl, 'ml, optional'),
      h('label', { class: 'checkbox' }, [fertilised, document.createTextNode('Fertilised')]),
      field('Fertiliser', fertiliser),
      field('Amount', fertAmount)
    ]));

    var repotted = h('input', { type: 'checkbox', name: 'repotted' });
    var pruned = h('input', { type: 'checkbox', name: 'pruned' });
    var pestSeen = h('input', { type: 'checkbox', name: 'pestSeen' });
    var pestType = h('select', { name: 'pestType' }, [h('option', { value: '', text: '—' })].concat(
      PESTS.map(function (p) { return h('option', { value: p, text: p }); })
    ));
    var graftChecked = h('input', { type: 'checkbox', name: 'graftChecked' });
    var suckersRemoved = h('input', { type: 'checkbox', name: 'suckersRemoved' });
    var moved = h('select', { name: 'moved' }, [
      h('option', { value: '', text: '—' }),
      h('option', { value: 'outdoors', text: 'moved outdoors' }),
      h('option', { value: 'indoors', text: 'moved indoors' })
    ]);

    form.appendChild(h('h3', { text: 'Work and health' }));
    var milestoneFields = [
      h('label', { class: 'checkbox' }, [repotted, document.createTextNode('Repotted')]),
      h('label', { class: 'checkbox' }, [pruned, document.createTextNode('Pruned / wired')]),
      h('label', { class: 'checkbox' }, [pestSeen, document.createTextNode('Pest seen')]),
      field('Which pest', pestType),
      h('label', { class: 'checkbox' }, [graftChecked, document.createTextNode('Graft line checked')]),
      h('label', { class: 'checkbox' }, [suckersRemoved, document.createTextNode('Suckers removed')])
    ];
    if (profile.setting === 'seasonal') milestoneFields.push(field('Moved', moved));
    form.appendChild(h('div', { class: 'field-grid' }, milestoneFields));

    var wired = h('input', { type: 'checkbox', name: 'wired' });
    var wireGauge = h('input', { type: 'text', name: 'wireGauge', placeholder: '2 mm aluminium' });
    var wireRemoved = h('input', { type: 'checkbox', name: 'wireRemoved' });
    var rootPrunePct = h('input', { type: 'number', name: 'rootPrunePct', step: '5', min: '0', max: '80', placeholder: '25' });
    var repotMix = h('input', { type: 'text', name: 'repotMix', placeholder: '1:1:1 akadama–pumice–lava' });
    var potDesc = h('input', { type: 'text', name: 'potDesc', placeholder: 'unglazed oval, 8 in' });
    var pestSeverity = h('select', { name: 'pestSeverity' }, ['', 'light', 'moderate', 'severe'].map(function (v) {
      return h('option', { value: v, text: v || '—' });
    }));
    var treated = h('input', { type: 'checkbox', name: 'treated' });
    var treatmentAgent = h('input', { type: 'text', name: 'treatmentAgent', placeholder: 'insecticidal soap · horticultural oil' });
    var reiHours = h('input', { type: 'number', name: 'reiHours', step: '1', min: '0', placeholder: '12' });
    var fertMethod = h('select', { name: 'fertMethod' }, FERT_METHODS.map(function (v) {
      return h('option', { value: v, text: v || '—' });
    }));
    var npk = h('input', { type: 'text', name: 'npk', placeholder: '10-10-10' });
    var movedTo = h('input', { type: 'text', name: 'movedTo', placeholder: 'Bench 2 · south wall · winter room' });
    var minutes = h('input', { type: 'number', name: 'minutes', step: '5', min: '0', placeholder: '20' });

    form.appendChild(h('details', { class: 'table-view' }, [
      h('summary', { text: 'Detail — styling, repot, treatment, location, time' }),
      h('div', { class: 'field-grid' }, [
        h('label', { class: 'checkbox' }, [wired, document.createTextNode('Wired')]),
        field('Wire gauge', wireGauge),
        h('label', { class: 'checkbox' }, [wireRemoved, document.createTextNode('Wire removed')]),
        field('Root pruned (%)', rootPrunePct, 'with a repot'),
        field('Repot mix', repotMix),
        field('Pot', potDesc),
        field('Pest severity', pestSeverity),
        h('label', { class: 'checkbox' }, [treated, document.createTextNode('Treated')]),
        field('Agent / product', treatmentAgent, 'goes to the compliance CSV'),
        field('REI (hours)', reiHours, 're-entry interval from the label'),
        field('Feed method', fertMethod),
        field('N-P-K', npk),
        field('Moved to', movedTo, 'updates the plant’s location'),
        field('Time spent (min)', minutes, 'builds the labor total')
      ])
    ]));

    var note = h('input', { type: 'text', name: 'note', placeholder: 'Back buds opening on the lower trunk.' });
    form.appendChild(field('Note', note));
    form.appendChild(h('div', { class: 'button-row' }, [
      h('button', { type: 'submit', class: 'button button-primary', text: 'Save check' })
    ]));

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var fields = {
        at: at.value,
        watered: watered.checked, waterMl: waterMl.value,
        fertilised: fertilised.checked, fertiliser: fertiliser.value, fertAmount: fertAmount.value,
        repotted: repotted.checked, pruned: pruned.checked,
        pestSeen: pestSeen.checked, pestType: pestType.value,
        graftChecked: graftChecked.checked, suckersRemoved: suckersRemoved.checked,
        moved: moved.value, note: note.value,
        wired: wired.checked, wireGauge: wireGauge.value, wireRemoved: wireRemoved.checked,
        rootPrunePct: rootPrunePct.value, repotMix: repotMix.value, potDesc: potDesc.value,
        pestSeverity: pestSeverity.value, treated: treated.checked,
        treatmentAgent: treatmentAgent.value, reiHours: reiHours.value,
        fertMethod: fertMethod.value, npk: npk.value,
        movedTo: movedTo.value, minutes: minutes.value
      };
      var measured = false;
      Object.keys(inputs).forEach(function (key) {
        fields[key] = inputs[key].value;
        if (inputs[key].value !== '') measured = true;
      });

      var acted = watered.checked || fertilised.checked || repotted.checked || pruned.checked ||
        pestSeen.checked || graftChecked.checked || suckersRemoved.checked || moved.value || note.value ||
        wired.checked || wireRemoved.checked || treated.checked || movedTo.value || minutes.value;
      if (!measured && !acted) {
        global.alert('Nothing to save — record at least one measurement, a care action, or a note.');
        return;
      }
      store.addEntry(plant.id, fields);
      render();
    });
    return form;
  }

  // A table twin for each chart, so no value is reachable only by hovering.
  function valueTableView(metric, points) {
    var body = h('tbody');
    points.slice().reverse().forEach(function (point) {
      body.appendChild(h('tr', {}, [
        h('td', { text: charts.formatDateLong(point.at) }),
        h('td', { class: 'num', text: charts.trimNumber(point.value, metric.decimals) })
      ]));
    });
    return h('details', { class: 'table-view' }, [
      h('summary', { text: 'Table view' }),
      h('div', { class: 'table-wrap' }, [
        h('table', {}, [
          h('thead', {}, [h('tr', {}, [
            h('th', { text: 'Date' }),
            h('th', { class: 'num', text: metric.label + (metric.unit ? ' (' + metric.unit + ')' : '') })
          ])]),
          body
        ])
      ])
    ]);
  }

  // Repots, prunes, pest sightings and graft checks happen a few times a year,
  // so they read better as a labelled list than as more chart lanes.
  function milestoneCard(plantId) {
    var milestones = store.milestonesFor(plantId);
    if (!milestones.length) {
      return h('div', { class: 'card' }, [
        h('h2', { text: 'Work and health log' }),
        h('p', { class: 'hint', text: 'No repots, pruning, pest sightings or graft checks logged yet.' })
      ]);
    }
    var body = h('tbody');
    milestones.forEach(function (item) {
      body.appendChild(h('tr', {}, [
        h('td', { text: charts.formatDateLong(item.at) }),
        h('td', {}, [
          h('span', { class: 'milestone-type', text: item.label }),
          item.alert ? document.createTextNode(' ') : null,
          item.alert ? statusChip({ level: 'bad', label: 'treat' }) : null
        ]),
        h('td', { text: item.detail || '' })
      ]));
    });
    return h('div', { class: 'card' }, [
      h('h2', { text: 'Work and health log' }),
      h('div', { class: 'table-wrap' }, [
        h('table', {}, [
          h('thead', {}, [h('tr', {}, [
            h('th', { text: 'Date' }),
            h('th', { text: 'Event' }),
            h('th', { text: 'Detail' })
          ])]),
          body
        ])
      ])
    ]);
  }

  function watchCard(profile) {
    return h('div', { class: 'card' }, [
      h('h2', { text: 'What to watch' }),
      h('div', { class: 'watch-list' }, profile.watch.map(function (item) {
        return h('div', { class: 'watch-item', 'data-severity': item.severity || 'normal' }, [
          h('div', { class: 'watch-title', text: item.title }),
          h('div', { class: 'watch-body', text: item.body })
        ]);
      }))
    ]);
  }

  function historyCard(plantId, entries, profile) {
    if (!entries.length) {
      return h('div', { class: 'card' }, [
        h('h2', { text: 'History' }),
        h('p', { class: 'hint', text: 'No checks logged yet.' })
      ]);
    }
    var tracked = (profile.track || ['ph', 'moisture', 'growth']).filter(function (key) { return METRICS[key]; });

    var body = h('tbody');
    entries.slice().reverse().forEach(function (entry) {
      var care = [];
      if (entry.watered) care.push('water' + (entry.waterMl != null ? ' ' + entry.waterMl + 'ml' : ''));
      if (entry.fertilised) care.push([entry.fertiliser, entry.fertAmount].filter(Boolean).join(' ') || 'fertiliser');
      if (entry.repotted) care.push('repot');
      if (entry.pruned) care.push('prune');
      if (entry.suckersRemoved) care.push('suckers off');
      if (entry.pestSeen) care.push('pest: ' + (entry.pestType || 'seen'));
      if (entry.moved) care.push('moved ' + entry.moved);

      var cells = [h('td', { text: charts.formatDateLong(entry.at) })];
      tracked.forEach(function (key) {
        cells.push(h('td', {
          class: 'num',
          text: entry[key] == null ? '—' : charts.trimNumber(entry[key], METRICS[key].decimals)
        }));
      });
      cells.push(h('td', { text: care.join(', ') || '—' }));
      cells.push(h('td', { text: entry.note || '' }));
      cells.push(h('td', { class: 'no-print' }, [
        h('button', {
          class: 'button button-quiet button-danger', text: 'Delete',
          onclick: function () {
            if (global.confirm('Delete this check?')) { store.deleteEntry(entry.id); render(); }
          }
        })
      ]));
      body.appendChild(h('tr', {}, cells));
    });

    var head = [h('th', { text: 'Date' })];
    tracked.forEach(function (key) {
      head.push(h('th', { class: 'num', text: METRICS[key].label + (METRICS[key].unit ? ' (' + METRICS[key].unit + ')' : '') }));
    });
    head.push(h('th', { text: 'Care' }));
    head.push(h('th', { text: 'Note' }));
    head.push(h('th', { class: 'no-print', text: '' }));

    return h('div', { class: 'card' }, [
      h('h2', { text: 'History' }),
      h('div', { class: 'table-wrap' }, [
        h('table', {}, [h('thead', {}, [h('tr', {}, head)]), body])
      ])
    ]);
  }

  function labelCard(plant) {
    var url = plantUrl(plant.id);
    var holder = h('div', { class: 'qr-large' });
    try {
      holder.innerHTML = QR.toSvg(url, { ecc: 'M' });
    } catch (error) {
      holder.appendChild(h('p', { class: 'hint', text: 'Could not build a QR code: ' + error.message }));
    }
    return h('div', { class: 'card' }, [
      h('h2', { text: 'Label' }),
      holder,
      h('p', { class: 'hint', text: url }),
      h('div', { class: 'button-row no-print' }, [
        h('a', { class: 'button', href: '#/labels', text: 'Print label sheet' })
      ])
    ]);
  }

  /* ---------------------------------------------------------- label sheet */

  function renderLabels(view) {
    var plants = store.listPlants();

    view.appendChild(h('div', { class: 'page-head no-print' }, [
      h('h1', { text: 'Label sheet' }),
      h('p', {
        class: 'hint',
        text: 'Each label carries a QR code pointing at that plant’s page. Print onto ' +
          'weatherproof or laminated stock, then scan with any phone camera — no app needed.'
      })
    ]));

    var base = h('input', { type: 'url', value: labelBase(), placeholder: 'https://user.github.io/repo/' });
    var warning = global.location.protocol === 'file:'
      ? 'This page is open from a file:// path, so labels would only work on this ' +
        'computer. Publish the folder (GitHub Pages works) and put that address here first.'
      : 'Labels encode this address. Change it if you print from one device but scan against another.';

    view.appendChild(h('div', { class: 'card no-print' }, [
      h('h2', { text: 'Label address' }),
      field('Base URL', base, warning),
      h('div', { class: 'button-row' }, [
        h('button', { class: 'button', text: 'Apply', onclick: function () { setLabelBase(base.value); render(); } }),
        h('button', { class: 'button button-primary', text: 'Print', onclick: function () { global.print(); } })
      ])
    ]));

    if (!plants.length) {
      view.appendChild(h('div', { class: 'card' }, [
        h('p', { class: 'hint', text: 'Add a plant first and its label will appear here.' })
      ]));
      return;
    }

    var sheet = h('div', { class: 'label-sheet' });
    plants.forEach(function (plant) {
      var cell = h('div', { class: 'label-cell' });
      var qr = h('div');
      try {
        qr.innerHTML = QR.toSvg(plantUrl(plant.id), { ecc: 'M' });
      } catch (error) {
        qr.textContent = 'QR failed';
      }
      cell.appendChild(qr);
      cell.appendChild(h('div', { class: 'label-name', text: plant.name }));
      if (plant.species) cell.appendChild(h('div', { class: 'label-species', text: plant.species }));
      cell.appendChild(h('div', { class: 'label-id', text: plant.id }));
      sheet.appendChild(cell);
    });
    view.appendChild(sheet);
  }

  /* --------------------------------------------------------------- backup */

  function renderBackup(view) {
    var plants = store.listPlants();
    var entryCount = plants.reduce(function (sum, p) { return sum + store.entriesFor(p.id).length; }, 0);

    view.appendChild(h('div', { class: 'page-head' }, [
      h('h1', { text: 'Backup and export' }),
      h('p', {
        class: 'hint',
        text: 'Readings live in this browser’s storage on this device. They are not ' +
          'synced anywhere, and clearing site data erases them. Export regularly, and ' +
          'import on a second device to combine two sets of readings.'
      })
    ]));

    view.appendChild(h('div', { class: 'card' }, [
      h('h2', { text: 'Export' }),
      h('p', { class: 'hint', text: plants.length + ' plants, ' + entryCount + ' checks.' }),
      h('div', { class: 'button-row' }, [
        h('button', {
          class: 'button button-primary', text: 'Download JSON backup',
          onclick: function () {
            download('bonsai-nursery-' + store.today() + '.json', store.exportJson(), 'application/json');
          }
        }),
        h('button', {
          class: 'button', text: 'Download CSV for Excel',
          onclick: function () {
            download('bonsai-readings-' + store.today() + '.csv', store.exportCsv(), 'text/csv');
          }
        })
      ]),
      h('p', {
        class: 'hint',
        text: 'The JSON file is the complete nursery and is what you import below. ' +
          'The CSV is one row per check with every factor as a column — including treatments, ' +
          'agents and re-entry intervals, so it doubles as the chemical application report. ' +
          'Photos are not included in either: they stay on the device that took them.'
      })
    ]));

    var picker = h('input', { type: 'file', accept: '.json,application/json' });
    var status = h('p', { class: 'hint' });
    picker.addEventListener('change', function () {
      var file = picker.files && picker.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var added = store.importJson(String(reader.result));
          status.textContent = 'Imported ' + added.plants + ' new plants and ' +
            added.entries + ' new checks. Anything already here was left alone.';
          render();
        } catch (error) {
          status.textContent = 'Import failed: ' + error.message;
        }
      };
      reader.readAsText(file);
    });

    view.appendChild(h('div', { class: 'card' }, [
      h('h2', { text: 'Import' }),
      field('Backup file', picker, 'Merges by id, so importing the same file twice is safe.'),
      status
    ]));

    view.appendChild(h('div', { class: 'card' }, [
      h('h2', { text: 'Danger zone' }),
      h('div', { class: 'button-row' }, [
        h('button', {
          class: 'button button-danger', text: 'Erase everything in this browser',
          onclick: function () {
            if (global.confirm('Erase all plants and readings stored in this browser?\n\nExport a backup first if you might want them back.')) {
              store.replaceAll({ version: 1, plants: [], entries: [] });
              global.location.hash = '#/';
            }
          }
        })
      ])
    ]));
  }


  /* ----------------------------------------------------------------- sync */

  function renderSync(view) {
    var cfg = sync.config();

    view.appendChild(h('div', { class: 'page-head' }, [
      h('h1', { text: 'Sync across devices' }),
      h('p', {
        class: 'hint',
        text: 'Optional. With this on, the greenhouse phone and the office laptop keep ' +
          'the same nursery automatically — no exporting a file each time. It is free, ' +
          'and it still works offline: readings are saved on the device and go up when ' +
          'you reconnect.'
      })
    ]));

    var badge = h('p', { class: 'hint', text: sync.status().message });
    sync.onStatus(function (state) { badge.textContent = state.message; });

    var enabled = h('input', { type: 'checkbox', name: 'syncEnabled', checked: cfg.enabled });
    var projectId = h('input', { type: 'text', name: 'projectId', value: cfg.projectId, placeholder: 'bonsai-nursery-1a2b3' });
    var apiKey = h('input', { type: 'text', name: 'apiKey', value: cfg.apiKey, placeholder: 'AIza…' });
    var code = h('input', { type: 'text', name: 'code', value: cfg.code, placeholder: 'paste the code from your other device' });

    var saved = h('p', { class: 'hint' });

    view.appendChild(h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [h('h2', { text: 'Connection' }), badge]),
      h('div', { class: 'field-grid' }, [
        field('Project ID', projectId, 'from the Firebase console'),
        field('Web API key', apiKey, 'Project settings → General → Web API Key')
      ]),
      field('Nursery code', code,
        'The same code on every device that should share this nursery. Treat it like a password — anyone who has it can read and write your readings.'),
      h('div', { class: 'button-row' }, [
        h('button', {
          class: 'button', text: 'Generate a new code',
          onclick: function () { code.value = sync.newCode(); }
        }),
        h('button', {
          class: 'button', text: 'Copy code',
          onclick: function () {
            code.select();
            try { document.execCommand('copy'); saved.textContent = 'Code copied.'; }
            catch (error) { saved.textContent = 'Select the code and copy it manually.'; }
          }
        })
      ]),
      h('label', { class: 'checkbox' }, [enabled, document.createTextNode('Keep this device in sync')]),
      h('div', { class: 'button-row' }, [
        h('button', {
          class: 'button button-primary', text: 'Save and sync now',
          onclick: function () {
            if (enabled.checked && !(projectId.value && apiKey.value && code.value)) {
              saved.textContent = 'Fill in the project ID, API key and nursery code first.';
              return;
            }
            sync.setConfig({
              enabled: enabled.checked,
              projectId: projectId.value.trim(),
              apiKey: apiKey.value.trim(),
              code: code.value.trim()
            });
            saved.textContent = 'Saved.';
            sync.start();
          }
        }),
        h('button', { class: 'button', text: 'Sync now', onclick: function () { sync.syncNow(); } })
      ]),
      saved
    ]));

    view.appendChild(h('div', { class: 'card' }, [
      h('h2', { text: 'One-time setup (about ten minutes)' }),
      h('ol', { class: 'steps' }, [
        h('li', {}, [document.createTextNode('At '), h('strong', { text: 'console.firebase.google.com' }),
          document.createTextNode(', create a project. No card is needed — the free Spark plan covers a nursery easily.')]),
        h('li', {}, [h('strong', { text: 'Build → Firestore Database → Create database' }),
          document.createTextNode('. Pick a region near you and start in production mode.')]),
        h('li', {}, [h('strong', { text: 'Build → Authentication → Get started → Anonymous' }),
          document.createTextNode(' and enable it. This does not create accounts; it just lets the rules below require a signed-in caller.')]),
        h('li', {}, [document.createTextNode('In '), h('strong', { text: 'Firestore → Rules' }),
          document.createTextNode(', paste the rules below and publish.')]),
        h('li', {}, [h('strong', { text: 'Project settings → General' }),
          document.createTextNode(', add a Web app if there is none, then copy the Project ID and Web API Key into the fields above.')]),
        h('li', {}, [document.createTextNode('Press '), h('strong', { text: 'Generate a new code' }),
          document.createTextNode(', save, then enter that same code on your other device.')])
      ]),
      h('pre', { class: 'code', text: "rules_version = '2';\nservice cloud.firestore {\n  match /databases/{database}/documents {\n    match /nurseries/{code} {\n      allow read, write: if request.auth != null;\n    }\n  }\n}" })
    ]));

    view.appendChild(h('div', { class: 'card' }, [
      h('h2', { text: 'What to expect' }),
      h('div', { class: 'watch-list' }, [
        h('div', { class: 'watch-item' }, [
          h('div', { class: 'watch-title', text: 'Edits merge, they do not overwrite' }),
          h('div', { class: 'watch-body', text: 'Each plant and each check syncs on its own, newest edit winning. Two devices adding different readings offline both keep theirs. Deletions carry across properly rather than reappearing from the other device.' })
        ]),
        h('div', { class: 'watch-item' }, [
          h('div', { class: 'watch-title', text: 'The code is the key' }),
          h('div', { class: 'watch-body', text: 'There are no usernames. Anyone holding the nursery code can read and write the nursery, exactly like an unguessable share link. A generated code is about 120 bits, so it will not be guessed — but do not post it anywhere public.' })
        ]),
        h('div', { class: 'watch-item' }, [
          h('div', { class: 'watch-title', text: 'Photos stay on the device' }),
          h('div', { class: 'watch-body', text: 'Sync ships the whole nursery as one document with a 1 MB ceiling, and photos would blow through it. So the readings, logs and completions sync; the pixels do not. Take reference photos on the device you review them on.' })
        ]),
        h('div', { class: 'watch-item' }, [
          h('div', { class: 'watch-title', text: 'Keep exporting occasionally' }),
          h('div', { class: 'watch-body', text: 'Sync copies your data; it does not version it. A JSON backup now and then is still the thing that saves you from a mistaken bulk delete.' })
        ])
      ])
    ]));
  }

  /* ------------------------------------------------------------- calendar */

  function taskRow(item, onChange) {
    var button = h('button', {
      class: 'button button-quiet',
      text: item.state === 'done' ? 'Undo' : 'Mark done',
      onclick: function () {
        store.setTaskDone(item.plantId, item.task.id, item.year, item.state !== 'done');
        onChange();
      }
    });
    return h('div', { class: 'task-row', 'data-state': item.state }, [
      h('div', { class: 'task-head' }, [
        h('span', { class: 'task-title', text: item.task.title }),
        h('span', { class: 'cat-chip', text: item.categoryLabel })
      ]),
      h('div', { class: 'task-meta' }, [
        h('a', { href: '#/p/' + item.plantId, text: item.plantName }),
        document.createTextNode(' · ' + item.when +
          (item.state === 'upcoming' && item.daysAway > 0 ? ' · in ' + item.daysAway + ' days' : '') +
          (item.state === 'overdue' ? ' · window has passed' : ''))
      ]),
      h('div', { class: 'task-body', text: item.task.body }),
      h('div', { class: 'button-row no-print' }, [button])
    ]);
  }

  function allTasks() {
    var today = new Date();
    var out = [];
    store.listPlants().forEach(function (plant) {
      var profile = profiles.get(plant.profileId);
      out = out.concat(calendar.tasksForPlant(plant, profile, today, store.isTaskDone));
    });
    return calendar.sortTasks(out);
  }

  function renderCalendar(view) {
    var items = allTasks();

    view.appendChild(h('div', { class: 'page-head' }, [
      h('h1', { text: 'Master calendar' }),
      h('p', {
        class: 'hint',
        text: 'Every dated window across the whole nursery, taken from each tree’s handbook — ' +
          'pruning, repotting, feeding cutoffs, indoor and outdoor moves, scouting and system ' +
          'changeovers. Marking one done is remembered for that year only, so it comes back next season.'
      })
    ]));

    view.appendChild(weatherCard());

    view.appendChild(h('div', { class: 'card no-print' }, [
      h('h2', { text: 'Reminders on your phone' }),
      h('p', {
        class: 'hint',
        text: 'Download every dated window as a calendar file and import or subscribe to it. Each becomes ' +
          'a yearly repeating all-day event with an alarm the day before — which is the only way this app ' +
          'can reach you while your phone is asleep, since there is no server anywhere in it.'
      }),
      h('div', { class: 'button-row' }, [
        h('button', {
          class: 'button button-primary', text: 'Download calendar (.ics)',
          onclick: function () {
            var pairs = store.listPlants().map(function (plant) {
              return { plant: plant, profile: profiles.get(plant.profileId) };
            }).filter(function (pair) { return (pair.profile.tasks || []).length; });
            if (!pairs.length) {
              global.alert('No plants with a care profile yet — nothing to export.');
              return;
            }
            download('koch-tree-nursery.ics', calendar.toIcs(pairs, new Date()), 'text/calendar');
          }
        })
      ])
    ]));

    if (!items.length) {
      view.appendChild(h('div', { class: 'card' }, [
        h('p', { class: 'hint', text: 'Nothing scheduled — add a plant and give it a care profile.' })
      ]));
      view.appendChild(weatherSettingsCard());
      return;
    }

    var groups = [
      { key: 'overdue', title: 'Missed', note: 'The window has passed. Handbook windows exist for a reason — if you skipped one deliberately, mark it done to clear it.' },
      { key: 'due', title: 'Due now', note: 'You are inside the window for these.' },
      { key: 'upcoming', title: 'Coming up', note: 'Next windows, soonest first.' },
      { key: 'done', title: 'Done this year', note: '' }
    ];

    groups.forEach(function (group) {
      var rows = items.filter(function (item) { return item.state === group.key; });
      if (!rows.length) return;
      var card = h('div', { class: 'card' }, [
        h('div', { class: 'card-head' }, [
          h('h2', { text: group.title }),
          h('span', { class: 'hint', text: rows.length + (rows.length === 1 ? ' item' : ' items') })
        ]),
        group.note ? h('p', { class: 'hint', text: group.note }) : null
      ]);
      var list = h('div', { class: 'task-list' });
      rows.forEach(function (item) { list.appendChild(taskRow(item, render)); });
      card.appendChild(list);
      view.appendChild(card);
    });

    view.appendChild(weatherSettingsCard());
  }

  // Only what needs attention, on the plant's own page.
  function plantTasksCard(plant, profile) {
    var items = calendar.tasksForPlant(plant, profile, new Date(), store.isTaskDone);
    var active = calendar.sortTasks(items).filter(function (item) {
      return item.state === 'overdue' || item.state === 'due' ||
        (item.state === 'upcoming' && item.daysAway <= 30);
    });
    if (!active.length) return null;
    var list = h('div', { class: 'task-list' });
    active.forEach(function (item) { list.appendChild(taskRow(item, render)); });
    return h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: 'Due now and next 30 days' }),
        h('a', { class: 'hint', href: '#/calendar', text: 'whole calendar' })
      ]),
      list
    ]);
  }

  /* ------------------------------------------------------------------ drip */

  function dripCard(plant, profile) {
    var summary = calendar.dripSummary(profile, plant, new Date());
    if (!summary) return null;

    var flow = h('input', {
      type: 'number', name: 'mlPerMin', step: '0.1', min: '0',
      value: plant.mlPerMin == null ? '' : plant.mlPerMin,
      placeholder: String(summary.mlPerMin)
    });

    function fact(key, value) {
      return h('div', { class: 'month-fact' }, [
        h('span', { class: 'k', text: key }),
        h('span', { class: 'v', text: value })
      ]);
    }

    var facts = summary.clamped
      ? [fact('Season', summary.season), fact('Status', 'Clamped'), fact('Hand-water', 'every 7–10 d')]
      : [
          fact('Season', summary.season),
          fact('Runs', summary.days),
          fact('Per run', summary.perRun + ' ml'),
          fact('Per week', summary.perWeek + ' ml'),
          fact('Emitters', String(summary.emitters))
        ];

    return h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: 'Drip system' }),
        statusChip(summary.calibrated
          ? { level: 'good', label: 'calibrated flow' }
          : { level: 'warn', label: 'nominal flow — not yet calibrated' })
      ]),
      h('p', {
        class: 'hint',
        text: summary.clamped
          ? 'The winter bypass is on for this tree, so nothing is logged automatically. Hand-water every 7–10 days and tick Watered when you do.'
          : 'Watering entries are created automatically for every scheduled run, so you never log bench water by hand. ' +
            'They are DERIVED from the schedule — emitters x flow x runtime — not measured at the pump, so a clogged emitter ' +
            'still reads as watered. The daily 30-second glance is what catches that.'
      }),
      h('div', { class: 'drip-facts' }, facts),
      h('div', { class: 'field-grid no-print' }, [
        field('Calibrated flow (ml per minute per emitter)', flow,
          'From the catch-cup pass: lift the staked lines into cups, manual-run exactly 2 minutes, then mL ÷ 2. Blank uses the kit’s nominal ' + summary.mlPerMin + '.')
      ]),
      h('div', { class: 'button-row no-print' }, [
        h('button', {
          class: 'button', text: 'Save calibration',
          onclick: function () {
            store.updatePlant(plant.id, { mlPerMin: flow.value === '' ? null : Number(flow.value) });
            render();
          }
        })
      ])
    ]);
  }

  /* ------------------------------------------------- specimen derivations */

  function quarantineStatus(plant) {
    if (!plant.quarantineUntil) return null;
    var until = new Date(plant.quarantineUntil + 'T23:59:59');
    if (until < new Date()) return null;
    return { level: 'bad', label: 'quarantine until ' + plant.quarantineUntil };
  }

  // Wire is on if the newest wire event is a wiring, not a removal.
  function wireStatus(plantId) {
    var last = null;
    store.entriesFor(plantId).forEach(function (e) {
      if (e.wired) last = { on: true, at: e.at, gauge: e.wireGauge };
      if (e.wireRemoved) last = { on: false, at: e.at };
    });
    if (!last || !last.on) return null;
    var days = store.daysSince(last.at);
    return {
      days: days,
      gauge: last.gauge,
      level: days >= WIRE_INSPECT_DAYS ? 'warn' : 'good',
      label: 'wire on ' + days + 'd' + (days >= WIRE_INSPECT_DAYS ? ' — inspect for bite' : '')
    };
  }

  // Re-entry interval from the newest treatment that declared one.
  function reiStatus(plantId) {
    var active = null;
    store.entriesFor(plantId).forEach(function (e) {
      if (!e.treated || e.reiHours == null) return;
      var until = new Date(new Date(e.at).getTime() + e.reiHours * 3600000);
      if (until > new Date() && (!active || until > active.until)) {
        active = { until: until, agent: e.treatmentAgent };
      }
    });
    if (!active) return null;
    return {
      level: 'bad',
      label: 'REI until ' + active.until.toLocaleString(undefined,
        { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) +
        (active.agent ? ' (' + active.agent + ')' : '')
    };
  }

  function laborHours(plantId) {
    var minutes = 0;
    store.entriesFor(plantId).forEach(function (e) { if (e.minutes != null) minutes += e.minutes; });
    return minutes ? Math.round(minutes / 6) / 10 : 0;
  }

  function lastRepot(plantId) {
    var last = null;
    store.entriesFor(plantId).forEach(function (e) { if (e.repotted) last = e.at; });
    return last;
  }

  // Derived light readout — the book's own conversions. Under the bench LEDs
  // the photoperiod is known, so DLI is real; outdoors only the instantaneous
  // PPFD is honest, since one midday lux reading is not a daily integral.
  function lightDerivation(profile, lux) {
    if (lux == null) return '';
    if (profile.drip && profile.drip.schedule) {
      var season = null;
      var monthDay = new Date().toISOString().slice(5, 10);
      profile.drip.schedule.seasons.forEach(function (item) {
        var inRange = item.from <= item.to
          ? (monthDay >= item.from && monthDay <= item.to)
          : (monthDay >= item.from || monthDay <= item.to);
        if (inRange) season = item;
      });
      if (season && season.lightHours) {
        var ppfd = lux / 70;   // white LED ÷70, BOOK
        var dli = ppfd * season.lightHours * 3600 / 1e6;
        return ' · ≈' + Math.round(ppfd) + ' µmol · DLI ≈ ' +
          (Math.round(dli * 10) / 10) + ' mol (' + season.lightHours + ' h)';
      }
    }
    return ' · ≈' + Math.round(lux / 54) + ' µmol midday (sun ÷54)';
  }

  /* -------------------------------------------------------- specimen card */

  function specimenCard(plant, profile) {
    var location = h('input', { type: 'text', name: 'location', value: plant.location || '', placeholder: 'Bench 2, top shelf · south wall' });
    var parent = h('select', { name: 'parentId' }, [h('option', { value: '', text: '—' })].concat(
      store.listPlants().filter(function (p) { return p.id !== plant.id; }).map(function (p) {
        return h('option', { value: p.id, text: p.name, selected: p.id === plant.parentId });
      })
    ));
    var propMethod = h('select', { name: 'propMethod' }, PROP_METHODS.map(function (m) {
      return h('option', { value: m, text: m || '—', selected: m === (plant.propMethod || '') });
    }));
    var ageYears = h('input', { type: 'number', name: 'ageYears', step: '1', min: '0', value: plant.ageYears == null ? '' : plant.ageYears });
    var cost = h('input', { type: 'number', name: 'cost', step: '1', min: '0', value: plant.cost == null ? '' : plant.cost });
    var estValue = h('input', { type: 'number', name: 'estValue', step: '1', min: '0', value: plant.estValue == null ? '' : plant.estValue });
    var grade = h('select', { name: 'grade' }, GRADES.map(function (g) {
      return h('option', { value: g, text: g || '—', selected: g === (plant.grade || '') });
    }));
    var quarantine = h('input', { type: 'date', name: 'quarantineUntil', value: plant.quarantineUntil || '' });

    var chips = h('div', { class: 'button-row' });
    var q = quarantineStatus(plant);
    if (q) chips.appendChild(statusChip(q));
    var wire = wireStatus(plant.id);
    if (wire) chips.appendChild(statusChip(wire));
    var rei = reiStatus(plant.id);
    if (rei) chips.appendChild(statusChip(rei));

    var facts = [];
    var parentPlant = plant.parentId ? store.getPlant(plant.parentId) : null;
    if (parentPlant) {
      facts.push(h('p', { class: 'lineage' }, [
        document.createTextNode('Propagated from '),
        h('a', { href: '#/p/' + parentPlant.id, text: parentPlant.name }),
        document.createTextNode(plant.propMethod ? ' · ' + plant.propMethod : '')
      ]));
    }
    var children = store.childrenOf(plant.id);
    if (children.length) {
      var aliveCount = children.filter(function (c) { return c.status !== 'lost'; }).length;
      var line = h('p', { class: 'lineage' }, [document.createTextNode(
        children.length + (children.length === 1 ? ' propagation' : ' propagations') +
        ' · ' + aliveCount + ' alive: ')]);
      children.forEach(function (child, index) {
        if (index) line.appendChild(document.createTextNode(', '));
        line.appendChild(h('a', { href: '#/p/' + child.id, text: child.name }));
        if (child.status === 'lost') line.appendChild(document.createTextNode(' (lost)'));
      });
      facts.push(line);
    }
    var hours = laborHours(plant.id);
    var repotAt = lastRepot(plant.id);
    var factBits = [];
    if (plant.location) factBits.push('at ' + plant.location);
    if (hours) factBits.push(hours + ' h logged work');
    if (repotAt) factBits.push('last repot ' + charts.formatDateLong(repotAt));
    if (plant.cost != null || plant.estValue != null) {
      factBits.push('cost ' + (plant.cost == null ? '—' : plant.cost) +
        ' · est. value ' + (plant.estValue == null ? '—' : plant.estValue));
    }
    if (factBits.length) facts.push(h('p', { class: 'hint', text: factBits.join(' · ') }));

    return h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [h('h2', { text: 'Specimen record' }), chips]),
      facts.length ? h('div', {}, facts) : null,
      h('details', { class: 'table-view no-print' }, [
        h('summary', { text: 'Edit identity, provenance and valuation' }),
        h('div', { class: 'field-grid' }, [
          field('Location', location, 'Changes are also logged when you fill “Moved to” on a check.'),
          field('Parent / mother stock', parent),
          field('Propagation method', propMethod),
          field('Estimated age (years)', ageYears),
          field('Cost', cost),
          field('Est. value', estValue),
          field('Grade / tier', grade),
          field('Quarantine until', quarantine, 'Handbooks: 3–4 weeks for anything new, in or out.')
        ]),
        h('div', { class: 'button-row' }, [
          h('button', {
            class: 'button button-primary', text: 'Save record',
            onclick: function () {
              store.updatePlant(plant.id, {
                location: location.value, parentId: parent.value, propMethod: propMethod.value,
                ageYears: ageYears.value === '' ? null : Number(ageYears.value),
                cost: cost.value === '' ? null : Number(cost.value),
                estValue: estValue.value === '' ? null : Number(estValue.value),
                grade: grade.value, quarantineUntil: quarantine.value
              });
              render();
            }
          })
        ])
      ])
    ]);
  }

  /* ----------------------------------------------------------- photo card */

  function photoCard(plant) {
    var list = photos.photosFor(plant.id);
    var picker = h('input', { type: 'file', name: 'photoFile', accept: 'image/*', capture: 'environment' });
    var note = h('input', { type: 'text', name: 'photoNote', placeholder: 'front, after wiring' });
    var status = h('p', { class: 'hint' });

    var used = photos.totalBytes();
    var meter = 'Photos: ' + (Math.round(used / 104857.6) / 10) + ' MB of ~' +
      Math.round(photos.maxBytes / 1048576) + ' MB. They stay on this device — ' +
      'downscaled, stripped of EXIF, and never included in sync or the JSON backup.';

    var grid = h('div', { class: 'photo-grid' });
    list.forEach(function (photo) {
      grid.appendChild(h('figure', { class: 'photo-cell' }, [
        h('img', { src: photo.data, alt: photo.note || ('Photo from ' + charts.formatDateLong(photo.at)) }),
        h('figcaption', { class: 'photo-meta', text: charts.formatDateLong(photo.at) + (photo.note ? ' · ' + photo.note : '') }),
        h('div', { class: 'button-row no-print' }, [
          h('button', {
            class: 'button button-quiet button-danger', text: 'Delete',
            onclick: function () {
              if (global.confirm('Delete this photo?')) { photos.removePhoto(plant.id, photo.id); render(); }
            }
          })
        ])
      ]));
    });

    picker.addEventListener('change', function () {
      var file = picker.files && picker.files[0];
      if (!file) return;
      photos.addPhoto(plant.id, file, note.value).then(function () {
        render();
      }).catch(function (error) {
        status.textContent = error.message;
      });
    });

    return h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: 'Photo timeline' }),
        h('span', { class: 'hint', text: list.length + (list.length === 1 ? ' photo' : ' photos') })
      ]),
      list.length ? grid : h('p', { class: 'hint', text: 'No photos yet. Same angles each time — front, back, and the detail you are working on.' }),
      h('div', { class: 'field-grid no-print' }, [
        field('Add a photo', picker),
        field('Caption', note, 'optional')
      ]),
      status,
      h('p', { class: 'hint', text: meter })
    ]);
  }

  /* -------------------------------------------------------------- weather */

  function alertBox(alert, plantName) {
    return h('div', { class: 'alert', 'data-level': alert.level }, [
      plantName ? h('div', { class: 'alert-plant', text: plantName }) : null,
      h('div', { class: 'alert-title', text: alert.title }),
      h('div', { class: 'alert-body', text: alert.detail })
    ]);
  }

  // Plants whose profile actually has a move schedule.
  function movingPlants() {
    return store.listPlants().map(function (plant) {
      return { plant: plant, profile: profiles.get(plant.profileId) };
    }).filter(function (pair) { return !!pair.profile.transitions; });
  }

  function coldestThreshold(pairs) {
    var lowest = null;
    pairs.forEach(function (pair) {
      var fall = pair.profile.transitions.fall;
      if (lowest == null || fall.moveAtLow > lowest) lowest = fall.moveAtLow;
    });
    return lowest;
  }

  function forecastStrip(days, threshold) {
    var strip = h('div', { class: 'forecast' });
    days.slice(0, 10).forEach(function (day) {
      strip.appendChild(h('div', {
        class: 'forecast-day',
        'data-cold': threshold != null && day.low <= threshold ? 'true' : 'false'
      }, [
        h('span', { class: 'd', text: weather.formatDay(day.date).replace(/,.*/, '') }),
        h('span', { class: 'lo', text: Math.round(day.low) + '°' }),
        h('span', { class: 'hi', text: 'hi ' + Math.round(day.high) + '°' })
      ]));
    });
    return strip;
  }

  /**
   * Weather is fetched, so this renders a placeholder and fills it in. Alerts
   * are computed per plant against its own thresholds.
   */
  function weatherCard() {
    var pairs = movingPlants();
    var body = h('div', { class: 'watch-list' }, [
      h('p', { class: 'hint', text: 'Loading forecast…' })
    ]);
    var config = weather.settings();

    var card = h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: 'Weather watch' }),
        h('span', { class: 'hint', text: config.label })
      ]),
      body
    ]);

    if (!pairs.length) {
      body.textContent = '';
      body.appendChild(h('p', {
        class: 'hint',
        text: 'No plants with a move schedule yet. The bergamot and olive profiles carry one.'
      }));
      return card;
    }

    weather.fetchForecast(false).then(function (forecast) {
      body.textContent = '';
      var now = new Date();
      var any = false;

      pairs.forEach(function (pair) {
        var alert = weather.alertFor(pair.profile, forecast, now);
        if (!alert) return;
        any = true;
        body.appendChild(alertBox(alert, pair.plant.name));
        weather.notifyOnce(pair.plant, alert);
      });

      if (!any) {
        body.appendChild(h('p', {
          class: 'hint',
          text: 'Nothing to act on: no forecast night crosses a move threshold, and no move window is within its acclimation lead time.'
        }));
      }

      body.appendChild(forecastStrip(forecast.days, coldestThreshold(pairs)));
      body.appendChild(h('p', {
        class: 'hint',
        text: 'Overnight lows, next 10 days. Fetched ' +
          new Date(forecast.fetchedAt).toLocaleTimeString() + ' from Open-Meteo. ' +
          'Highlighted nights are at or below the warmest move-in threshold among your trees.'
      }));
    }).catch(function (error) {
      body.textContent = '';
      body.appendChild(h('p', {
        class: 'hint',
        text: 'Could not load the forecast: ' + error.message +
          ' Your readings and calendar are unaffected.'
      }));
    });

    return card;
  }

  function weatherSettingsCard() {
    var config = weather.settings();
    var lat = h('input', { type: 'number', name: 'latitude', step: '0.01', value: config.latitude });
    var lon = h('input', { type: 'number', name: 'longitude', step: '0.01', value: config.longitude });
    var label = h('input', { type: 'text', name: 'label', value: config.label });
    var notify = h('input', { type: 'checkbox', name: 'notify', checked: config.notify });
    var status = h('p', { class: 'hint' });

    return h('div', { class: 'card no-print' }, [
      h('h2', { text: 'Location and alerts' }),
      h('div', { class: 'field-grid' }, [
        field('Latitude', lat),
        field('Longitude', lon),
        field('Label', label, 'Only for display')
      ]),
      h('label', { class: 'checkbox' }, [notify, document.createTextNode('Raise a system notification when an alert appears')]),
      h('p', {
        class: 'hint',
        text: 'A site with no server cannot wake a sleeping phone. Notifications fire while the app is ' +
          'open or when you open it — once per alert per day, so it does not nag. For reminders that ' +
          'reach you with the phone asleep, use the calendar file below: your own calendar app fires ' +
          'those in the background, free, with nothing running anywhere.'
      }),
      h('div', { class: 'button-row' }, [
        h('button', {
          class: 'button button-primary', text: 'Save and refresh',
          onclick: function () {
            weather.setSettings({
              latitude: Number(lat.value), longitude: Number(lon.value),
              label: label.value, notify: notify.checked
            });
            if (notify.checked && weather.canNotify()) {
              weather.requestPermission().then(function () { render(); });
            } else {
              render();
            }
          }
        }),
        h('button', {
          class: 'button', text: 'Refresh forecast now',
          onclick: function () { weather.fetchForecast(true).then(render).catch(function () { render(); }); }
        })
      ]),
      status
    ]);
  }

  // Per-plant alert, on its own page.
  function plantWeatherCard(plant, profile) {
    if (!profile.transitions) return null;
    var body = h('div', { class: 'watch-list' }, [h('p', { class: 'hint', text: 'Loading forecast…' })]);
    weather.fetchForecast(false).then(function (forecast) {
      body.textContent = '';
      var alert = weather.alertFor(profile, forecast, new Date());
      if (alert) {
        body.appendChild(alertBox(alert, null));
        weather.notifyOnce(plant, alert);
      } else {
        body.appendChild(h('p', { class: 'hint', text: 'No move action indicated by the current forecast.' }));
      }
      body.appendChild(forecastStrip(forecast.days, profile.transitions.fall.moveAtLow));
    }).catch(function (error) {
      body.textContent = '';
      body.appendChild(h('p', { class: 'hint', text: 'Forecast unavailable: ' + error.message }));
    });

    var t = profile.transitions;
    return h('div', { class: 'card' }, [
      h('div', { class: 'card-head' }, [
        h('h2', { text: 'Weather watch' }),
        h('a', { class: 'hint', href: '#/calendar', text: 'settings' })
      ]),
      h('p', {
        class: 'hint',
        text: 'In ' + t.fall.window[0] + ' to ' + t.fall.window[1] + ' (or sooner at ' + t.fall.moveAtLow +
          ' °F nights) · out ' + t.spring.window[0] + ' to ' + t.spring.window[1] + ' (nights above ' +
          t.spring.moveAboveLow + ' °F) · ' + t.acclimationDays + '-day acclimation each way.'
      }),
      body
    ]);
  }

  /* -------------------------------------------------------------- scanner */

  function setupScanner() {
    var button = document.getElementById('scan-button');
    var dialog = document.getElementById('scan-dialog');
    var video = document.getElementById('scan-video');
    var status = document.getElementById('scan-status');
    if (!button || !dialog) return;

    var stream = null;
    var timer = null;

    function stop() {
      if (timer) { clearInterval(timer); timer = null; }
      if (stream) {
        stream.getTracks().forEach(function (track) { track.stop(); });
        stream = null;
      }
      if (dialog.open) dialog.close();
    }

    dialog.querySelector('[data-close-scan]').addEventListener('click', stop);
    dialog.addEventListener('close', stop);

    button.addEventListener('click', function () {
      // Any phone camera app opens these labels directly; this in-page reader
      // is only for a device already sitting on the tracker.
      if (typeof global.BarcodeDetector === 'undefined') {
        global.alert('This browser cannot scan in-page.\n\nPoint your phone’s camera app at the label instead — it opens the plant page directly.');
        return;
      }
      dialog.showModal();
      status.textContent = 'Starting camera…';
      navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
        .then(function (media) {
          stream = media;
          video.srcObject = media;
          return video.play();
        })
        .then(function () {
          status.textContent = 'Point the camera at a plant label.';
          var detector = new global.BarcodeDetector({ formats: ['qr_code'] });
          timer = setInterval(function () {
            detector.detect(video).then(function (codes) {
              if (!codes.length) return;
              var value = codes[0].rawValue || '';
              var match = value.match(/#\/p\/([a-z0-9]+)/i);
              if (match) {
                stop();
                global.location.hash = '#/p/' + match[1];
              } else {
                status.textContent = 'That code is not a plant label.';
              }
            }).catch(function () { /* transient decode errors are expected */ });
          }, 300);
        })
        .catch(function (error) {
          status.textContent = 'Camera unavailable: ' + error.message;
        });
    });
  }

  /* --------------------------------------------------------------- router */

  // The site is static, so there is nothing running overnight to write the
  // drip log. Instead it is caught up whenever the app is opened — ids are
  // deterministic, so this is idempotent and safe to run on every render.
  function catchUpDrip() {
    var made = 0;
    store.listPlants().forEach(function (plant) {
      made += calendar.backfillDrip(store, profiles.get(plant.profileId), plant, new Date());
    });
    return made;
  }

  function render() {
    var view = document.getElementById('view');
    view.textContent = '';
    catchUpDrip();

    var hash = global.location.hash || '#/';
    var plantMatch = hash.match(/^#\/p\/([^/?]+)/);

    var current = 'list';
    if (plantMatch) {
      renderPlant(view, decodeURIComponent(plantMatch[1]));
    } else if (hash.indexOf('#/labels') === 0) {
      renderLabels(view);
      current = 'labels';
    } else if (hash.indexOf('#/calendar') === 0) {
      renderCalendar(view);
      current = 'calendar';
    } else if (hash.indexOf('#/sync') === 0) {
      renderSync(view);
      current = 'sync';
    } else if (hash.indexOf('#/backup') === 0) {
      renderBackup(view);
      current = 'backup';
    } else {
      renderList(view);
    }

    Array.prototype.forEach.call(document.querySelectorAll('[data-nav]'), function (link) {
      if (link.getAttribute('data-nav') === current) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });

    global.scrollTo(0, 0);
  }

  global.addEventListener('hashchange', render);
  // The header badge is the only always-visible sync signal, so it reports
  // every state including "off" being deliberate.
  function setupSyncBadge() {
    var badge = document.getElementById('sync-status');
    if (!badge) return;
    function paint(state) {
      if (state.level === 'off') {
        badge.hidden = true;
        return;
      }
      badge.hidden = false;
      badge.setAttribute('data-level', state.level);
      badge.textContent = state.message;
    }
    sync.onStatus(paint);
    paint(sync.status());
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupScanner();
    setupSyncBadge();
    render();
    sync.start();
  });

  global.BonsaiApp = { render: render, plantUrl: plantUrl };
})(window);

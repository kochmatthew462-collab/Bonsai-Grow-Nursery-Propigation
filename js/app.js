/*
 * Bonsai Nursery Tracker — routing and views.
 *
 * Four hash routes: the nursery list, a plant detail page, the printable label
 * sheet, and backup. A QR label encodes <base>#/p/<id>, so scanning it with any
 * phone camera opens that plant's page directly.
 */
(function (global) {
  'use strict';

  var store = global.BonsaiStore;
  var charts = global.BonsaiCharts;
  var QR = global.BonsaiQR;

  var METRICS = [
    { key: 'ph', name: 'pH', unit: '', color: 'var(--series-ph)', decimals: 1 },
    { key: 'moisture', name: 'Moisture', unit: '', color: 'var(--series-moisture)', decimals: 1 },
    { key: 'growth', name: 'Growth', unit: 'mm', color: 'var(--series-growth)', decimals: 0 }
  ];

  var STAGES = ['cutting', 'air layer', 'seedling', 'nursery stock', 'in training', 'refinement'];

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

  /* ------------------------------------------------------------ stat tiles */

  function statTile(label, value, unit, sub, color) {
    return h('div', { class: 'stat-tile' }, [
      h('div', { class: 'stat-label' }, [
        color ? h('span', { class: 'stat-key', style: 'background:' + color }) : null,
        h('span', { text: label })
      ]),
      h('div', { class: 'stat-value' }, [
        document.createTextNode(value),
        unit ? h('span', { class: 'unit', text: unit }) : null
      ]),
      h('div', { class: 'stat-sub', text: sub || '' })
    ]);
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
            'Open a plant to log a check, or print its QR label from the Labels page.'
          : 'No plants yet. Add your first below, then print a QR label for its pot.'
      })
    ]));

    if (plants.length) {
      var table = h('table', {}, [
        h('thead', {}, [h('tr', {}, [
          h('th', { text: 'Plant' }),
          h('th', { text: 'Stage' }),
          h('th', { class: 'num', text: 'pH' }),
          h('th', { class: 'num', text: 'Moisture' }),
          h('th', { class: 'num', text: 'Growth' }),
          h('th', { class: 'num', text: 'Watered' }),
          h('th', { class: 'num', text: 'Fed' }),
          h('th', { class: 'num', text: 'Checks' })
        ])])
      ]);
      var body = h('tbody');
      plants.forEach(function (plant) {
        var latest = store.latest(plant.id);
        var wateredDays = latest.watered ? store.daysSince(latest.watered.at) : null;
        var fedDays = latest.fertilised ? store.daysSince(latest.fertilised.at) : null;
        body.appendChild(h('tr', {}, [
          h('td', {}, [
            h('a', { class: 'plant-row-link', href: '#/p/' + plant.id, text: plant.name }),
            plant.species ? h('div', { class: 'hint', text: plant.species }) : null
          ]),
          h('td', { text: plant.stage || '' }),
          h('td', { class: 'num', text: latest.ph ? charts.trimNumber(latest.ph.ph, 1) : '—' }),
          h('td', { class: 'num', text: latest.moisture ? charts.trimNumber(latest.moisture.moisture, 1) : '—' }),
          h('td', { class: 'num', text: latest.growth ? charts.trimNumber(latest.growth.growth, 0) + ' mm' : '—' }),
          h('td', { class: 'num', text: wateredDays == null ? '—' : wateredDays + 'd ago' }),
          h('td', { class: 'num', text: fedDays == null ? '—' : fedDays + 'd ago' }),
          h('td', { class: 'num', text: String(store.entriesFor(plant.id).length) })
        ]));
      });
      table.appendChild(body);
      view.appendChild(h('div', { class: 'card' }, [
        h('div', { class: 'table-wrap' }, [table])
      ]));
    }

    // Add-plant form.
    var form = h('form', { class: 'card' });
    var name = h('input', { type: 'text', required: true, placeholder: 'Shohin juniper #4' });
    var species = h('input', { type: 'text', placeholder: "Juniperus procumbens 'Nana'" });
    var stage = h('select', {}, STAGES.map(function (s) {
      return h('option', { value: s, text: s });
    }));
    var source = h('input', { type: 'text', placeholder: 'cutting from bench 2' });
    var startedOn = h('input', { type: 'date', value: store.today() });
    var notes = h('textarea', { placeholder: 'Rooting medium, position, anything worth remembering.' });

    form.appendChild(h('h2', { text: 'Add a plant' }));
    form.appendChild(h('div', { class: 'field-grid' }, [
      field('Name', name),
      field('Species', species),
      field('Stage', stage),
      field('Source', source),
      field('Started on', startedOn)
    ]));
    form.appendChild(field('Notes', notes));
    form.appendChild(h('div', { class: 'button-row' }, [
      h('button', { type: 'submit', class: 'button button-primary', text: 'Add plant' })
    ]));
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var plant = store.addPlant({
        name: name.value, species: species.value, stage: stage.value,
        source: source.value, startedOn: startedOn.value, notes: notes.value
      });
      global.location.hash = '#/p/' + plant.id;
    });
    view.appendChild(form);
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
            'label printed from another device, import that device\'s backup first.'
        }),
        h('div', { class: 'button-row' }, [
          h('a', { class: 'button', href: '#/', text: 'Back to nursery' }),
          h('a', { class: 'button', href: '#/backup', text: 'Import a backup' })
        ])
      ]));
      return;
    }

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

    /* --- headline numbers */
    var growthDelta = '';
    var growthSeries = store.seriesFor(id, 'growth');
    if (growthSeries.length > 1) {
      var change = growthSeries[growthSeries.length - 1].value - growthSeries[growthSeries.length - 2].value;
      growthDelta = (change >= 0 ? '+' : '') + charts.trimNumber(change, 0) + ' mm since last check';
    }

    var wateredDays = latest.watered ? store.daysSince(latest.watered.at) : null;
    var fedDays = latest.fertilised ? store.daysSince(latest.fertilised.at) : null;

    view.appendChild(h('div', { class: 'kpi-row' }, [
      statTile('Latest pH', latest.ph ? charts.trimNumber(latest.ph.ph, 1) : '—', '',
        latest.ph ? charts.formatDate(latest.ph.at) : 'not measured', 'var(--series-ph)'),
      statTile('Moisture', latest.moisture ? charts.trimNumber(latest.moisture.moisture, 1) : '—', '',
        latest.moisture ? charts.formatDate(latest.moisture.at) : 'not measured', 'var(--series-moisture)'),
      statTile('Growth', latest.growth ? charts.trimNumber(latest.growth.growth, 0) : '—', 'mm',
        growthDelta || (latest.growth ? charts.formatDate(latest.growth.at) : 'not measured'), 'var(--series-growth)'),
      statTile('Watered', wateredDays == null ? '—' : String(wateredDays), wateredDays == null ? '' : 'd ago',
        latest.watered ? charts.formatDate(latest.watered.at) : 'never logged', 'var(--series-water)'),
      statTile('Fed', fedDays == null ? '—' : String(fedDays), fedDays == null ? '' : 'd ago',
        latest.fertilised ? charts.formatDate(latest.fertilised.at) : 'never logged', 'var(--series-fert)')
    ]));

    /* --- log a check */
    view.appendChild(logForm(id));

    /* --- trends */
    var chartGrid = h('div', { class: 'chart-grid-cards' });
    METRICS.forEach(function (metric) {
      var points = store.seriesFor(id, metric.key);
      var holder = h('div', { class: 'chart-holder' });
      var card = h('div', { class: 'card' }, [
        h('div', { class: 'card-head' }, [
          h('h2', { text: metric.name + (metric.unit ? ' (' + metric.unit + ')' : '') }),
          h('span', { class: 'hint', text: points.length + (points.length === 1 ? ' reading' : ' readings') })
        ]),
        holder
      ]);
      if (points.length) card.appendChild(valueTableView(metric, points));
      chartGrid.appendChild(card);
      charts.trend(holder, {
        points: points, color: metric.color, name: metric.name,
        unit: metric.unit, decimals: metric.decimals
      });
    });
    view.appendChild(chartGrid);

    /* --- care events */
    var careRows = [
      { name: 'Watering', color: 'var(--series-water)', events: store.eventsFor(id, 'watered') },
      { name: 'Fertiliser', color: 'var(--series-fert)', events: store.eventsFor(id, 'fertilised') }
    ];
    var careHolder = h('div', { class: 'chart-holder' });
    var careCard = h('div', { class: 'card' }, [
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
    ]);
    view.appendChild(careCard);
    charts.careTimeline(careHolder, { rows: careRows });

    /* --- full history */
    view.appendChild(historyCard(id, entries));

    /* --- label */
    view.appendChild(labelCard(plant));

    /* --- admin */
    view.appendChild(h('div', { class: 'card no-print' }, [
      h('h2', { text: 'Manage plant' }),
      h('div', { class: 'button-row' }, [
        h('button', {
          class: 'button button-danger',
          text: 'Delete this plant and its readings',
          onclick: function () {
            if (global.confirm('Delete "' + plant.name + '" and all of its readings? This cannot be undone.')) {
              store.deletePlant(plant.id);
              global.location.hash = '#/';
            }
          }
        })
      ])
    ]));
  }

  function logForm(plantId) {
    var form = h('form', { class: 'card no-print' });
    var at = h('input', { type: 'date', value: store.today() });
    var ph = h('input', { type: 'number', step: '0.1', min: '0', max: '14', placeholder: '6.4' });
    var moisture = h('input', { type: 'number', step: '0.1', min: '0', max: '10', placeholder: '4' });
    var growth = h('input', { type: 'number', step: '1', placeholder: '38' });
    var watered = h('input', { type: 'checkbox' });
    var waterMl = h('input', { type: 'number', step: '10', min: '0', placeholder: '250' });
    var fertilised = h('input', { type: 'checkbox' });
    var fertiliser = h('input', { type: 'text', placeholder: 'Biogold' });
    var fertAmount = h('input', { type: 'text', placeholder: '2 pellets' });
    var note = h('input', { type: 'text', placeholder: 'Back buds opening on the lower trunk.' });

    form.appendChild(h('h2', { text: 'Log a check' }));
    form.appendChild(h('p', {
      class: 'hint',
      text: 'Leave anything you did not measure blank — a blank field records nothing rather than a zero.'
    }));
    form.appendChild(h('div', { class: 'field-grid' }, [
      field('Date', at),
      field('pH', ph, '0–14'),
      field('Moisture', moisture, 'probe reading 0–10'),
      field('Growth', growth, 'mm, measured the same way each time')
    ]));
    form.appendChild(h('div', { class: 'field-grid' }, [
      h('label', { class: 'checkbox' }, [watered, document.createTextNode('Watered')]),
      field('Water amount', waterMl, 'ml, optional'),
      h('label', { class: 'checkbox' }, [fertilised, document.createTextNode('Fertilised')]),
      field('Fertiliser', fertiliser),
      field('Amount', fertAmount)
    ]));
    form.appendChild(field('Note', note));
    form.appendChild(h('div', { class: 'button-row' }, [
      h('button', { type: 'submit', class: 'button button-primary', text: 'Save check' })
    ]));

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var hasSomething = ph.value || moisture.value || growth.value ||
        watered.checked || fertilised.checked || note.value;
      if (!hasSomething) {
        global.alert('Nothing to save — record at least one measurement, a care action, or a note.');
        return;
      }
      store.addEntry(plantId, {
        at: at.value, ph: ph.value, moisture: moisture.value, growth: growth.value,
        watered: watered.checked, waterMl: waterMl.value,
        fertilised: fertilised.checked, fertiliser: fertiliser.value,
        fertAmount: fertAmount.value, note: note.value
      });
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
            h('th', { class: 'num', text: metric.name + (metric.unit ? ' (' + metric.unit + ')' : '') })
          ])]),
          body
        ])
      ])
    ]);
  }

  function historyCard(plantId, entries) {
    if (!entries.length) {
      return h('div', { class: 'card' }, [
        h('h2', { text: 'History' }),
        h('p', { class: 'hint', text: 'No checks logged yet.' })
      ]);
    }
    var body = h('tbody');
    entries.slice().reverse().forEach(function (entry) {
      var care = [];
      if (entry.watered) care.push('water' + (entry.waterMl != null ? ' ' + entry.waterMl + 'ml' : ''));
      if (entry.fertilised) care.push([entry.fertiliser, entry.fertAmount].filter(Boolean).join(' ') || 'fertiliser');
      body.appendChild(h('tr', {}, [
        h('td', { text: charts.formatDateLong(entry.at) }),
        h('td', { class: 'num', text: entry.ph == null ? '—' : charts.trimNumber(entry.ph, 1) }),
        h('td', { class: 'num', text: entry.moisture == null ? '—' : charts.trimNumber(entry.moisture, 1) }),
        h('td', { class: 'num', text: entry.growth == null ? '—' : charts.trimNumber(entry.growth, 0) }),
        h('td', { text: care.join(', ') || '—' }),
        h('td', { text: entry.note || '' }),
        h('td', { class: 'no-print' }, [
          h('button', {
            class: 'button button-quiet button-danger', text: 'Delete',
            onclick: function () {
              if (global.confirm('Delete this check?')) { store.deleteEntry(entry.id); render(); }
            }
          })
        ])
      ]));
    });

    return h('div', { class: 'card' }, [
      h('h2', { text: 'History' }),
      h('div', { class: 'table-wrap' }, [
        h('table', {}, [
          h('thead', {}, [h('tr', {}, [
            h('th', { text: 'Date' }),
            h('th', { class: 'num', text: 'pH' }),
            h('th', { class: 'num', text: 'Moisture' }),
            h('th', { class: 'num', text: 'Growth (mm)' }),
            h('th', { text: 'Care' }),
            h('th', { text: 'Note' }),
            h('th', { class: 'no-print', text: '' })
          ])]),
          body
        ])
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
        text: 'Each label carries a QR code pointing at that plant\'s page. Print onto ' +
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
        h('button', {
          class: 'button', text: 'Apply',
          onclick: function () { setLabelBase(base.value); render(); }
        }),
        h('button', {
          class: 'button button-primary', text: 'Print',
          onclick: function () { global.print(); }
        })
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
        text: 'Readings live in this browser\'s storage on this device. They are not ' +
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
          'The CSV is one row per check, ready for a PivotTable in Excel or Google Sheets.'
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
        global.alert('This browser cannot scan in-page.\n\nPoint your phone\'s camera app at the label instead — it opens the plant page directly.');
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

  function render() {
    var view = document.getElementById('view');
    view.textContent = '';

    var hash = global.location.hash || '#/';
    var plantMatch = hash.match(/^#\/p\/([^/?]+)/);

    var current = 'list';
    if (plantMatch) {
      renderPlant(view, decodeURIComponent(plantMatch[1]));
      current = 'list';
    } else if (hash.indexOf('#/labels') === 0) {
      renderLabels(view);
      current = 'labels';
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
  document.addEventListener('DOMContentLoaded', function () {
    setupScanner();
    render();
  });

  // Expose for the smoke test.
  global.BonsaiApp = { render: render, plantUrl: plantUrl };
})(window);

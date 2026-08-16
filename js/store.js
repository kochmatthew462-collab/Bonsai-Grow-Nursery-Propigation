/*
 * Bonsai store — plants and readings, held in localStorage.
 *
 * localStorage is per-browser and per-device: it does not sync between the
 * greenhouse phone and the office laptop. That is a deliberate trade (no
 * server, no account, no subscription), and the JSON export/import below is
 * how you move a nursery between devices or back it up. See the README.
 */
(function (global) {
  'use strict';

  var KEY = 'bonsai.nursery.v1';

  // No vowels and no look-alike characters, so a hand-typed label ID from
  // across the bench does not turn 0 into O or 1 into l.
  var ID_ALPHABET = '23456789abcdefghjkmnpqrstuvwxyz';

  var listeners = [];
  var cache = null;

  function blank() {
    return { version: 1, plants: [], entries: [] };
  }

  function load() {
    if (cache) return cache;
    try {
      var raw = global.localStorage.getItem(KEY);
      cache = raw ? JSON.parse(raw) : blank();
    } catch (error) {
      cache = blank();
    }
    if (!Array.isArray(cache.plants)) cache.plants = [];
    if (!Array.isArray(cache.entries)) cache.entries = [];
    return cache;
  }

  function persist() {
    try {
      global.localStorage.setItem(KEY, JSON.stringify(cache));
    } catch (error) {
      global.alert('Could not save — browser storage is full or blocked.\n\n' +
        'Export a JSON backup before you lose anything.');
      return;
    }
    listeners.forEach(function (fn) { fn(); });
  }

  function newId(length) {
    var size = length || 6;
    var out = '';
    var bytes = new Uint8Array(size);
    if (global.crypto && global.crypto.getRandomValues) {
      global.crypto.getRandomValues(bytes);
    } else {
      for (var i = 0; i < size; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    for (var k = 0; k < size; k++) out += ID_ALPHABET[bytes[k] % ID_ALPHABET.length];
    return out;
  }

  function uniquePlantId() {
    var data = load();
    for (var attempt = 0; attempt < 50; attempt++) {
      var id = newId(6);
      var taken = data.plants.some(function (p) { return p.id === id; });
      if (!taken) return id;
    }
    return newId(10);
  }

  /* ------------------------------------------------------------- plants */

  function listPlants() {
    return load().plants.slice().sort(function (a, b) {
      return (a.name || '').localeCompare(b.name || '');
    });
  }

  function getPlant(id) {
    return load().plants.filter(function (p) { return p.id === id; })[0] || null;
  }

  function addPlant(fields) {
    var data = load();
    var plant = {
      id: uniquePlantId(),
      name: (fields.name || '').trim() || 'Untitled',
      species: (fields.species || '').trim(),
      stage: fields.stage || 'cutting',
      profileId: fields.profileId || 'generic',
      source: (fields.source || '').trim(),
      startedOn: fields.startedOn || today(),
      notes: (fields.notes || '').trim(),
      createdAt: new Date().toISOString()
    };
    data.plants.push(plant);
    persist();
    return plant;
  }

  function updatePlant(id, fields) {
    var plant = getPlant(id);
    if (!plant) return null;
    ['name', 'species', 'stage', 'profileId', 'source', 'startedOn', 'notes'].forEach(function (key) {
      if (fields[key] != null) plant[key] = fields[key];
    });
    persist();
    return plant;
  }

  function deletePlant(id) {
    var data = load();
    data.plants = data.plants.filter(function (p) { return p.id !== id; });
    data.entries = data.entries.filter(function (e) { return e.plantId !== id; });
    persist();
  }

  /* ------------------------------------------------------------ entries */

  function entriesFor(plantId) {
    return load().entries
      .filter(function (e) { return e.plantId === plantId; })
      .sort(function (a, b) { return a.at.localeCompare(b.at); });
  }

  // Blank fields stay blank: a check where you measured pH but not moisture
  // must not record a moisture of zero.
  function numberOrNull(value) {
    if (value == null || value === '') return null;
    var n = Number(value);
    return isFinite(n) ? n : null;
  }

  function addEntry(plantId, fields) {
    var data = load();
    var entry = {
      id: newId(10),
      plantId: plantId,
      at: fields.at ? new Date(fields.at).toISOString() : new Date().toISOString(),
      ph: numberOrNull(fields.ph),
      moisture: numberOrNull(fields.moisture),
      ec: numberOrNull(fields.ec),
      growth: numberOrNull(fields.growth),
      tempLow: numberOrNull(fields.tempLow),
      tempHigh: numberOrNull(fields.tempHigh),
      humidity: numberOrNull(fields.humidity),
      light: numberOrNull(fields.light),
      chill: numberOrNull(fields.chill),
      watered: !!fields.watered,
      waterMl: numberOrNull(fields.waterMl),
      fertilised: !!fields.fertilised,
      fertiliser: (fields.fertiliser || '').trim(),
      fertAmount: (fields.fertAmount || '').trim(),
      // Occasional milestones. Kept as flags rather than chart series because
      // they happen a few times a year, not on every check.
      repotted: !!fields.repotted,
      pruned: !!fields.pruned,
      pestSeen: !!fields.pestSeen,
      pestType: (fields.pestType || '').trim(),
      suckersRemoved: !!fields.suckersRemoved,
      graftChecked: !!fields.graftChecked,
      moved: fields.moved || '',
      note: (fields.note || '').trim()
    };
    data.entries.push(entry);
    persist();
    return entry;
  }

  function deleteEntry(entryId) {
    var data = load();
    data.entries = data.entries.filter(function (e) { return e.id !== entryId; });
    persist();
  }

  /* ------------------------------------------------------ derived views */

  function seriesFor(plantId, metric) {
    return entriesFor(plantId)
      .filter(function (e) { return e[metric] != null; })
      .map(function (e) { return { at: e.at, value: e[metric], entry: e }; });
  }

  function eventsFor(plantId, kind) {
    return entriesFor(plantId)
      .filter(function (e) { return kind === 'watered' ? e.watered : e.fertilised; })
      .map(function (e) {
        var detail = kind === 'watered'
          ? (e.waterMl != null ? e.waterMl + ' ml' : 'watered')
          : ([e.fertiliser, e.fertAmount].filter(Boolean).join(' ') || 'fertilised');
        return { at: e.at, detail: detail, entry: e };
      });
  }

  var METRIC_KEYS = ['ph', 'moisture', 'ec', 'growth', 'tempLow', 'tempHigh', 'humidity', 'light', 'chill'];
  var EVENT_KEYS = ['watered', 'fertilised', 'repotted', 'pruned', 'pestSeen', 'suckersRemoved'];

  // The most recent entry carrying each metric, and the most recent occurrence
  // of each event — a check that measured only pH must not blank the rest.
  function latest(plantId) {
    var entries = entriesFor(plantId);
    var out = { last: null };
    METRIC_KEYS.concat(EVENT_KEYS).forEach(function (key) { out[key] = null; });
    if (!entries.length) return out;
    out.last = entries[entries.length - 1];
    for (var i = entries.length - 1; i >= 0; i--) {
      var e = entries[i];
      METRIC_KEYS.forEach(function (key) {
        if (out[key] == null && e[key] != null) out[key] = e;
      });
      EVENT_KEYS.forEach(function (key) {
        if (out[key] == null && e[key]) out[key] = e;
      });
    }
    return out;
  }

  var MILESTONES = [
    { key: 'repotted', label: 'Repotted' },
    { key: 'pruned', label: 'Pruned / wired' },
    { key: 'pestSeen', label: 'Pest seen', detail: 'pestType', alert: true },
    { key: 'suckersRemoved', label: 'Rootstock suckers removed' },
    { key: 'graftChecked', label: 'Graft line checked' }
  ];

  function milestonesFor(plantId) {
    var out = [];
    entriesFor(plantId).forEach(function (e) {
      MILESTONES.forEach(function (m) {
        if (!e[m.key]) return;
        out.push({
          at: e.at, label: m.label, alert: !!m.alert,
          detail: m.detail ? (e[m.detail] || '') : '', entryId: e.id
        });
      });
      if (e.moved) {
        out.push({ at: e.at, label: 'Moved ' + e.moved, alert: false, detail: '', entryId: e.id });
      }
    });
    return out.sort(function (a, b) { return b.at.localeCompare(a.at); });
  }

  function daysSince(iso) {
    if (!iso) return null;
    var ms = Date.now() - new Date(iso).getTime();
    return Math.max(0, Math.floor(ms / 86400000));
  }

  function today() {
    var d = new Date();
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }

  /* ------------------------------------------------- backup & spreadsheet */

  function exportJson() {
    return JSON.stringify(load(), null, 2);
  }

  /**
   * Merge a backup into the current nursery. Plants and readings are matched
   * on id, so re-importing the same file twice does not duplicate anything,
   * and importing a phone's export onto a laptop combines the two.
   */
  function importJson(text) {
    var incoming = JSON.parse(text);
    if (!incoming || !Array.isArray(incoming.plants) || !Array.isArray(incoming.entries)) {
      throw new Error('That file does not look like a nursery backup.');
    }
    var data = load();
    var plantIds = {};
    data.plants.forEach(function (p) { plantIds[p.id] = true; });
    var entryIds = {};
    data.entries.forEach(function (e) { entryIds[e.id] = true; });

    var addedPlants = 0;
    var addedEntries = 0;
    incoming.plants.forEach(function (p) {
      if (p && p.id && !plantIds[p.id]) {
        data.plants.push(p);
        plantIds[p.id] = true;
        addedPlants++;
      }
    });
    incoming.entries.forEach(function (e) {
      if (e && e.id && !entryIds[e.id]) {
        data.entries.push(e);
        entryIds[e.id] = true;
        addedEntries++;
      }
    });
    persist();
    return { plants: addedPlants, entries: addedEntries };
  }

  function csvCell(value) {
    var s = value == null ? '' : String(value);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function exportCsv() {
    var data = load();
    var names = {};
    data.plants.forEach(function (p) { names[p.id] = p; });
    var header = ['plant_id', 'plant_name', 'species', 'profile', 'date',
      'ph', 'moisture_pct', 'ec_ms_cm', 'growth_mm', 'temp_low_f', 'temp_high_f',
      'humidity_pct', 'light_lux', 'chill_hours',
      'watered', 'water_ml', 'fertilised', 'fertiliser', 'fert_amount',
      'repotted', 'pruned', 'pest_seen', 'pest_type', 'suckers_removed',
      'graft_checked', 'moved', 'note'];
    var yn = function (v) { return v ? 'yes' : 'no'; };
    var lines = [header.join(',')];
    data.entries.slice().sort(function (a, b) { return a.at.localeCompare(b.at); })
      .forEach(function (e) {
        var plant = names[e.plantId] || {};
        lines.push([
          e.plantId, plant.name, plant.species, plant.profileId, e.at,
          e.ph, e.moisture, e.ec, e.growth, e.tempLow, e.tempHigh,
          e.humidity, e.light, e.chill,
          yn(e.watered), e.waterMl, yn(e.fertilised), e.fertiliser, e.fertAmount,
          yn(e.repotted), yn(e.pruned), yn(e.pestSeen), e.pestType, yn(e.suckersRemoved),
          yn(e.graftChecked), e.moved, e.note
        ].map(csvCell).join(','));
      });
    return lines.join('\n');
  }

  function replaceAll(next) {
    cache = next;
    persist();
  }

  function subscribe(fn) {
    listeners.push(fn);
  }

  global.BonsaiStore = {
    listPlants: listPlants,
    getPlant: getPlant,
    addPlant: addPlant,
    updatePlant: updatePlant,
    deletePlant: deletePlant,
    entriesFor: entriesFor,
    addEntry: addEntry,
    deleteEntry: deleteEntry,
    seriesFor: seriesFor,
    eventsFor: eventsFor,
    milestonesFor: milestonesFor,
    metricKeys: METRIC_KEYS,
    latest: latest,
    daysSince: daysSince,
    today: today,
    exportJson: exportJson,
    importJson: importJson,
    exportCsv: exportCsv,
    replaceAll: replaceAll,
    subscribe: subscribe
  };
})(window);

/*
 * Calendar — dated tasks, and the derived drip log.
 *
 * TASKS. Each profile carries dated windows transcribed from its handbook
 * (prune, repot, feed, move, scout, system). This expands them against the
 * calendar, works out what is due, overdue or coming, and remembers what has
 * been marked done for a given year.
 *
 * DRIP. The bench's GrowHub outlet is a smart switch: it reports on/off, and
 * there is no public API to ask it anything anyway. So delivered water is
 * DERIVED, not measured — emitters x calibrated flow x runtime, on the days the
 * season's recipe runs. That is honest automation as long as two things stay
 * true: the calibration is real (the packet's catch-cup pass), and somebody
 * still does the 30-second daily glance to confirm the cycle actually ran.
 * A clogged emitter looks identical to a working one from here.
 */
(function (global) {
  'use strict';

  var DAY_MS = 86400000;
  // A missed window nags for this long, then stops — otherwise every window
  // you ever skipped stays red forever.
  var OVERDUE_GRACE_DAYS = 45;
  // First run on an established nursery should not invent months of history.
  var MAX_BACKFILL_DAYS = 30;

  var CATEGORY_LABELS = {
    move: 'Move', prune: 'Prune', repot: 'Repot', feed: 'Feed',
    pest: 'Scout', measure: 'Measure', system: 'System'
  };

  function startOfDay(date) {
    var copy = new Date(date.getTime());
    copy.setHours(0, 0, 0, 0);
    return copy;
  }

  function dateOf(year, monthDay) {
    var parts = String(monthDay).split('-');
    return new Date(year, Number(parts[0]) - 1, Number(parts[1]));
  }

  function isoDay(date) {
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
  }

  function formatWindow(start, end) {
    var opts = { month: 'short', day: 'numeric' };
    var a = start.toLocaleDateString(undefined, opts);
    if (isoDay(start) === isoDay(end)) return a;
    return a + ' – ' + end.toLocaleDateString(undefined, opts);
  }

  /* ------------------------------------------------------------- tasks */

  // A window whose end falls before its start wraps the year end, e.g. the
  // pomegranate's Dec-Feb structural prune.
  function windowFor(task, year) {
    var start = dateOf(year, task.from);
    var end = dateOf(year, task.to);
    if (end < start) end = dateOf(year + 1, task.to);
    end = new Date(end.getTime() + DAY_MS - 1);
    return { start: start, end: end, year: year };
  }

  /**
   * The instance of a task that matters right now: the window containing
   * today, else a recently missed one, else the next one due.
   */
  function currentInstance(task, today) {
    var year = today.getFullYear();
    var candidates = [windowFor(task, year - 1), windowFor(task, year), windowFor(task, year + 1)];

    var containing = candidates.filter(function (w) {
      return today >= w.start && today <= w.end;
    })[0];
    if (containing) return { window: containing, state: 'due' };

    var missed = candidates.filter(function (w) {
      return w.end < today && (today - w.end) <= OVERDUE_GRACE_DAYS * DAY_MS;
    }).sort(function (a, b) { return b.end - a.end; })[0];
    if (missed) return { window: missed, state: 'overdue' };

    var next = candidates.filter(function (w) { return w.start > today; })
      .sort(function (a, b) { return a.start - b.start; })[0];
    if (next) return { window: next, state: 'upcoming' };
    return null;
  }

  /**
   * Every task for one plant, resolved against today and against what has
   * already been marked done.
   */
  function tasksForPlant(plant, profile, today, isDone) {
    var now = startOfDay(today || new Date());
    return (profile.tasks || []).map(function (task) {
      var instance = currentInstance(task, now);
      if (!instance) return null;
      var done = isDone(plant.id, task.id, instance.window.year);
      return {
        plantId: plant.id,
        plantName: plant.name,
        profileName: profile.name,
        task: task,
        category: task.category,
        categoryLabel: CATEGORY_LABELS[task.category] || task.category,
        start: instance.window.start,
        end: instance.window.end,
        year: instance.window.year,
        when: formatWindow(instance.window.start, instance.window.end),
        daysAway: Math.round((instance.window.start - now) / DAY_MS),
        state: done ? 'done' : instance.state,
        doneAt: done || null
      };
    }).filter(Boolean);
  }

  var ORDER = { overdue: 0, due: 1, upcoming: 2, done: 3 };

  function sortTasks(list) {
    return list.slice().sort(function (a, b) {
      if (ORDER[a.state] !== ORDER[b.state]) return ORDER[a.state] - ORDER[b.state];
      return a.start - b.start;
    });
  }

  /* -------------------------------------------------------------- drip */

  // Season ranges are MM-DD and may wrap the year end (winter does).
  function seasonFor(schedule, date) {
    var monthDay = isoDay(date).slice(5);
    var found = null;
    (schedule.seasons || []).forEach(function (season) {
      var inRange = season.from <= season.to
        ? (monthDay >= season.from && monthDay <= season.to)
        : (monthDay >= season.from || monthDay <= season.to);
      if (inRange) found = season;
    });
    return found;
  }

  function emittersFor(drip, season) {
    if (!season) return 0;
    if (season.label === 'Winter' && drip.winterEmitters != null) return drip.winterEmitters;
    return drip.emitters == null ? 0 : drip.emitters;
  }

  /** What the drip is scheduled to deliver to this plant on this day, in mL. */
  function dripOn(profile, plant, date) {
    var drip = profile.drip;
    if (!drip || !drip.schedule) return null;
    var season = seasonFor(drip.schedule, date);
    if (!season) return null;
    if (season.days.indexOf(date.getDay()) < 0) return null;   // not a run day
    var emitters = emittersFor(drip, season);
    if (!emitters) return null;
    var flow = (plant && plant.mlPerMin) || drip.schedule.nominalMlPerMin;
    return {
      date: new Date(date.getTime()),
      season: season.label,
      minutes: season.minutes,
      emitters: emitters,
      mlPerMin: flow,
      ml: Math.round(emitters * flow * season.minutes),
      calibrated: !!(plant && plant.mlPerMin)
    };
  }

  /** A one-line description of the programme in force today. */
  function dripSummary(profile, plant, today) {
    var drip = profile.drip;
    if (!drip || !drip.schedule) return null;
    var now = startOfDay(today || new Date());
    var season = seasonFor(drip.schedule, now);
    if (!season) return null;
    var emitters = emittersFor(drip, season);
    var flow = (plant && plant.mlPerMin) || drip.schedule.nominalMlPerMin;
    var names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    return {
      season: season.label,
      days: season.days.map(function (d) { return names[d]; }).join(' · '),
      minutes: season.minutes,
      emitters: emitters,
      mlPerMin: flow,
      perRun: Math.round(emitters * flow * season.minutes),
      perWeek: Math.round(emitters * flow * season.minutes * season.days.length),
      calibrated: !!(plant && plant.mlPerMin),
      clamped: emitters === 0
    };
  }

  /**
   * Generate the drip entries that should exist for days since the last one.
   * Ids are deterministic, so this is idempotent and safe to run on every load
   * and safe to sync — two devices generate byte-identical records.
   */
  function backfillDrip(store, profile, plant, today) {
    var drip = profile.drip;
    if (!drip || !drip.schedule) return 0;
    var now = startOfDay(today || new Date());

    var existing = {};
    var earliest = null;
    store.entriesFor(plant.id).forEach(function (entry) {
      if (entry.auto === 'drip') existing[entry.id] = true;
      var at = new Date(entry.at);
      if (!earliest || at < earliest) earliest = at;
    });

    // Never invent water from before the plant was being tracked.
    var floor = new Date(now.getTime() - MAX_BACKFILL_DAYS * DAY_MS);
    var startedOn = plant.startedOn ? new Date(plant.startedOn) : null;
    if (startedOn && startedOn > floor) floor = startOfDay(startedOn);
    if (earliest && earliest > floor) floor = startOfDay(earliest);

    var made = 0;
    for (var day = new Date(floor.getTime()); day <= now; day = new Date(day.getTime() + DAY_MS)) {
      var run = dripOn(profile, plant, day);
      if (!run) continue;
      var id = 'drip-' + plant.id + '-' + isoDay(day);
      if (existing[id]) continue;
      store.addEntry(plant.id, {
        id: id,
        at: isoDay(day),
        watered: true,
        waterMl: run.ml,
        auto: 'drip',
        note: 'Drip: ' + run.emitters + ' emitter' + (run.emitters === 1 ? '' : 's') +
          ' x ' + run.minutes + ' min (' + run.season.toLowerCase() + ' recipe' +
          (run.calibrated ? '' : ', nominal flow') + ')'
      });
      made++;
    }
    return made;
  }


  /* --------------------------------------------------------------- export */

  // RFC 5545 wants lines folded at 75 octets, continued with a leading space.
  function fold(line) {
    if (line.length <= 74) return line;
    var out = [line.slice(0, 74)];
    var rest = line.slice(74);
    while (rest.length > 73) {
      out.push(' ' + rest.slice(0, 73));
      rest = rest.slice(73);
    }
    if (rest.length) out.push(' ' + rest);
    return out.join('\r\n');
  }

  function escapeText(value) {
    return String(value || '')
      .replace(/\\/g, '\\\\')
      .replace(/;/g, '\\;')
      .replace(/,/g, '\\,')
      .replace(/\r?\n/g, '\\n');
  }

  function stamp(date) {
    return date.getUTCFullYear() +
      String(date.getUTCMonth() + 1).padStart(2, '0') +
      String(date.getUTCDate()).padStart(2, '0') + 'T' +
      String(date.getUTCHours()).padStart(2, '0') +
      String(date.getUTCMinutes()).padStart(2, '0') +
      String(date.getUTCSeconds()).padStart(2, '0') + 'Z';
  }

  function dateValue(date) {
    return date.getFullYear() +
      String(date.getMonth() + 1).padStart(2, '0') +
      String(date.getDate()).padStart(2, '0');
  }

  /**
   * A subscribable calendar of every dated window, as yearly-recurring all-day
   * events with a one-day-ahead alarm.
   *
   * This is the only part of the app that can reach you with the phone asleep:
   * your calendar app fires these itself, with no server involved. Weather
   * alerts cannot work this way — they depend on a forecast that does not exist
   * yet — which is why they only appear while the app is open.
   */
  function toIcs(plantsWithProfiles, now) {
    var created = now || new Date();
    var lines = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Koch\'s Tree Nursery Tracker//EN',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
      'X-WR-CALNAME:Tree nursery'
    ];

    plantsWithProfiles.forEach(function (pair) {
      var plant = pair.plant;
      var profile = pair.profile;
      (profile.tasks || []).forEach(function (task) {
        var win = windowFor(task, created.getFullYear());
        // DTEND on an all-day event is exclusive, so add a day to the last one.
        var end = new Date(win.end.getTime() + 1);
        lines.push('BEGIN:VEVENT');
        lines.push('UID:' + plant.id + '-' + task.id + '@koch-nursery');
        lines.push('DTSTAMP:' + stamp(created));
        lines.push('DTSTART;VALUE=DATE:' + dateValue(win.start));
        lines.push('DTEND;VALUE=DATE:' + dateValue(end));
        lines.push('RRULE:FREQ=YEARLY');
        lines.push(fold('SUMMARY:' + escapeText(plant.name + ' — ' + task.title)));
        lines.push(fold('DESCRIPTION:' + escapeText(
          task.body + '\n\n' + profile.name + ' · ' + (profile.source || 'handbook'))));
        lines.push('CATEGORIES:' + escapeText(CATEGORY_LABELS[task.category] || task.category));
        lines.push('BEGIN:VALARM');
        lines.push('TRIGGER:-P1D');
        lines.push('ACTION:DISPLAY');
        lines.push(fold('DESCRIPTION:' + escapeText(plant.name + ' — ' + task.title)));
        lines.push('END:VALARM');
        lines.push('END:VEVENT');
      });
    });

    lines.push('END:VCALENDAR');
    return lines.join('\r\n');
  }

  global.BonsaiCalendar = {
    tasksForPlant: tasksForPlant,
    sortTasks: sortTasks,
    categoryLabels: CATEGORY_LABELS,
    dripOn: dripOn,
    dripSummary: dripSummary,
    backfillDrip: backfillDrip,
    toIcs: toIcs,
    isoDay: isoDay
  };
})(window);

/*
 * Weather watch — forecast lows for the nursery, and the move alerts they drive.
 *
 * Forecast comes from Open-Meteo: free, no API key, and CORS-enabled, which is
 * what makes it usable from a static page with nothing to keep secret. The
 * response is cached so opening the app repeatedly does not re-fetch.
 *
 * ON NOTIFICATIONS, HONESTLY. A static site has no server, so it cannot wake
 * your phone on its own. What this does:
 *
 *   - shows the alert whenever the app is open or opened, and
 *   - raises a real system notification at that moment, if permission is given.
 *
 * What it cannot do is push to a sleeping phone. For the DATE-driven half of
 * the problem — the move windows, pruning, feeding cutoffs — the calendar's
 * .ics export is the honest answer: your phone's own calendar app fires those
 * reminders in the background, for free, with no server anywhere. Weather is
 * the part that genuinely needs the app open, so check it during a cold snap.
 */
(function (global) {
  'use strict';

  var SETTINGS_KEY = 'bonsai.weather.v1';
  var CACHE_KEY = 'bonsai.weatherCache.v1';
  var SEEN_KEY = 'bonsai.weatherSeen.v1';
  var CACHE_MINUTES = 60;
  var FORECAST_DAYS = 14;
  // How far ahead a threatening night counts as "act now".
  var ACTION_HORIZON_DAYS = 7;
  // "Consistently" in the schedule: more than one night, not a single dip.
  var CONSISTENT_NIGHTS = 2;
  var SPRING_STABLE_NIGHTS = 5;

  // Brookeville, Maryland — ZIP 20833, the location both tree handbooks are
  // written for. Editable on the Calendar page.
  var DEFAULT_LOCATION = { latitude: 39.18, longitude: -77.06, label: 'Brookeville, MD (20833)' };

  function readJson(key, fallback) {
    try {
      var raw = global.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function writeJson(key, value) {
    try { global.localStorage.setItem(key, JSON.stringify(value)); } catch (error) { /* ignore */ }
  }

  function settings() {
    var stored = readJson(SETTINGS_KEY, {});
    return {
      latitude: stored.latitude == null ? DEFAULT_LOCATION.latitude : stored.latitude,
      longitude: stored.longitude == null ? DEFAULT_LOCATION.longitude : stored.longitude,
      label: stored.label || DEFAULT_LOCATION.label,
      notify: !!stored.notify,
      endpoint: stored.endpoint || 'https://api.open-meteo.com/v1/forecast'
    };
  }

  function setSettings(next) {
    var merged = settings();
    Object.keys(next || {}).forEach(function (key) { merged[key] = next[key]; });
    writeJson(SETTINGS_KEY, merged);
    writeJson(CACHE_KEY, null);   // location changed: the cache is meaningless
    return merged;
  }

  /* ------------------------------------------------------------- forecast */

  function cached() {
    var entry = readJson(CACHE_KEY, null);
    if (!entry || !entry.fetchedAt || !entry.days) return null;
    if (Date.now() - Date.parse(entry.fetchedAt) > CACHE_MINUTES * 60000) return null;
    return entry;
  }

  function fetchForecast(force) {
    var hit = force ? null : cached();
    if (hit) return Promise.resolve(hit);

    var config = settings();
    var url = config.endpoint +
      '?latitude=' + encodeURIComponent(config.latitude) +
      '&longitude=' + encodeURIComponent(config.longitude) +
      '&daily=temperature_2m_min,temperature_2m_max' +
      '&temperature_unit=fahrenheit&timezone=auto&forecast_days=' + FORECAST_DAYS;

    return global.fetch(url).then(function (response) {
      if (!response.ok) throw new Error('Forecast request failed (HTTP ' + response.status + ')');
      return response.json();
    }).then(function (payload) {
      var daily = payload && payload.daily;
      if (!daily || !daily.time || !daily.temperature_2m_min) {
        throw new Error('The forecast service returned no daily temperatures.');
      }
      var days = daily.time.map(function (date, index) {
        return {
          date: date,
          low: daily.temperature_2m_min[index],
          high: daily.temperature_2m_max[index]
        };
      }).filter(function (day) { return day.low != null; });
      var entry = { fetchedAt: new Date().toISOString(), days: days, timezone: payload.timezone };
      writeJson(CACHE_KEY, entry);
      return entry;
    });
  }

  /* --------------------------------------------------------------- alerts */

  function pad(n) { return String(n).padStart(2, '0'); }

  function monthDay(date) {
    return pad(date.getMonth() + 1) + '-' + pad(date.getDate());
  }

  function dateOf(year, md) {
    var parts = md.split('-');
    return new Date(year, Number(parts[0]) - 1, Number(parts[1]));
  }

  function daysBetween(a, b) {
    return Math.round((b - a) / 86400000);
  }

  function formatDay(iso) {
    return new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  }

  /**
   * Decide what this plant needs, given the forecast. Fall and spring are
   * different problems: in autumn a single cold night can do damage, so the
   * worst night in the horizon rules. In spring the risk is moving too early,
   * so every night in the horizon has to clear the bar.
   */
  function alertFor(profile, forecast, today) {
    var transitions = profile.transitions;
    if (!transitions || !forecast || !forecast.days.length) return null;
    var now = today || new Date();
    var year = now.getFullYear();
    var md = monthDay(now);

    var horizon = forecast.days.slice(0, ACTION_HORIZON_DAYS);
    var lows = horizon.map(function (day) { return day.low; });
    var coldest = horizon.reduce(function (worst, day) {
      return !worst || day.low < worst.low ? day : worst;
    }, null);

    // --- autumn: is it time to come in?
    var fall = transitions.fall;
    var fallStart = dateOf(year, fall.window[0]);
    var fallEnd = dateOf(year, fall.window[1]);
    var fallSeason = md >= '08-01' && md <= '12-31';

    if (fallSeason) {
      if (coldest && coldest.low <= fall.damageLow) {
        return {
          level: 'bad', kind: 'fall',
          title: 'Move indoors now — damaging cold forecast',
          detail: formatDay(coldest.date) + ' is forecast to hit ' + Math.round(coldest.low) +
            ' °F, at or below the ' + fall.damageLow + ' °F damage threshold. Do not wait for the window.',
          coldest: coldest
        };
      }
      var nightsAtRisk = lows.filter(function (low) { return low <= fall.moveAtLow; }).length;
      if (nightsAtRisk >= CONSISTENT_NIGHTS) {
        return {
          level: 'warn', kind: 'fall',
          title: 'Time to move indoors',
          detail: nightsAtRisk + ' of the next ' + horizon.length + ' nights are forecast at or below ' +
            fall.moveAtLow + ' °F. ' + fall.note,
          coldest: coldest
        };
      }
      var daysToWindow = daysBetween(now, fallStart);
      if (daysToWindow >= 0 && daysToWindow <= transitions.acclimationDays) {
        return {
          level: 'warn', kind: 'acclimate',
          title: 'Start the move-in acclimation',
          detail: 'The window opens in ' + daysToWindow + ' days (' + fall.window[0] + ' to ' +
            fall.window[1] + '). Move the pot to a shaded porch or under a canopy for ' +
            transitions.acclimationDays + ' days first, so it adapts to lower light before going inside.',
          coldest: coldest
        };
      }
      if (now > fallEnd && now.getMonth() >= 9) {
        return {
          level: 'bad', kind: 'fall',
          title: 'Move window has passed',
          detail: 'The ' + fall.window[0] + ' to ' + fall.window[1] + ' window closed. Coldest night ahead is ' +
            (coldest ? Math.round(coldest.low) + ' °F on ' + formatDay(coldest.date) : 'unknown') + '.',
          coldest: coldest
        };
      }
    }

    // --- spring: is it safe to go back out?
    var spring = transitions.spring;
    var springStart = dateOf(year, spring.window[0]);
    var springSeason = md >= '02-01' && md <= '06-30';

    if (springSeason) {
      var stable = forecast.days.slice(0, SPRING_STABLE_NIGHTS);
      var tooCold = stable.filter(function (day) { return day.low < spring.moveAboveLow; });
      var daysToSpring = daysBetween(now, springStart);

      if (now >= springStart && !tooCold.length && stable.length) {
        return {
          level: 'good', kind: 'spring',
          title: 'Safe to move outdoors',
          detail: 'All of the next ' + stable.length + ' nights are forecast at or above ' +
            spring.moveAboveLow + ' °F. ' + spring.note,
          coldest: coldest
        };
      }
      if (now >= springStart && tooCold.length) {
        return {
          level: 'warn', kind: 'spring',
          title: 'Hold indoors — cold nights still forecast',
          detail: tooCold.length + ' of the next ' + stable.length + ' nights fall below ' +
            spring.moveAboveLow + ' °F, coldest ' + Math.round(tooCold[0].low) + ' °F on ' +
            formatDay(tooCold[0].date) + '. A cold snap after the move costs more than a late move does.',
          coldest: coldest
        };
      }
      if (daysToSpring >= 0 && daysToSpring <= transitions.acclimationDays) {
        return {
          level: 'warn', kind: 'acclimate',
          title: 'Start the move-out acclimation',
          detail: 'The window opens in ' + daysToSpring + ' days. Put it in a sheltered, shaded spot first and ' +
            'introduce morning sun gradually over a week, or the foliage burns.',
          coldest: coldest
        };
      }
    }

    return null;
  }

  /* -------------------------------------------------------- notifications */

  function canNotify() {
    return typeof global.Notification !== 'undefined';
  }

  function requestPermission() {
    if (!canNotify()) return Promise.resolve('unsupported');
    return global.Notification.requestPermission();
  }

  /**
   * Raise a system notification, but only once per plant per alert per day —
   * the app re-renders constantly and a repeated buzz teaches you to ignore it.
   */
  function notifyOnce(plant, alert) {
    if (!canNotify() || global.Notification.permission !== 'granted') return false;
    if (!settings().notify) return false;
    if (alert.level !== 'bad' && alert.level !== 'warn') return false;

    var today = new Date().toISOString().slice(0, 10);
    var key = plant.id + ':' + alert.title + ':' + today;
    var seen = readJson(SEEN_KEY, {});
    if (seen[key]) return false;
    seen[key] = true;
    writeJson(SEEN_KEY, seen);

    try {
      new global.Notification(plant.name + ' — ' + alert.title, {
        body: alert.detail,
        tag: key
      });
      return true;
    } catch (error) {
      return false;
    }
  }

  global.BonsaiWeather = {
    settings: settings,
    setSettings: setSettings,
    defaultLocation: DEFAULT_LOCATION,
    fetchForecast: fetchForecast,
    cached: cached,
    alertFor: alertFor,
    canNotify: canNotify,
    requestPermission: requestPermission,
    notifyOnce: notifyOnce,
    formatDay: formatDay
  };
})(window);

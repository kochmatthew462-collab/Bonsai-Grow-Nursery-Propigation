/*
 * Optional cloud sync — Cloud Firestore over its REST API.
 *
 * Deliberately no Firebase SDK: the app stays a set of plain files with no
 * build step and no CDN, and if the network is gone the tracker carries on
 * working offline and syncs when it comes back.
 *
 * The whole nursery travels as one JSON string in a single document. That
 * keeps merges atomic and sidesteps Firestore's typed-value encoding and its
 * refusal to store nested arrays. A nursery of a few thousand readings sits
 * far inside the 1 MiB document ceiling; the guard below warns before it does
 * not.
 *
 * Access model: the nursery code IS the key. Anyone holding it can read and
 * write that nursery, exactly like an unguessable share link. Codes are 24
 * characters from a 32-character alphabet (~120 bits), so guessing one is not
 * a practical attack — but treat the code as a password, not as a username.
 */
(function (global) {
  'use strict';

  var CONFIG_KEY = 'bonsai.sync.v1';
  var TOKEN_KEY = 'bonsai.syncToken.v1';
  var CODE_ALPHABET = '23456789abcdefghjkmnpqrstuvwxyz';

  var DEFAULT_AUTH_BASE = 'https://identitytoolkit.googleapis.com';
  var DEFAULT_FIRESTORE_BASE = 'https://firestore.googleapis.com';

  var SIZE_WARN_BYTES = 800 * 1024;   // Firestore's hard ceiling is 1 MiB.
  var POLL_MS = 60000;
  var CHANGE_DEBOUNCE_MS = 2500;

  var listeners = [];
  var state = { level: 'off', message: 'Sync is off.', at: null };
  var busy = false;
  var changeTimer = null;
  var pollTimer = null;

  /* --------------------------------------------------------------- config */

  function readConfig() {
    try {
      var raw = global.localStorage.getItem(CONFIG_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      return {};
    }
  }

  function config() {
    var cfg = readConfig();
    return {
      enabled: !!cfg.enabled,
      projectId: cfg.projectId || '',
      apiKey: cfg.apiKey || '',
      code: cfg.code || '',
      authBase: cfg.authBase || DEFAULT_AUTH_BASE,
      firestoreBase: cfg.firestoreBase || DEFAULT_FIRESTORE_BASE
    };
  }

  function setConfig(next) {
    var merged = config();
    Object.keys(next || {}).forEach(function (key) { merged[key] = next[key]; });
    try {
      global.localStorage.setItem(CONFIG_KEY, JSON.stringify(merged));
    } catch (error) { /* storage full — sync simply stays off */ }
    forgetToken();
    if (!merged.enabled) setStatus('off', 'Sync is off.');
    return merged;
  }

  function isConfigured() {
    var cfg = config();
    return !!(cfg.enabled && cfg.projectId && cfg.apiKey && cfg.code);
  }

  function newCode() {
    var bytes = new Uint8Array(24);
    if (global.crypto && global.crypto.getRandomValues) global.crypto.getRandomValues(bytes);
    else for (var i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    var out = '';
    for (var k = 0; k < bytes.length; k++) out += CODE_ALPHABET[bytes[k] % CODE_ALPHABET.length];
    return out;
  }

  /* --------------------------------------------------------------- status */

  function setStatus(level, message) {
    state = { level: level, message: message, at: new Date().toISOString() };
    listeners.forEach(function (fn) {
      try { fn(state); } catch (error) { /* a bad listener must not stop sync */ }
    });
  }

  function status() { return state; }
  function onStatus(fn) { listeners.push(fn); }

  /* ----------------------------------------------------------------- auth */

  // Anonymous sign-in. It does not identify anyone; it exists so the security
  // rules can require an authenticated caller rather than being wide open.
  function forgetToken() {
    try { global.localStorage.removeItem(TOKEN_KEY); } catch (error) { /* ignore */ }
  }

  function cachedToken() {
    try {
      var raw = global.localStorage.getItem(TOKEN_KEY);
      if (!raw) return null;
      var token = JSON.parse(raw);
      if (!token.idToken || !token.expiresAt) return null;
      if (Date.parse(token.expiresAt) - Date.now() < 60000) return null;
      return token.idToken;
    } catch (error) {
      return null;
    }
  }

  function getToken() {
    var existing = cachedToken();
    if (existing) return Promise.resolve(existing);

    var cfg = config();
    return global.fetch(cfg.authBase + '/v1/accounts:signUp?key=' + encodeURIComponent(cfg.apiKey), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ returnSecureToken: true })
    }).then(function (response) {
      return response.json().then(function (payload) {
        if (!response.ok) {
          var reason = (payload && payload.error && payload.error.message) || ('HTTP ' + response.status);
          if (String(reason).indexOf('ADMIN_ONLY_OPERATION') >= 0 ||
              String(reason).indexOf('OPERATION_NOT_ALLOWED') >= 0) {
            throw new Error('Anonymous sign-in is not enabled for this Firebase project. ' +
              'Turn it on under Authentication → Sign-in method → Anonymous.');
          }
          throw new Error('Sign-in failed: ' + reason);
        }
        var seconds = Number(payload.expiresIn || 3600);
        try {
          global.localStorage.setItem(TOKEN_KEY, JSON.stringify({
            idToken: payload.idToken,
            expiresAt: new Date(Date.now() + seconds * 1000).toISOString()
          }));
        } catch (error) { /* ignore */ }
        return payload.idToken;
      });
    });
  }

  /* ------------------------------------------------------------- document */

  function documentUrl() {
    var cfg = config();
    return cfg.firestoreBase + '/v1/projects/' + encodeURIComponent(cfg.projectId) +
      '/databases/(default)/documents/nurseries/' + encodeURIComponent(cfg.code);
  }

  function fetchRemote(token) {
    return global.fetch(documentUrl(), {
      headers: { Authorization: 'Bearer ' + token }
    }).then(function (response) {
      if (response.status === 404) return null;   // first sync from this code
      return response.json().then(function (payload) {
        if (!response.ok) {
          var reason = (payload && payload.error && payload.error.message) || ('HTTP ' + response.status);
          if (response.status === 403) {
            throw new Error('Firestore refused the read. Check the security rules allow ' +
              'the nurseries collection for signed-in callers.');
          }
          throw new Error('Read failed: ' + reason);
        }
        var raw = payload.fields && payload.fields.data && payload.fields.data.stringValue;
        if (!raw) return null;
        try {
          return JSON.parse(raw);
        } catch (error) {
          throw new Error('The stored nursery is not readable JSON.');
        }
      });
    });
  }

  function pushRemote(token, snapshot) {
    var body = JSON.stringify(snapshot);
    if (body.length > SIZE_WARN_BYTES) {
      throw new Error('This nursery is ' + Math.round(body.length / 1024) + ' KB, close to ' +
        'Firestore\'s 1 MB document limit. Export a backup and trim old readings.');
    }
    return global.fetch(documentUrl(), {
      method: 'PATCH',
      headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fields: {
          data: { stringValue: body },
          updatedAt: { stringValue: new Date().toISOString() }
        }
      })
    }).then(function (response) {
      if (response.ok) return true;
      return response.json().then(function (payload) {
        var reason = (payload && payload.error && payload.error.message) || ('HTTP ' + response.status);
        throw new Error('Write failed: ' + reason);
      });
    });
  }

  /* ---------------------------------------------------------- live sensors */

  /**
   * The Raspberry Pi cabinet monitor writes a small companion document,
   * nurseries/<code>-live, with current readings. Same credentials, same
   * rules; returns null when sync is off or no Pi has ever written it.
   */
  function fetchLive() {
    if (!isConfigured()) return Promise.resolve(null);
    return getToken().then(function (token) {
      return global.fetch(documentUrl() + '-live', {
        headers: { Authorization: 'Bearer ' + token }
      });
    }).then(function (response) {
      if (response.status === 404) return null;
      if (!response.ok) throw new Error('Live read failed (HTTP ' + response.status + ')');
      return response.json().then(function (payload) {
        var raw = payload.fields && payload.fields.data && payload.fields.data.stringValue;
        return raw ? JSON.parse(raw) : null;
      });
    });
  }

  /* ------------------------------------------------------------ the cycle */

  /**
   * Pull, merge, and push back only when the merge actually changed something.
   * Merging before writing is what makes two devices converge rather than
   * clobber each other.
   */
  function syncNow() {
    if (!isConfigured()) {
      setStatus('off', 'Sync is off.');
      return Promise.resolve(state);
    }
    if (busy) return Promise.resolve(state);
    busy = true;
    setStatus('syncing', 'Syncing…');

    var token;
    return getToken()
      .then(function (issued) {
        token = issued;
        return fetchRemote(token);
      })
      .then(function (remote) {
        var before = JSON.stringify(global.BonsaiStore.snapshot());
        if (remote) global.BonsaiStore.mergeSnapshot(remote);
        var after = global.BonsaiStore.snapshot();
        var afterText = JSON.stringify(after);
        var remoteText = remote ? JSON.stringify(remote) : null;

        if (remoteText === afterText) {
          setStatus('ok', 'Up to date.');
          return state;
        }
        return pushRemote(token, after).then(function () {
          setStatus('ok', before === afterText ? 'Uploaded local changes.' : 'Merged and synced.');
          return state;
        });
      })
      .catch(function (error) {
        var offline = typeof navigator !== 'undefined' && navigator.onLine === false;
        setStatus('error', offline
          ? 'Offline — your readings are saved here and will sync when you reconnect.'
          : (error.message || 'Sync failed.'));
        return state;
      })
      .then(function (result) {
        busy = false;
        return result;
      });
  }

  function scheduleFromChange() {
    if (!isConfigured() || busy) return;
    if (changeTimer) clearTimeout(changeTimer);
    changeTimer = setTimeout(function () {
      changeTimer = null;
      syncNow();
    }, CHANGE_DEBOUNCE_MS);
  }

  function start() {
    if (pollTimer) clearInterval(pollTimer);
    if (!isConfigured()) {
      setStatus('off', 'Sync is off.');
      return;
    }
    syncNow();
    pollTimer = setInterval(syncNow, POLL_MS);
    global.addEventListener('online', syncNow);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) syncNow();
    });
    global.BonsaiStore.subscribe(scheduleFromChange);
  }

  global.BonsaiSync = {
    config: config,
    setConfig: setConfig,
    isConfigured: isConfigured,
    newCode: newCode,
    status: status,
    onStatus: onStatus,
    syncNow: syncNow,
    fetchLive: fetchLive,
    start: start
  };
})(window);

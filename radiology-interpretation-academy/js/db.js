/* Radiology Interpretation Academy — storage layer.
   IndexedDB for studies + images (blobs); localStorage for lightweight progress/SRS state. */
window.RIA = window.RIA || {};

RIA.db = (function () {
  var DB_NAME = 'ria-db';
  var DB_VERSION = 1;
  var dbPromise = null;

  function open() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains('studies')) {
          var s = db.createObjectStore('studies', { keyPath: 'id' });
          s.createIndex('createdAt', 'createdAt');
        }
        if (!db.objectStoreNames.contains('images')) {
          var im = db.createObjectStore('images', { keyPath: 'id' });
          im.createIndex('studyId', 'studyId');
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
    return dbPromise;
  }

  function tx(store, mode, fn) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var t = db.transaction(store, mode);
        var os = t.objectStore(store);
        var out = fn(os);
        t.oncomplete = function () { resolve(out && out.__value !== undefined ? out.__value : out); };
        t.onerror = function () { reject(t.error); };
        t.onabort = function () { reject(t.error); };
      });
    });
  }

  function reqToPromise(req) {
    return new Promise(function (resolve, reject) {
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function uid(prefix) {
    return (prefix || 'id') + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  // ——— Studies ———
  function saveStudy(study) {
    if (!study.id) study.id = uid('study');
    if (!study.createdAt) study.createdAt = Date.now();
    study.updatedAt = Date.now();
    return tx('studies', 'readwrite', function (os) { os.put(study); }).then(function () { return study; });
  }

  function getStudy(id) {
    return open().then(function (db) {
      return reqToPromise(db.transaction('studies').objectStore('studies').get(id));
    });
  }

  function listStudies() {
    return open().then(function (db) {
      return reqToPromise(db.transaction('studies').objectStore('studies').getAll());
    }).then(function (rows) {
      rows.sort(function (a, b) { return (b.updatedAt || 0) - (a.updatedAt || 0); });
      return rows;
    });
  }

  function deleteStudy(id) {
    return listImages(id).then(function (imgs) {
      return tx('images', 'readwrite', function (os) {
        imgs.forEach(function (im) { os.delete(im.id); });
      });
    }).then(function () {
      return tx('studies', 'readwrite', function (os) { os.delete(id); });
    });
  }

  // ——— Images ———
  function saveImage(rec) {
    if (!rec.id) rec.id = uid('img');
    return tx('images', 'readwrite', function (os) { os.put(rec); }).then(function () { return rec; });
  }

  function listImages(studyId) {
    return open().then(function (db) {
      var idx = db.transaction('images').objectStore('images').index('studyId');
      return reqToPromise(idx.getAll(studyId));
    }).then(function (rows) {
      rows.sort(function (a, b) { return (a.order || 0) - (b.order || 0) || a.name.localeCompare(b.name); });
      return rows;
    });
  }

  function deleteImage(id) {
    return tx('images', 'readwrite', function (os) { os.delete(id); });
  }

  // ——— localStorage helpers (progress, SRS, prefs, user cards) ———
  var LS_PREFIX = 'ria:';
  function lsGet(key, fallback) {
    try {
      var raw = localStorage.getItem(LS_PREFIX + key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch (e) { return fallback; }
  }
  function lsSet(key, value) {
    try { localStorage.setItem(LS_PREFIX + key, JSON.stringify(value)); } catch (e) { /* storage unavailable */ }
  }

  return {
    uid: uid,
    saveStudy: saveStudy, getStudy: getStudy, listStudies: listStudies, deleteStudy: deleteStudy,
    saveImage: saveImage, listImages: listImages, deleteImage: deleteImage,
    get: lsGet, set: lsSet
  };
})();

/*
 * Photo timeline — the visual progress log.
 *
 * Photos live in their own localStorage key, DELIBERATELY outside the nursery
 * snapshot: the cloud sync ships the whole nursery as one Firestore document
 * with a 1 MiB ceiling, and a single un-shrunk phone photo is 3-5 MiB. So
 * photos stay on the device that took them, downscaled hard, and both the
 * Sync and Backup pages say so. The photo LOG (that a photo was taken, when,
 * of what) is the part a record system actually needs to sync; the pixels are
 * a local luxury.
 *
 * Everything is re-encoded through a canvas to bounded JPEG — which also
 * strips EXIF, so a photo cannot smuggle a GPS position into an export.
 */
(function (global) {
  'use strict';

  var KEY = 'bonsai.photos.v1';
  var MAX_EDGE = 640;          // longest edge after downscale
  var JPEG_QUALITY = 0.72;
  var WARN_BYTES = 3 * 1024 * 1024;
  var MAX_BYTES = 4.5 * 1024 * 1024;   // hard stop before localStorage's ~5 MiB cliff

  function readAll() {
    try {
      var raw = global.localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      return {};
    }
  }

  function writeAll(data) {
    global.localStorage.setItem(KEY, JSON.stringify(data));
  }

  function newId() {
    return 'ph' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  function photosFor(plantId) {
    var list = readAll()[plantId] || [];
    return list.slice().sort(function (a, b) { return b.at.localeCompare(a.at); });
  }

  function totalBytes() {
    var data = readAll();
    var total = 0;
    Object.keys(data).forEach(function (plantId) {
      data[plantId].forEach(function (photo) { total += (photo.data || '').length; });
    });
    return total;
  }

  function downscale(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var image = new Image();
      image.onload = function () {
        try {
          var scale = Math.min(1, MAX_EDGE / Math.max(image.width, image.height));
          var canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(image.width * scale));
          canvas.height = Math.max(1, Math.round(image.height * scale));
          canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
          URL.revokeObjectURL(url);
          resolve(canvas.toDataURL('image/jpeg', JPEG_QUALITY));
        } catch (error) {
          reject(error);
        }
      };
      image.onerror = function () {
        URL.revokeObjectURL(url);
        reject(new Error('That file is not a readable image.'));
      };
      image.src = url;
    });
  }

  function addPhoto(plantId, file, note) {
    return downscale(file).then(function (dataUrl) {
      if (totalBytes() + dataUrl.length > MAX_BYTES) {
        throw new Error('Photo storage is full (~' + Math.round(MAX_BYTES / 1048576) +
          ' MB). Delete old photos first — the log of readings is unaffected.');
      }
      var data = readAll();
      var list = data[plantId] || [];
      list.push({
        id: newId(),
        at: new Date().toISOString(),
        note: (note || '').trim(),
        data: dataUrl
      });
      data[plantId] = list;
      writeAll(data);
      return list[list.length - 1];
    });
  }

  function removePhoto(plantId, photoId) {
    var data = readAll();
    data[plantId] = (data[plantId] || []).filter(function (photo) { return photo.id !== photoId; });
    if (!data[plantId].length) delete data[plantId];
    writeAll(data);
  }

  function removeAllFor(plantId) {
    var data = readAll();
    delete data[plantId];
    writeAll(data);
  }

  global.BonsaiPhotos = {
    photosFor: photosFor,
    addPhoto: addPhoto,
    removePhoto: removePhoto,
    removeAllFor: removeAllFor,
    totalBytes: totalBytes,
    warnBytes: WARN_BYTES,
    maxBytes: MAX_BYTES
  };
})(window);

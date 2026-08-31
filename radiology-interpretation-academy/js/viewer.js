/* Radiology Interpretation Academy — study viewer.
   Stack scroll, zoom/pan, window-level, invert, rotate, annotations.
   Raster images (PNG/JPEG/etc.) via ImageBitmap + canvas filters.
   Uncompressed DICOM via dicomParser (CDN) with true window/level. */
window.RIA = window.RIA || {};

RIA.viewer = (function () {

  // ——— DICOM support ———
  function isDicomBlob(buf) {
    if (buf.byteLength < 132) return false;
    var magic = new Uint8Array(buf, 128, 4);
    return magic[0] === 68 && magic[1] === 73 && magic[2] === 67 && magic[3] === 77; // "DICM"
  }

  function parseDicom(arrayBuffer) {
    if (typeof dicomParser === 'undefined') {
      throw new Error('DICOM support needs the dicomParser library (loads from CDN — check your connection), or export the image as PNG/JPEG.');
    }
    var byteArray = new Uint8Array(arrayBuffer);
    var ds = dicomParser.parseDicom(byteArray);
    var tsn = ds.string('x00020010') || '1.2.840.10008.1.2';
    var uncompressed = ['1.2.840.10008.1.2', '1.2.840.10008.1.2.1', '1.2.840.10008.1.2.1.99'];
    if (uncompressed.indexOf(tsn) === -1) {
      throw new Error('Compressed DICOM (' + tsn + ') is not supported in-browser here. Export as PNG/JPEG or decompress first.');
    }
    var rows = ds.uint16('x00280010'), cols = ds.uint16('x00280011');
    var bits = ds.uint16('x00280100') || 16;
    var signed = ds.uint16('x00280103') === 1;
    var samples = ds.uint16('x00280002') || 1;
    var photo = (ds.string('x00280004') || 'MONOCHROME2').trim();
    var slope = parseFloat(ds.string('x00281053')) || 1;
    var intercept = parseFloat(ds.string('x00281052')) || 0;
    var wc = parseFloat((ds.string('x00281050') || '').split('\\')[0]);
    var ww = parseFloat((ds.string('x00281051') || '').split('\\')[0]);
    var pixelEl = ds.elements.x7fe00010;
    if (!pixelEl || !rows || !cols) throw new Error('No image pixel data found in this DICOM file.');

    var pixels;
    if (samples === 3 && bits === 8) {
      pixels = new Uint8Array(ds.byteArray.buffer, pixelEl.dataOffset, rows * cols * 3);
    } else if (bits <= 8) {
      pixels = new Uint8Array(ds.byteArray.buffer, pixelEl.dataOffset, rows * cols);
    } else if (signed) {
      pixels = new Int16Array(ds.byteArray.buffer, pixelEl.dataOffset, rows * cols);
    } else {
      pixels = new Uint16Array(ds.byteArray.buffer, pixelEl.dataOffset, rows * cols);
    }

    // Default window from data if header lacks one
    if (!isFinite(wc) || !isFinite(ww) || ww <= 0) {
      var mn = Infinity, mx = -Infinity;
      var step = Math.max(1, Math.floor(pixels.length / 50000));
      for (var i = 0; i < pixels.length; i += step) {
        var v = pixels[i] * slope + intercept;
        if (v < mn) mn = v;
        if (v > mx) mx = v;
      }
      wc = (mn + mx) / 2;
      ww = Math.max(1, mx - mn);
    }

    return {
      rows: rows, cols: cols, pixels: pixels, samples: samples,
      photo: photo, slope: slope, intercept: intercept,
      defaultWC: wc, defaultWW: ww,
      modality: (ds.string('x00080060') || '').trim(),
      desc: (ds.string('x0008103e') || ds.string('x00081030') || '').trim()
    };
  }

  function renderDicomToCanvas(d, wc, ww) {
    var c = document.createElement('canvas');
    c.width = d.cols; c.height = d.rows;
    var ctx = c.getContext('2d');
    var img = ctx.createImageData(d.cols, d.rows);
    var out = img.data;
    var n = d.rows * d.cols;
    if (d.samples === 3) {
      for (var i = 0; i < n; i++) {
        out[i * 4] = d.pixels[i * 3];
        out[i * 4 + 1] = d.pixels[i * 3 + 1];
        out[i * 4 + 2] = d.pixels[i * 3 + 2];
        out[i * 4 + 3] = 255;
      }
    } else {
      var lo = wc - 0.5 - (ww - 1) / 2;
      var scale = 255 / Math.max(1, ww - 1);
      var mono1 = d.photo === 'MONOCHROME1';
      for (var j = 0; j < n; j++) {
        var v = (d.pixels[j] * d.slope + d.intercept - lo) * scale;
        v = v < 0 ? 0 : (v > 255 ? 255 : v);
        if (mono1) v = 255 - v;
        out[j * 4] = out[j * 4 + 1] = out[j * 4 + 2] = v;
        out[j * 4 + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return c;
  }

  // ——— Viewer factory ———
  // opts: { container, images: [{id, name, blob, isDicom}], annotations, onAnnotationsChange }
  function create(opts) {
    var state = {
      idx: 0, zoom: 1, panX: 0, panY: 0, rot: 0, invert: false,
      bright: 100, contrast: 100,          // raster W/L via filters (percent)
      wc: null, ww: null,                  // dicom true window
      tool: 'pan',                          // pan | wl | annotate
      showAnnotations: true
    };
    var cache = {};   // imageId -> { bitmap } | { dicom, rendered, key } | { error }
    var container = opts.container;
    container.classList.add('viewer');
    container.innerHTML =
      '<div class="viewer-toolbar" role="toolbar">' +
        '<button data-act="prev" title="Previous image (←/↑ or wheel)">◀</button>' +
        '<span class="viewer-count">–</span>' +
        '<button data-act="next" title="Next image (→/↓ or wheel)">▶</button>' +
        '<span class="viewer-sep"></span>' +
        '<button data-act="tool-pan" title="Pan tool (drag to move)" class="tool-on">✋ Pan</button>' +
        '<button data-act="tool-wl" title="Window/level tool (drag: ↔ width/contrast, ↕ level/brightness)">🌓 W/L</button>' +
        '<button data-act="tool-annotate" title="Annotation tool (click image to add a numbered note)">📍 Note</button>' +
        '<span class="viewer-sep"></span>' +
        '<button data-act="zin" title="Zoom in (Ctrl+wheel)">＋</button>' +
        '<button data-act="zout" title="Zoom out">－</button>' +
        '<button data-act="invert" title="Invert greyscale (I)">◐</button>' +
        '<button data-act="rotate" title="Rotate 90°">⟳</button>' +
        '<button data-act="toggle-ann" title="Show/hide annotations">👁</button>' +
        '<button data-act="reset" title="Reset view (R)">Reset</button>' +
        '<span class="viewer-info"></span>' +
      '</div>' +
      '<div class="viewer-stage"><canvas></canvas><div class="viewer-msg" hidden></div></div>' +
      '<input class="viewer-slider" type="range" min="0" max="0" value="0" title="Stack scroll">';

    var canvas = container.querySelector('canvas');
    var ctx = canvas.getContext('2d');
    var stage = container.querySelector('.viewer-stage');
    var msgEl = container.querySelector('.viewer-msg');
    var slider = container.querySelector('.viewer-slider');
    var infoEl = container.querySelector('.viewer-info');
    var countEl = container.querySelector('.viewer-count');

    function images() { return opts.images; }
    function current() { return images()[state.idx]; }

    function setMsg(text) {
      msgEl.hidden = !text;
      msgEl.textContent = text || '';
    }

    function loadCurrent() {
      var im = current();
      if (!im) { setMsg('No images in this study yet — add some above.'); draw(); return; }
      var c = cache[im.id];
      if (c) { draw(); return; }
      cache[im.id] = { loading: true };
      setMsg('Loading…');
      im.blob.arrayBuffer().then(function (buf) {
        if (im.isDicom || isDicomBlob(buf)) {
          try {
            var d = parseDicom(buf);
            cache[im.id] = { dicom: d };
            if (state.wc === null) { state.wc = d.defaultWC; state.ww = d.defaultWW; }
          } catch (e) {
            cache[im.id] = { error: e.message };
          }
          setMsg('');
          draw();
        } else {
          createImageBitmap(new Blob([buf])).then(function (bmp) {
            cache[im.id] = { bitmap: bmp };
            setMsg('');
            draw();
          }).catch(function () {
            cache[im.id] = { error: 'Could not decode this file as an image.' };
            setMsg('');
            draw();
          });
        }
      });
    }

    function sourceCanvasFor(im) {
      var c = cache[im.id];
      if (!c) return null;
      if (c.bitmap) return c.bitmap;
      if (c.dicom) {
        var wc = state.wc !== null ? state.wc : c.dicom.defaultWC;
        var ww = state.ww !== null ? state.ww : c.dicom.defaultWW;
        var key = Math.round(wc) + ':' + Math.round(ww);
        if (c.key !== key) {
          c.rendered = renderDicomToCanvas(c.dicom, wc, ww);
          c.key = key;
        }
        return c.rendered;
      }
      return null;
    }

    function fitScale(w, h) {
      var quarter = state.rot % 2 === 1;
      var iw = quarter ? h : w, ih = quarter ? w : h;
      return Math.min(stage.clientWidth / iw, stage.clientHeight / ih) * 0.98;
    }

    function draw() {
      var dpr = window.devicePixelRatio || 1;
      var W = stage.clientWidth, H = stage.clientHeight;
      if (canvas.width !== W * dpr || canvas.height !== H * dpr) {
        canvas.width = W * dpr; canvas.height = H * dpr;
        canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, W, H);

      var im = current();
      countEl.textContent = images().length ? (state.idx + 1) + ' / ' + images().length : '0 / 0';
      slider.max = Math.max(0, images().length - 1);
      slider.value = state.idx;
      if (!im) { infoEl.textContent = ''; return; }

      var c = cache[im.id];
      if (c && c.error) { setMsg(c.error); infoEl.textContent = im.name; return; }
      var src = sourceCanvasFor(im);
      if (!src) return;

      var iw = src.width, ih = src.height;
      var base = fitScale(iw, ih);
      var scale = base * state.zoom;

      ctx.save();
      ctx.translate(W / 2 + state.panX, H / 2 + state.panY);
      ctx.rotate(state.rot * Math.PI / 2);
      ctx.scale(scale, scale);
      var filters = [];
      if (c.bitmap) {
        if (state.bright !== 100) filters.push('brightness(' + state.bright + '%)');
        if (state.contrast !== 100) filters.push('contrast(' + state.contrast + '%)');
      }
      if (state.invert) filters.push('invert(1)');
      ctx.filter = filters.length ? filters.join(' ') : 'none';
      ctx.imageSmoothingEnabled = scale < 2; // pixel-peep at high zoom
      ctx.drawImage(src, -iw / 2, -ih / 2);
      ctx.restore();

      drawAnnotations(im, W, H, iw, ih, scale);

      var parts = [im.name];
      if (c.dicom) {
        if (c.dicom.modality) parts.push(c.dicom.modality);
        parts.push('WC ' + Math.round(state.wc !== null ? state.wc : c.dicom.defaultWC) +
                   ' / WW ' + Math.round(state.ww !== null ? state.ww : c.dicom.defaultWW));
      }
      parts.push('zoom ' + state.zoom.toFixed(1) + '×');
      infoEl.textContent = parts.join(' · ');
    }

    function imageToScreen(im, ix, iy, W, H, iw, ih, scale) {
      var x = (ix - 0.5) * iw * scale, y = (iy - 0.5) * ih * scale;
      var a = state.rot * Math.PI / 2;
      var rx = x * Math.cos(a) - y * Math.sin(a);
      var ry = x * Math.sin(a) + y * Math.cos(a);
      return { x: W / 2 + state.panX + rx, y: H / 2 + state.panY + ry };
    }

    function screenToImage(sx, sy) {
      var im = current(); if (!im) return null;
      var src = sourceCanvasFor(im); if (!src) return null;
      var W = stage.clientWidth, H = stage.clientHeight;
      var iw = src.width, ih = src.height;
      var scale = fitScale(iw, ih) * state.zoom;
      var x = sx - W / 2 - state.panX, y = sy - H / 2 - state.panY;
      var a = -state.rot * Math.PI / 2;
      var rx = x * Math.cos(a) - y * Math.sin(a);
      var ry = x * Math.sin(a) + y * Math.cos(a);
      return { x: rx / (iw * scale) + 0.5, y: ry / (ih * scale) + 0.5 };
    }

    function annots(im) {
      var all = opts.annotations || {};
      return all[im.id] || [];
    }

    function drawAnnotations(im, W, H, iw, ih, scale) {
      if (!state.showAnnotations) return;
      var list = annots(im);
      list.forEach(function (m, i) {
        var p = imageToScreen(im, m.x, m.y, W, H, iw, ih, scale);
        ctx.save();
        ctx.beginPath();
        ctx.arc(p.x, p.y, 11, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 196, 0, 0.9)';
        ctx.fill();
        ctx.fillStyle = '#1a1a1a';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(String(i + 1), p.x, p.y + 0.5);
        ctx.restore();
      });
    }

    // ——— interactions ———
    function setIdx(i) {
      var n = images().length;
      if (!n) return;
      state.idx = Math.max(0, Math.min(n - 1, i));
      setMsg('');
      loadCurrent();
    }

    stage.addEventListener('wheel', function (e) {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        state.zoom = Math.max(0.2, Math.min(20, state.zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
        draw();
      } else {
        setIdx(state.idx + (e.deltaY > 0 ? 1 : -1));
      }
    }, { passive: false });

    var drag = null;
    stage.addEventListener('pointerdown', function (e) {
      if (e.button === 2) { drag = { mode: 'wl', x: e.clientX, y: e.clientY }; }
      else if (state.tool === 'annotate') { handleAnnotateClick(e); return; }
      else drag = { mode: state.tool === 'wl' ? 'wl' : 'pan', x: e.clientX, y: e.clientY };
      stage.setPointerCapture(e.pointerId);
    });
    stage.addEventListener('contextmenu', function (e) { e.preventDefault(); });
    stage.addEventListener('pointermove', function (e) {
      if (!drag) return;
      var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      drag.x = e.clientX; drag.y = e.clientY;
      if (drag.mode === 'pan') {
        state.panX += dx; state.panY += dy;
      } else {
        var im = current();
        var c = im && cache[im.id];
        if (c && c.dicom) {
          var wwNow = state.ww !== null ? state.ww : c.dicom.defaultWW;
          state.ww = Math.max(1, wwNow + dx * Math.max(1, wwNow / 200));
          var wcNow = state.wc !== null ? state.wc : c.dicom.defaultWC;
          state.wc = wcNow + dy * Math.max(1, wwNow / 400);
        } else {
          state.contrast = Math.max(10, Math.min(400, state.contrast + dx * 0.5));
          state.bright = Math.max(10, Math.min(400, state.bright - dy * 0.5));
        }
      }
      draw();
    });
    stage.addEventListener('pointerup', function () { drag = null; });

    function handleAnnotateClick(e) {
      var rect = stage.getBoundingClientRect();
      var pt = screenToImage(e.clientX - rect.left, e.clientY - rect.top);
      var im = current();
      if (!pt || !im || pt.x < 0 || pt.x > 1 || pt.y < 0 || pt.y > 1) return;
      var list = annots(im).slice();
      // Clicking near an existing marker offers deletion
      for (var i = 0; i < list.length; i++) {
        if (Math.abs(list[i].x - pt.x) < 0.02 && Math.abs(list[i].y - pt.y) < 0.02) {
          if (confirm('Delete note ' + (i + 1) + ': "' + list[i].text + '"?')) {
            list.splice(i, 1);
            commitAnnotations(im, list);
          }
          return;
        }
      }
      var text = prompt('Annotation for marker ' + (list.length + 1) + ':');
      if (text === null) return;
      list.push({ x: pt.x, y: pt.y, text: text.trim() });
      commitAnnotations(im, list);
    }

    function commitAnnotations(im, list) {
      opts.annotations = opts.annotations || {};
      opts.annotations[im.id] = list;
      if (opts.onAnnotationsChange) opts.onAnnotationsChange(opts.annotations);
      draw();
    }

    slider.addEventListener('input', function () { setIdx(parseInt(slider.value, 10)); });

    container.querySelector('.viewer-toolbar').addEventListener('click', function (e) {
      var btn = e.target.closest('button');
      if (!btn) return;
      var act = btn.dataset.act;
      if (act === 'prev') setIdx(state.idx - 1);
      else if (act === 'next') setIdx(state.idx + 1);
      else if (act === 'zin') { state.zoom = Math.min(20, state.zoom * 1.25); draw(); }
      else if (act === 'zout') { state.zoom = Math.max(0.2, state.zoom / 1.25); draw(); }
      else if (act === 'invert') { state.invert = !state.invert; draw(); }
      else if (act === 'rotate') { state.rot = (state.rot + 1) % 4; draw(); }
      else if (act === 'toggle-ann') { state.showAnnotations = !state.showAnnotations; draw(); }
      else if (act === 'reset') {
        state.zoom = 1; state.panX = 0; state.panY = 0; state.rot = 0; state.invert = false;
        state.bright = 100; state.contrast = 100; state.wc = null; state.ww = null;
        draw();
      }
      else if (act && act.indexOf('tool-') === 0) {
        state.tool = act.slice(5);
        container.querySelectorAll('.viewer-toolbar button').forEach(function (b) {
          b.classList.toggle('tool-on', b.dataset.act === act);
        });
        stage.style.cursor = state.tool === 'annotate' ? 'crosshair' : (state.tool === 'wl' ? 'ns-resize' : 'grab');
      }
    });

    function onKey(e) {
      if (e.target.matches('input, textarea, select')) return;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); setIdx(state.idx + 1); }
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); setIdx(state.idx - 1); }
      else if (e.key === 'i' || e.key === 'I') { state.invert = !state.invert; draw(); }
      else if (e.key === 'r' || e.key === 'R') { state.zoom = 1; state.panX = 0; state.panY = 0; state.bright = 100; state.contrast = 100; state.wc = null; state.ww = null; draw(); }
      else if (e.key === '+' || e.key === '=') { state.zoom = Math.min(20, state.zoom * 1.25); draw(); }
      else if (e.key === '-') { state.zoom = Math.max(0.2, state.zoom / 1.25); draw(); }
    }
    document.addEventListener('keydown', onKey);

    var ro = new ResizeObserver(function () { draw(); });
    ro.observe(stage);

    loadCurrent();

    return {
      refresh: function (imgs) { opts.images = imgs; state.idx = Math.min(state.idx, Math.max(0, imgs.length - 1)); loadCurrent(); },
      destroy: function () {
        document.removeEventListener('keydown', onKey);
        ro.disconnect();
        Object.keys(cache).forEach(function (k) { if (cache[k].bitmap) cache[k].bitmap.close(); });
      }
    };
  }

  return { create: create, isDicomBlob: isDicomBlob };
})();

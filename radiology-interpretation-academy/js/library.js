/* Radiology Interpretation Academy — personal study library.
   Create studies, upload image series (PNG/JPEG/uncompressed DICOM), view, annotate, and write reports.
   Everything is stored locally in your browser (IndexedDB) — nothing is uploaded anywhere. */
window.RIA = window.RIA || {};

RIA.library = (function () {
  var esc = function (s) { return RIA.ui.esc(s); };

  var MODALITIES = ['XR', 'CT', 'MRI', 'US', 'Fluoro', 'NM/PET', 'Mammo', 'Other'];
  var REGIONS = ['Neuro', 'Head & Neck', 'Spine', 'Chest', 'Cardiac', 'Abdomen', 'Pelvis', 'MSK Upper', 'MSK Lower', 'Whole body', 'Other'];
  var AGES = ['Neonate', 'Infant', 'Child', 'Adolescent', 'Adult', 'Older adult'];

  function selectOpts(list, sel) {
    return list.map(function (v) {
      return '<option' + (v === sel ? ' selected' : '') + '>' + esc(v) + '</option>';
    }).join('');
  }

  // ——— List view ———
  function renderList(el) {
    RIA.db.listStudies().then(function (studies) {
      var cards = studies.map(function (s) {
        return '<a class="card study-card" href="#/study/' + esc(s.id) + '">' +
          '<div class="card-title">' + esc(s.title || 'Untitled study') + '</div>' +
          '<div class="card-meta">' +
            RIA.ui.chip(s.modality || '—') + RIA.ui.chip(s.region || '—') + RIA.ui.chip(s.ageGroup || '—') +
          '</div>' +
          (s.diagnosis ? '<div class="card-sub">Dx: ' + esc(s.diagnosis) + '</div>' : '') +
          '<div class="card-sub dim">' + RIA.ui.fmtDate(s.updatedAt) + '</div>' +
        '</a>';
      }).join('');

      el.innerHTML =
        '<header class="page-head"><h1>📁 My Study Library</h1>' +
        '<p>Your personal teaching-file: upload anonymized images or DICOM series, annotate findings, and practice writing structured reports. ' +
        '<strong>Everything stays in this browser</strong> — nothing is uploaded to any server. ' +
        '<em>Never store images containing patient-identifiable information.</em></p></header>' +
        '<div class="panel"><h2>New study</h2>' +
        '<form id="new-study" class="form-grid">' +
          '<label>Title<input name="title" required placeholder="e.g., Adult CXR — RML pneumonia teaching case"></label>' +
          '<label>Modality<select name="modality">' + selectOpts(MODALITIES) + '</select></label>' +
          '<label>Region<select name="region">' + selectOpts(REGIONS) + '</select></label>' +
          '<label>Age group<select name="ageGroup">' + selectOpts(AGES, 'Adult') + '</select></label>' +
          '<label class="span2">Clinical history<input name="history" placeholder="e.g., 62M, fever and productive cough"></label>' +
          '<button class="btn primary" type="submit">Create study</button>' +
        '</form></div>' +
        '<h2>Studies (' + studies.length + ')</h2>' +
        (cards ? '<div class="card-grid">' + cards + '</div>'
               : '<p class="dim">No studies yet. Create one above, then add images inside it.</p>');

      el.querySelector('#new-study').addEventListener('submit', function (e) {
        e.preventDefault();
        var f = e.target;
        RIA.db.saveStudy({
          title: f.title.value.trim(),
          modality: f.modality.value, region: f.region.value, ageGroup: f.ageGroup.value,
          history: f.history.value.trim(),
          findings: '', impression: '', diagnosis: '', teachingPoints: '', annotations: {}
        }).then(function (s) { location.hash = '#/study/' + s.id; });
      });
    });
  }

  // ——— Study/viewer view ———
  var activeViewer = null;

  function destroyViewer() {
    if (activeViewer) { activeViewer.destroy(); activeViewer = null; }
  }

  function renderStudy(el, id) {
    Promise.all([RIA.db.getStudy(id), RIA.db.listImages(id)]).then(function (res) {
      var study = res[0], images = res[1];
      if (!study) { el.innerHTML = '<p>Study not found. <a href="#/library">Back to library</a></p>'; return; }

      el.innerHTML =
        '<header class="page-head study-head">' +
          '<a class="crumb" href="#/library">← Library</a>' +
          '<h1 id="study-title-h">' + esc(study.title || 'Untitled study') + '</h1>' +
          '<div>' + RIA.ui.chip(study.modality) + RIA.ui.chip(study.region) + RIA.ui.chip(study.ageGroup) + '</div>' +
        '</header>' +
        '<div class="study-layout">' +
          '<div class="study-viewer-col">' +
            '<div id="viewer-host"></div>' +
            '<div class="panel">' +
              '<div class="row-between"><h2>Images (' + images.length + ')</h2>' +
              '<label class="btn small">＋ Add images<input id="img-upload" type="file" multiple accept="image/*,.dcm,application/dicom" hidden></label></div>' +
              '<p class="dim small">PNG/JPEG and uncompressed DICOM (.dcm). Files are sorted by name — number them (01, 02…) for ordered stacks. Wheel = stack scroll · Ctrl+wheel = zoom · drag = pan · right-drag or W/L tool = window/level.</p>' +
              '<ul id="img-list" class="img-list"></ul>' +
            '</div>' +
          '</div>' +
          '<div class="study-report-col">' +
            '<div class="panel"><h2>Structured report practice</h2>' +
              '<label>Clinical history<textarea id="f-history" rows="2">' + esc(study.history) + '</textarea></label>' +
              '<label>Findings<textarea id="f-findings" rows="7" placeholder="Systematic, organ-by-organ…">' + esc(study.findings) + '</textarea></label>' +
              '<label>Impression<textarea id="f-impression" rows="3" placeholder="Numbered, most important first, answers the question…">' + esc(study.impression) + '</textarea></label>' +
              '<label>Final diagnosis<input id="f-diagnosis" value="' + esc(study.diagnosis) + '" placeholder="Revealed answer / gold standard"></label>' +
              '<label>Teaching points<textarea id="f-teaching" rows="4" placeholder="What should you remember from this case?">' + esc(study.teachingPoints) + '</textarea></label>' +
              '<div class="row-between"><span class="dim small" id="save-state">Saved</span>' +
              '<button id="del-study" class="btn danger small">Delete study</button></div>' +
            '</div>' +
            '<div class="panel"><h2>Annotations on current image set</h2><div id="ann-summary" class="dim small"></div></div>' +
          '</div>' +
        '</div>';

      // Viewer
      var host = el.querySelector('#viewer-host');
      destroyViewer();
      activeViewer = RIA.viewer.create({
        container: host,
        images: images,
        annotations: study.annotations || {},
        onAnnotationsChange: function (ann) {
          study.annotations = ann;
          scheduleSave();
          renderAnnSummary();
        }
      });

      function renderAnnSummary() {
        var ann = study.annotations || {};
        var html = images.map(function (im) {
          var list = ann[im.id] || [];
          if (!list.length) return '';
          return '<div><strong>' + esc(im.name) + '</strong><ol>' +
            list.map(function (m) { return '<li>' + esc(m.text || '(no text)') + '</li>'; }).join('') +
            '</ol></div>';
        }).join('');
        el.querySelector('#ann-summary').innerHTML = html || 'No annotations yet — use the 📍 Note tool in the viewer.';
      }

      function renderImgList() {
        var ul = el.querySelector('#img-list');
        ul.innerHTML = images.map(function (im, i) {
          return '<li><span>' + (i + 1) + '. ' + esc(im.name) + (im.isDicom ? ' <span class="chip">DICOM</span>' : '') + '</span>' +
            '<button class="btn tiny danger" data-del="' + esc(im.id) + '">✕</button></li>';
        }).join('') || '<li class="dim">No images yet.</li>';
      }
      renderImgList();
      renderAnnSummary();

      // Upload
      el.querySelector('#img-upload').addEventListener('change', function (e) {
        var files = Array.prototype.slice.call(e.target.files);
        if (!files.length) return;
        var order = images.length;
        var chain = Promise.resolve();
        files.sort(function (a, b) { return a.name.localeCompare(b.name, undefined, { numeric: true }); });
        files.forEach(function (file) {
          chain = chain.then(function () {
            return file.arrayBuffer().then(function (buf) {
              var isDcm = RIA.viewer.isDicomBlob(buf) || /\.dcm$/i.test(file.name);
              return RIA.db.saveImage({
                studyId: id, name: file.name, order: order++,
                isDicom: isDcm, blob: new Blob([buf], { type: file.type || 'application/octet-stream' })
              });
            });
          });
        });
        chain.then(function () {
          RIA.ui.toast(files.length + ' image(s) added');
          renderStudy(el, id); // re-render with fresh image list
        });
      });

      // Delete image
      el.querySelector('#img-list').addEventListener('click', function (e) {
        var btn = e.target.closest('button[data-del]');
        if (!btn) return;
        if (!confirm('Remove this image from the study?')) return;
        RIA.db.deleteImage(btn.dataset.del).then(function () { renderStudy(el, id); });
      });

      // Report autosave
      var saveTimer = null;
      function scheduleSave() {
        el.querySelector('#save-state').textContent = 'Saving…';
        clearTimeout(saveTimer);
        saveTimer = setTimeout(function () {
          study.history = el.querySelector('#f-history').value;
          study.findings = el.querySelector('#f-findings').value;
          study.impression = el.querySelector('#f-impression').value;
          study.diagnosis = el.querySelector('#f-diagnosis').value;
          study.teachingPoints = el.querySelector('#f-teaching').value;
          RIA.db.saveStudy(study).then(function () {
            var st = el.querySelector('#save-state');
            if (st) st.textContent = 'Saved';
          });
        }, 600);
      }
      ['#f-history', '#f-findings', '#f-impression', '#f-diagnosis', '#f-teaching'].forEach(function (sel) {
        el.querySelector(sel).addEventListener('input', scheduleSave);
      });

      el.querySelector('#del-study').addEventListener('click', function () {
        if (!confirm('Delete this study and all its images? This cannot be undone.')) return;
        RIA.db.deleteStudy(id).then(function () { location.hash = '#/library'; });
      });
    });
  }

  return { renderList: renderList, renderStudy: renderStudy, destroyViewer: destroyViewer };
})();

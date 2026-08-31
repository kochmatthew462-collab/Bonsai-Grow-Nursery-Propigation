/* Radiology Interpretation Academy — shell, router, and content views. */
window.RIA = window.RIA || {};

RIA.app = (function () {
  var esc = function (s) { return RIA.ui.esc(s); };
  var main;

  // ——— progress helpers ———
  function readSet() { return RIA.db.get('readItems', {}); }
  function markRead(key, val) {
    var r = readSet();
    if (val) r[key] = Date.now(); else delete r[key];
    RIA.db.set('readItems', r);
  }
  function isRead(key) { return !!readSet()[key]; }

  function completeButton(key) {
    var read = isRead(key);
    return '<button class="btn ' + (read ? '' : 'primary') + '" data-complete="' + esc(key) + '">' +
      (read ? '✓ Completed — mark unread' : 'Mark as completed') + '</button>';
  }
  function wireComplete(el, rerender) {
    var btn = el.querySelector('[data-complete]');
    if (!btn) return;
    btn.addEventListener('click', function () {
      markRead(btn.dataset.complete, !isRead(btn.dataset.complete));
      RIA.ui.toast('Progress updated');
      rerender();
    });
  }

  // ——— Dashboard ———
  function viewHome(el) {
    var learnTotal = RIA.data.modalities.length + RIA.data.approaches.length + RIA.data.anatomy.length;
    var read = readSet();
    var learnDone = Object.keys(read).length;
    var due = RIA.srs.dueCards().length;
    var scores = RIA.db.get('quizScores', {});
    var quizzesTaken = Object.keys(scores).length;
    var sign = RIA.data.signs[Math.floor((Date.now() / 86400000)) % RIA.data.signs.length];

    RIA.db.listStudies().then(function (studies) {
      el.innerHTML =
        '<header class="page-head"><h1>🩻 Radiology Interpretation Academy</h1>' +
        '<p>A self-study curriculum for interpreting radiologic imaging — every major modality, adult and pediatric, ' +
        'from physics to systematic search patterns to structured reporting.</p></header>' +

        '<div class="stat-row">' +
          '<a class="stat" href="#/learn"><div class="stat-num">' + learnDone + '<span class="dim">/' + learnTotal + '</span></div><div class="stat-lbl">curriculum items completed</div></a>' +
          '<a class="stat" href="#/flashcards"><div class="stat-num">' + due + '</div><div class="stat-lbl">flashcards due</div></a>' +
          '<a class="stat" href="#/quiz"><div class="stat-num">' + quizzesTaken + '<span class="dim">/' + RIA.data.quizzes.length + '</span></div><div class="stat-lbl">quizzes attempted</div></a>' +
          '<a class="stat" href="#/library"><div class="stat-num">' + studies.length + '</div><div class="stat-lbl">studies in your library</div></a>' +
        '</div>' +

        '<div class="home-grid">' +
          '<a class="card big" href="#/learn"><div class="card-title">📚 Modalities</div><div class="card-sub">How X-ray, CT, MRI, US, PET & more make images — and how to read each one\'s language: densities, HU, sequences, echogenicity, tracers.</div></a>' +
          '<a class="card big" href="#/approach"><div class="card-title">🧭 Systematic Approaches</div><div class="card-sub">Interactive checklists for CXR, head CT, CT abdomen, MRI brain, MSK trauma and more — plus reporting and cognitive-error training.</div></a>' +
          '<a class="card big" href="#/anatomy"><div class="card-title">🗺️ Radiologic Anatomy</div><div class="card-sub">Region-by-region imaging anatomy with adult and pediatric norms, variants, and diagrams.</div></a>' +
          '<a class="card big" href="#/library"><div class="card-title">📁 My Study Library</div><div class="card-sub">Hold your own images & DICOM series, view PACS-style, annotate findings, and practice writing reports.</div></a>' +
          '<a class="card big" href="#/flashcards"><div class="card-title">🃏 Flashcards</div><div class="card-sub">Spaced repetition for signs, measurements, and anatomy — add your own cards.</div></a>' +
          '<a class="card big" href="#/quiz"><div class="card-title">❓ Quizzes</div><div class="card-sub">Case-style questions with explanations across all systems.</div></a>' +
          '<a class="card big" href="#/signs"><div class="card-title">💡 Classic Signs</div><div class="card-sub">Searchable glossary of named signs, from air bronchograms to the whirlpool sign.</div></a>' +
          '<a class="card big" href="#/measurements"><div class="card-title">📏 Normal Measurements</div><div class="card-sub">Adult and pediatric reference values and dose context.</div></a>' +
        '</div>' +

        '<div class="panel"><h2>💡 Sign of the day</h2>' +
        '<p><strong>' + esc(sign.name) + '</strong> <span class="chip">' + esc(sign.modality) + '</span> <span class="chip">' + esc(sign.region) + '</span></p>' +
        '<p>' + esc(sign.desc) + '</p><p class="dim">' + esc(sign.means) + '</p>' +
        '<a href="#/signs">Browse all signs →</a></div>' +

        '<div class="panel dim small"><p><strong>Disclaimer:</strong> This is a personal education tool. It is not medical advice, ' +
        'not a diagnostic device, and no substitute for formal training, supervision, or clinical judgment. ' +
        'Store only anonymized images — never patient-identifiable data.</p></div>';
    });
  }

  // ——— Learn (modalities) ———
  function viewLearnList(el) {
    el.innerHTML =
      '<header class="page-head"><h1>📚 Modalities</h1>' +
      '<p>Each module covers how the modality works, how to read its grammar, artifacts, safety, and pediatric differences.</p></header>' +
      '<div class="card-grid">' +
      RIA.data.modalities.map(function (m) {
        return '<a class="card" href="#/learn/' + m.id + '">' +
          '<div class="card-title">' + m.icon + ' ' + esc(m.name) + (isRead('mod:' + m.id) ? ' <span class="done">✓</span>' : '') + '</div>' +
          '<div class="card-sub">' + esc(m.tagline) + '</div></a>';
      }).join('') + '</div>';
  }

  function viewLearnDetail(el, id) {
    var m = RIA.data.modalities.find(function (x) { return x.id === id; });
    if (!m) { el.innerHTML = '<p>Not found. <a href="#/learn">Back</a></p>'; return; }
    el.innerHTML =
      '<header class="page-head"><a class="crumb" href="#/learn">← Modalities</a>' +
      '<h1>' + m.icon + ' ' + esc(m.name) + '</h1><p>' + esc(m.tagline) + '</p></header>' +
      m.sections.map(function (s) {
        return '<section class="panel"><h2>' + esc(s.h) + '</h2>' + s.body + '</section>';
      }).join('') +
      (m.peds ? '<section class="panel peds-callout"><h2>🧸 Pediatric considerations</h2>' + m.peds + '</section>' : '') +
      '<section class="panel keypoints"><h2>🔑 Key points</h2><ul>' +
        m.keyPoints.map(function (k) { return '<li>' + esc(k) + '</li>'; }).join('') +
      '</ul></section>' +
      '<div class="row-center">' + completeButton('mod:' + m.id) + '</div>';
    wireComplete(el, function () { viewLearnDetail(el, id); });
  }

  // ——— Approaches ———
  function viewApproachList(el) {
    var scopeChip = { adult: '<span class="chip">Adult</span>', peds: '<span class="chip peds">Pediatric</span>', both: '<span class="chip">Adult</span><span class="chip peds">Pediatric</span>' };
    el.innerHTML =
      '<header class="page-head"><h1>🧭 Systematic Approaches</h1>' +
      '<p>Interpretation is a ritual. Work each checklist step-by-step on real studies until the sequence is automatic — the checkboxes are for practicing runs.</p></header>' +
      '<div class="card-grid">' +
      RIA.data.approaches.map(function (a) {
        return '<a class="card" href="#/approach/' + a.id + '">' +
          '<div class="card-title">' + a.icon + ' ' + esc(a.name) + (isRead('app:' + a.id) ? ' <span class="done">✓</span>' : '') + '</div>' +
          '<div class="card-meta">' + (scopeChip[a.scope] || '') + '</div>' +
          '<div class="card-sub">' + a.steps.length + ' steps</div></a>';
      }).join('') + '</div>';
  }

  function viewApproachDetail(el, id) {
    var a = RIA.data.approaches.find(function (x) { return x.id === id; });
    if (!a) { el.innerHTML = '<p>Not found. <a href="#/approach">Back</a></p>'; return; }
    el.innerHTML =
      '<header class="page-head"><a class="crumb" href="#/approach">← Approaches</a>' +
      '<h1>' + a.icon + ' ' + esc(a.name) + '</h1>' + a.intro + '</header>' +
      '<div class="panel"><div class="row-between"><h2>Checklist</h2><button class="btn small" id="reset-checks">Reset checkboxes</button></div>' +
      '<ol class="checklist">' +
      a.steps.map(function (s, i) {
        return '<li><label><input type="checkbox" data-step="' + i + '"><div>' +
          '<strong>' + esc(s.t) + '</strong><p>' + esc(s.d) + '</p></div></label></li>';
      }).join('') +
      '</ol></div>' +
      '<div class="two-col">' +
        '<section class="panel"><h2>💎 Pearls</h2><ul>' + a.pearls.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ul></section>' +
        '<section class="panel warn"><h2>⚠️ Classic misses</h2><ul>' + a.misses.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ul></section>' +
      '</div>' +
      '<div class="row-center">' + completeButton('app:' + a.id) + '</div>';

    el.querySelector('#reset-checks').addEventListener('click', function () {
      el.querySelectorAll('.checklist input').forEach(function (c) { c.checked = false; });
    });
    wireComplete(el, function () { viewApproachDetail(el, id); });
  }

  // ——— Anatomy ———
  function viewAnatomyList(el) {
    el.innerHTML =
      '<header class="page-head"><h1>🗺️ Radiologic Anatomy</h1>' +
      '<p>Imaging anatomy by region, always with the pediatric deltas alongside the adult norms.</p></header>' +
      '<div class="card-grid">' +
      RIA.data.anatomy.map(function (r) {
        return '<a class="card" href="#/anatomy/' + r.id + '">' +
          '<div class="card-title">' + r.icon + ' ' + esc(r.name) + (isRead('ana:' + r.id) ? ' <span class="done">✓</span>' : '') + '</div>' +
          '<div class="card-sub">' + r.sections.length + ' topics</div></a>';
      }).join('') + '</div>';
  }

  function viewAnatomyDetail(el, id) {
    var r = RIA.data.anatomy.find(function (x) { return x.id === id; });
    if (!r) { el.innerHTML = '<p>Not found. <a href="#/anatomy">Back</a></p>'; return; }
    var svg = r.svg && RIA.data.anatomySvgs[r.svg] ? '<div class="panel diagram">' + RIA.data.anatomySvgs[r.svg] + '</div>' : '';
    el.innerHTML =
      '<header class="page-head"><a class="crumb" href="#/anatomy">← Anatomy</a>' +
      '<h1>' + r.icon + ' ' + esc(r.name) + '</h1>' + r.intro + '</header>' +
      svg +
      r.sections.map(function (s) {
        return '<section class="panel"><h2>' + esc(s.h) + '</h2>' + s.body + '</section>';
      }).join('') +
      (r.peds ? '<section class="panel peds-callout"><h2>🧸 Pediatric</h2>' + r.peds + '</section>' : '') +
      '<div class="row-center">' + completeButton('ana:' + r.id) + '</div>';
    wireComplete(el, function () { viewAnatomyDetail(el, id); });
  }

  // ——— Signs ———
  function viewSigns(el, filterQ) {
    var q = (filterQ || '').toLowerCase();
    var regions = [];
    RIA.data.signs.forEach(function (s) { if (regions.indexOf(s.region) === -1) regions.push(s.region); });

    function rowsHtml(query, region) {
      return RIA.data.signs.filter(function (s) {
        var hay = (s.name + ' ' + s.modality + ' ' + s.region + ' ' + s.desc + ' ' + s.means).toLowerCase();
        return (!query || hay.indexOf(query) !== -1) && (!region || s.region === region);
      }).map(function (s) {
        return '<tr><td><strong>' + esc(s.name) + '</strong></td><td>' + esc(s.modality) + '</td><td>' + esc(s.region) + '</td>' +
          '<td>' + esc(s.desc) + '<div class="dim">' + esc(s.means) + '</div></td></tr>';
      }).join('') || '<tr><td colspan="4" class="dim">No matches.</td></tr>';
    }

    el.innerHTML =
      '<header class="page-head"><h1>💡 Classic Signs</h1>' +
      '<p>' + RIA.data.signs.length + ' named signs. A sign is a compressed diagnosis — learn what it looks like, what it means, and what to do next.</p></header>' +
      '<div class="row-start">' +
        '<input id="sign-q" class="search-box" placeholder="Search signs… (e.g., pneumoperitoneum, torsion)" value="' + esc(filterQ || '') + '">' +
        '<select id="sign-region"><option value="">All regions</option>' +
        regions.map(function (r) { return '<option>' + esc(r) + '</option>'; }).join('') + '</select>' +
      '</div>' +
      '<div class="table-wrap"><table class="signs-table">' +
      '<thead><tr><th>Sign</th><th>Modality</th><th>Region</th><th>Appearance & meaning</th></tr></thead>' +
      '<tbody id="sign-rows">' + rowsHtml(q, '') + '</tbody></table></div>';

    function refresh() {
      var query = el.querySelector('#sign-q').value.toLowerCase();
      var region = el.querySelector('#sign-region').value;
      el.querySelector('#sign-rows').innerHTML = rowsHtml(query, region);
    }
    el.querySelector('#sign-q').addEventListener('input', refresh);
    el.querySelector('#sign-region').addEventListener('change', refresh);
  }

  // ——— Measurements ———
  function viewMeasurements(el) {
    el.innerHTML =
      '<header class="page-head"><h1>📏 Normal Measurements & Thresholds</h1>' +
      '<p>Commonly taught reference values — local protocols, age, and body habitus adjust them. Anchor the number, then learn its exceptions.</p></header>' +
      RIA.data.measurements.map(function (g) {
        return '<section class="panel"><h2>' + esc(g.group) + '</h2><div class="table-wrap"><table>' +
          '<thead><tr><th>Structure / metric</th><th>Normal</th><th>Notes</th></tr></thead><tbody>' +
          g.rows.map(function (r) {
            return '<tr><td>' + esc(r[0]) + '</td><td class="nowrap"><strong>' + esc(r[1]) + '</strong></td><td class="dim">' + esc(r[2]) + '</td></tr>';
          }).join('') + '</tbody></table></div></section>';
      }).join('');
  }

  // ——— Global search ———
  function viewSearch(el, q) {
    q = (q || '').trim();
    var ql = q.toLowerCase();
    var results = [];
    if (ql) {
      RIA.data.modalities.forEach(function (m) {
        var hay = (m.name + ' ' + m.tagline + ' ' + m.sections.map(function (s) { return s.h + ' ' + s.body; }).join(' ')).toLowerCase();
        if (hay.indexOf(ql) !== -1) results.push({ href: '#/learn/' + m.id, icon: m.icon, title: m.name, kind: 'Modality module' });
      });
      RIA.data.approaches.forEach(function (a) {
        var hay = (a.name + ' ' + a.intro + ' ' + a.steps.map(function (s) { return s.t + ' ' + s.d; }).join(' ') + a.pearls.join(' ') + a.misses.join(' ')).toLowerCase();
        if (hay.indexOf(ql) !== -1) results.push({ href: '#/approach/' + a.id, icon: a.icon, title: a.name, kind: 'Systematic approach' });
      });
      RIA.data.anatomy.forEach(function (r) {
        var hay = (r.name + ' ' + r.intro + ' ' + r.sections.map(function (s) { return s.h + ' ' + s.body; }).join(' ') + ' ' + (r.peds || '')).toLowerCase();
        if (hay.indexOf(ql) !== -1) results.push({ href: '#/anatomy/' + r.id, icon: r.icon, title: r.name, kind: 'Anatomy region' });
      });
      RIA.data.signs.forEach(function (s) {
        var hay = (s.name + ' ' + s.desc + ' ' + s.means + ' ' + s.region).toLowerCase();
        if (hay.indexOf(ql) !== -1) results.push({ href: '#/signs?q=' + encodeURIComponent(s.name), icon: '💡', title: s.name, kind: 'Classic sign · ' + s.region });
      });
      RIA.data.measurements.forEach(function (g) {
        g.rows.forEach(function (r) {
          if ((r[0] + ' ' + r[1] + ' ' + r[2]).toLowerCase().indexOf(ql) !== -1) {
            results.push({ href: '#/measurements', icon: '📏', title: r[0] + ' — ' + r[1], kind: 'Measurement' });
          }
        });
      });
    }
    el.innerHTML =
      '<header class="page-head"><h1>🔎 Search</h1></header>' +
      '<input id="global-q" class="search-box wide" placeholder="Search the whole curriculum…" value="' + esc(q) + '" autofocus>' +
      (ql ? '<p class="dim">' + results.length + ' result(s) for “' + esc(q) + '”</p>' : '<p class="dim">Type to search modalities, approaches, anatomy, signs, and measurements.</p>') +
      '<div class="result-list">' +
      results.map(function (r) {
        return '<a class="result" href="' + r.href + '"><span>' + r.icon + '</span><div><strong>' + esc(r.title) + '</strong><div class="dim small">' + esc(r.kind) + '</div></div></a>';
      }).join('') + '</div>';
    var box = el.querySelector('#global-q');
    box.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') location.hash = '#/search?q=' + encodeURIComponent(box.value);
    });
  }

  // ——— About ———
  function viewAbout(el) {
    el.innerHTML =
      '<header class="page-head"><h1>ℹ️ About & How to Use</h1></header>' +
      '<section class="panel"><h2>A suggested workflow</h2><ol>' +
        '<li><strong>Foundation:</strong> work through the Modalities modules — you cannot interpret images whose physics you do not understand.</li>' +
        '<li><strong>Ritual:</strong> pick one Systematic Approach at a time (start with the adult CXR). Read it, then run its checklist against real teaching cases until it is automatic.</li>' +
        '<li><strong>Anatomy in parallel:</strong> one region per week, always noting the pediatric deltas.</li>' +
        '<li><strong>Bank cases:</strong> collect anonymized teaching images into the Study Library. For each case: write Findings and Impression BEFORE revealing the diagnosis; annotate the key finding; add a flashcard for the lesson.</li>' +
        '<li><strong>Retain:</strong> clear your due flashcards daily (minutes, not hours) and re-take quizzes until stable ≥85%.</li>' +
        '<li><strong>Push volume:</strong> speed comes from repetitions of the same search pattern, not from rushing. Accuracy first; speed follows.</li>' +
      '</ol></section>' +
      '<section class="panel"><h2>Where to find practice images</h2>' +
      '<p>This app deliberately ships without patient images. Openly licensed teaching cases (look for each case\'s license) are available from sources such as ' +
      'Radiopaedia (radiopaedia.org), openly licensed institutional teaching files, and public DICOM sample sets. Save cases you study into your library with your own write-ups.</p></section>' +
      '<section class="panel"><h2>Privacy & data</h2>' +
      '<p>All studies, images, notes, progress, and flashcards live in <strong>this browser only</strong> (IndexedDB + localStorage). Clearing site data erases them. ' +
      'Never store images containing patient-identifiable information (names, IDs, dates of birth, faces) — anonymize first.</p></section>' +
      '<section class="panel warn"><h2>Disclaimer</h2>' +
      '<p>Educational reference for self-study. Not medical advice, not a diagnostic tool, and not a substitute for accredited training and supervised practice. ' +
      'Reference values and guidance simplify real practice — always defer to current local protocols and formal references.</p></section>';
  }

  // ——— Router ———
  var routes = [
    { re: /^#?\/?$/, fn: function () { viewHome(main); } },
    { re: /^#\/learn$/, fn: function () { viewLearnList(main); } },
    { re: /^#\/learn\/([\w-]+)$/, fn: function (m) { viewLearnDetail(main, m[1]); } },
    { re: /^#\/approach$/, fn: function () { viewApproachList(main); } },
    { re: /^#\/approach\/([\w-]+)$/, fn: function (m) { viewApproachDetail(main, m[1]); } },
    { re: /^#\/anatomy$/, fn: function () { viewAnatomyList(main); } },
    { re: /^#\/anatomy\/([\w-]+)$/, fn: function (m) { viewAnatomyDetail(main, m[1]); } },
    { re: /^#\/signs(?:\?q=(.*))?$/, fn: function (m) { viewSigns(main, m[1] ? decodeURIComponent(m[1]) : ''); } },
    { re: /^#\/measurements$/, fn: function () { viewMeasurements(main); } },
    { re: /^#\/library$/, fn: function () { RIA.library.renderList(main); } },
    { re: /^#\/study\/([\w-]+)$/, fn: function (m) { RIA.library.renderStudy(main, m[1]); } },
    { re: /^#\/flashcards$/, fn: function () { RIA.quiz.renderFlashcards(main); } },
    { re: /^#\/quiz$/, fn: function () { RIA.quiz.renderList(main); } },
    { re: /^#\/quiz\/([\w-]+)$/, fn: function (m) { RIA.quiz.renderQuiz(main, m[1]); } },
    { re: /^#\/search(?:\?q=(.*))?$/, fn: function (m) { viewSearch(main, m[1] ? decodeURIComponent(m[1]) : ''); } },
    { re: /^#\/about$/, fn: function () { viewAbout(main); } }
  ];

  function route() {
    // teardown of stateful views
    RIA.library.destroyViewer();
    if (main._fcKeyHandler) { document.removeEventListener('keydown', main._fcKeyHandler); main._fcKeyHandler = null; }

    var hash = location.hash || '#/';
    for (var i = 0; i < routes.length; i++) {
      var m = hash.match(routes[i].re);
      if (m) { routes[i].fn(m); highlightNav(hash); window.scrollTo(0, 0); return; }
    }
    main.innerHTML = '<p>Page not found. <a href="#/">Home</a></p>';
  }

  function highlightNav(hash) {
    var section = hash.split('/')[1] || '';
    section = section.split('?')[0];
    var map = { study: 'library', '': 'home' };
    var active = map[section] !== undefined ? map[section] : section;
    document.querySelectorAll('.nav a').forEach(function (a) {
      a.classList.toggle('active', a.dataset.nav === active);
    });
  }

  function init() {
    main = document.getElementById('main');
    document.getElementById('nav-search-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var q = document.getElementById('nav-search').value.trim();
      location.hash = '#/search?q=' + encodeURIComponent(q);
    });
    var burger = document.getElementById('burger');
    var sidebar = document.querySelector('.sidebar');
    burger.addEventListener('click', function () { sidebar.classList.toggle('open'); });
    document.querySelector('.nav').addEventListener('click', function (e) {
      if (e.target.closest('a')) sidebar.classList.remove('open');
    });
    window.addEventListener('hashchange', route);
    route();
  }

  return { init: init };
})();

document.addEventListener('DOMContentLoaded', RIA.app.init);

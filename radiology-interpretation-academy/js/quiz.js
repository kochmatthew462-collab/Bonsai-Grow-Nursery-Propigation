/* Radiology Interpretation Academy — quizzes and flashcard review sessions. */
window.RIA = window.RIA || {};

RIA.quiz = (function () {
  var esc = function (s) { return RIA.ui.esc(s); };

  // ——— Quiz list ———
  function bestScores() { return RIA.db.get('quizScores', {}); }

  function renderList(el) {
    var scores = bestScores();
    el.innerHTML =
      '<header class="page-head"><h1>❓ Quizzes</h1>' +
      '<p>Applied interpretation questions with explanations. Best scores are saved locally.</p></header>' +
      '<div class="card-grid">' +
      RIA.data.quizzes.map(function (q) {
        var best = scores[q.id];
        return '<a class="card" href="#/quiz/' + q.id + '">' +
          '<div class="card-title">' + q.icon + ' ' + esc(q.name) + '</div>' +
          '<div class="card-sub">' + esc(q.desc) + '</div>' +
          '<div class="card-sub">' + q.questions.length + ' questions' +
          (best !== undefined ? ' · best: <strong>' + best + '/' + q.questions.length + '</strong>' : '') + '</div>' +
        '</a>';
      }).join('') +
      '</div>';
  }

  // ——— Take a quiz ———
  function renderQuiz(el, id) {
    var quiz = RIA.data.quizzes.find(function (q) { return q.id === id; });
    if (!quiz) { el.innerHTML = '<p>Quiz not found. <a href="#/quiz">Back</a></p>'; return; }
    var state = { i: 0, correct: 0, answered: false };

    function renderQ() {
      var q = quiz.questions[state.i];
      // shuffle option order so the answer position is never predictable
      var order = q.opts.map(function (_, i) { return i; });
      for (var s = order.length - 1; s > 0; s--) {
        var r = Math.floor(Math.random() * (s + 1));
        var tmp = order[s]; order[s] = order[r]; order[r] = tmp;
      }
      var answerPos = order.indexOf(q.a);
      el.innerHTML =
        '<header class="page-head"><a class="crumb" href="#/quiz">← Quizzes</a>' +
        '<h1>' + quiz.icon + ' ' + esc(quiz.name) + '</h1>' +
        '<p class="dim">Question ' + (state.i + 1) + ' of ' + quiz.questions.length +
        ' · ' + state.correct + ' correct so far</p></header>' +
        '<div class="panel quiz-panel">' +
          '<p class="quiz-q">' + esc(q.q) + '</p>' +
          '<div class="quiz-opts">' +
          order.map(function (origIdx, i) {
            return '<button class="quiz-opt" data-i="' + i + '">' + esc(q.opts[origIdx]) + '</button>';
          }).join('') +
          '</div>' +
          '<div class="quiz-why" hidden></div>' +
          '<div class="row-end"><button class="btn primary" id="quiz-next" hidden>' +
          (state.i + 1 < quiz.questions.length ? 'Next question →' : 'Finish') + '</button></div>' +
        '</div>';

      el.querySelector('.quiz-opts').addEventListener('click', function (e) {
        var btn = e.target.closest('.quiz-opt');
        if (!btn || state.answered) return;
        state.answered = true;
        var pick = parseInt(btn.dataset.i, 10);
        var right = pick === answerPos;
        if (right) state.correct += 1;
        el.querySelectorAll('.quiz-opt').forEach(function (b, i) {
          b.disabled = true;
          if (i === answerPos) b.classList.add('correct');
          if (i === pick && !right) b.classList.add('wrong');
        });
        var why = el.querySelector('.quiz-why');
        why.hidden = false;
        why.innerHTML = '<strong>' + (right ? '✔ Correct.' : '✘ Not quite.') + '</strong> ' + esc(q.why);
        el.querySelector('#quiz-next').hidden = false;
      });

      el.querySelector('#quiz-next').addEventListener('click', function () {
        state.i += 1;
        state.answered = false;
        if (state.i < quiz.questions.length) renderQ();
        else renderResult();
      });
    }

    function renderResult() {
      var scores = bestScores();
      var prev = scores[quiz.id] || 0;
      if (state.correct > prev) { scores[quiz.id] = state.correct; RIA.db.set('quizScores', scores); }
      var pct = Math.round(100 * state.correct / quiz.questions.length);
      el.innerHTML =
        '<header class="page-head"><a class="crumb" href="#/quiz">← Quizzes</a><h1>' + quiz.icon + ' Results</h1></header>' +
        '<div class="panel center">' +
        '<div class="score-big">' + state.correct + ' / ' + quiz.questions.length + '</div>' +
        '<p>' + pct + '% — ' + (pct >= 85 ? 'excellent; keep the streak.' : pct >= 60 ? 'solid — review the explanations you missed.' : 'worth re-reading the linked modules and retrying.') + '</p>' +
        '<div class="row-center">' +
        '<a class="btn" href="#/quiz/' + quiz.id + '" onclick="location.reload()">Retry</a> ' +
        '<a class="btn primary" href="#/quiz">All quizzes</a></div></div>';
    }

    renderQ();
  }

  // ——— Flashcards ———
  function renderFlashcards(el) {
    var decks = RIA.srs.deckSummary();
    var due = RIA.srs.dueCards();
    el.innerHTML =
      '<header class="page-head"><h1>🃏 Flashcards</h1>' +
      '<p>Spaced repetition (SM-2). Cards you find hard return sooner; easy cards stretch out over weeks. ' +
      '<strong>' + due.length + '</strong> card(s) due now.</p></header>' +
      '<div class="row-start">' +
        '<button class="btn primary" id="start-review"' + (due.length ? '' : ' disabled') + '>Start review (' + due.length + ')</button>' +
      '</div>' +
      '<h2>Decks</h2>' +
      '<div class="card-grid">' +
      decks.map(function (d) {
        return '<div class="card"><div class="card-title">' + esc(d.name) + '</div>' +
          '<div class="card-sub">' + d.total + ' cards · ' + d.due + ' due · ' + d.learned + ' learned</div></div>';
      }).join('') +
      '</div>' +
      '<div class="panel"><h2>Add your own card</h2>' +
      '<form id="add-card" class="form-grid">' +
        '<label>Deck<input name="deck" placeholder="My Cards" value="My Cards"></label>' +
        '<label class="span2">Front<input name="front" required placeholder="Question / prompt"></label>' +
        '<label class="span2">Back<input name="back" required placeholder="Answer"></label>' +
        '<button class="btn" type="submit">Add card</button>' +
      '</form>' +
      '<div id="user-cards"></div></div>';

    function renderUserCards() {
      var mine = RIA.srs.allCards().filter(function (c) { return c.user; });
      el.querySelector('#user-cards').innerHTML = mine.length
        ? '<h3>Your cards (' + mine.length + ')</h3><ul class="img-list">' + mine.map(function (c) {
            return '<li><span>' + esc(c.front) + '</span><button class="btn tiny danger" data-del="' + c.id + '">✕</button></li>';
          }).join('') + '</ul>'
        : '';
    }
    renderUserCards();

    el.querySelector('#add-card').addEventListener('submit', function (e) {
      e.preventDefault();
      var f = e.target;
      RIA.srs.addUserCard(f.deck.value.trim() || 'My Cards', f.front.value.trim(), f.back.value.trim());
      f.front.value = ''; f.back.value = '';
      RIA.ui.toast('Card added');
      renderFlashcards(el);
    });
    el.querySelector('#user-cards').addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-del]');
      if (!btn) return;
      RIA.srs.deleteUserCard(btn.dataset.del);
      renderFlashcards(el);
    });
    el.querySelector('#start-review').addEventListener('click', function () { renderSession(el); });
  }

  function renderSession(el) {
    var queue = RIA.srs.dueCards();
    // shuffle
    for (var i = queue.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = queue[i]; queue[i] = queue[j]; queue[j] = t;
    }
    var done = 0;

    function next() {
      if (!queue.length) {
        el.innerHTML = '<div class="panel center"><div class="score-big">🎉</div>' +
          '<p>Review complete — ' + done + ' card(s) reviewed. Come back when more are due.</p>' +
          '<a class="btn primary" href="#/flashcards" onclick="RIA.quiz._fcBack(event)">Back to decks</a></div>';
        return;
      }
      var card = queue[0];
      el.innerHTML =
        '<header class="page-head"><h1>🃏 Review</h1><p class="dim">' + queue.length + ' remaining · deck: ' + esc(card.deck) + '</p></header>' +
        '<div class="panel flashcard">' +
          '<div class="fc-front">' + esc(card.front) + '</div>' +
          '<div class="fc-back" hidden>' + esc(card.back) + '</div>' +
          '<div class="row-center" id="fc-controls">' +
            '<button class="btn primary" id="fc-show">Show answer (space)</button>' +
          '</div>' +
        '</div>';

      function show() {
        el.querySelector('.fc-back').hidden = false;
        el.querySelector('#fc-controls').innerHTML =
          '<button class="btn grade-again" data-g="0">Again</button>' +
          '<button class="btn grade-hard" data-g="3">Hard</button>' +
          '<button class="btn grade-good" data-g="4">Good</button>' +
          '<button class="btn grade-easy" data-g="5">Easy</button>';
      }
      el.querySelector('#fc-show').addEventListener('click', show);

      el.querySelector('#fc-controls').addEventListener('click', function (e) {
        var btn = e.target.closest('button[data-g]');
        if (!btn) return;
        var g = parseInt(btn.dataset.g, 10);
        RIA.srs.gradeCard(card.id, g);
        queue.shift();
        if (g < 3) queue.push(card); // failed cards come back this session
        else done += 1;
        next();
      });

      function keyHandler(e) {
        if (e.target.matches('input, textarea')) return;
        if (e.key === ' ' && el.querySelector('#fc-show')) { e.preventDefault(); show(); }
        else if (['1', '2', '3', '4'].indexOf(e.key) !== -1 && !el.querySelector('#fc-show')) {
          var map = { '1': 0, '2': 3, '3': 4, '4': 5 };
          document.removeEventListener('keydown', keyHandler);
          RIA.srs.gradeCard(card.id, map[e.key]);
          queue.shift();
          if (map[e.key] < 3) queue.push(card); else done += 1;
          next();
        }
      }
      document.addEventListener('keydown', keyHandler, { once: false });
      // clean up handler when leaving
      el._fcKeyHandler && document.removeEventListener('keydown', el._fcKeyHandler);
      el._fcKeyHandler = keyHandler;
    }
    next();
  }

  function _fcBack(e) {
    // allow default hash navigation; re-render happens via router
  }

  return { renderList: renderList, renderQuiz: renderQuiz, renderFlashcards: renderFlashcards, _fcBack: _fcBack };
})();

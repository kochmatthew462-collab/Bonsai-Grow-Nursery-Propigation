/* Radiology Interpretation Academy — spaced repetition (SM-2 variant).
   Card state: { ef, interval (days), reps, due (ms epoch) }. Grades: 0=Again, 3=Hard, 4=Good, 5=Easy. */
window.RIA = window.RIA || {};

RIA.srs = (function () {
  var DAY = 24 * 60 * 60 * 1000;

  function freshState() {
    return { ef: 2.5, interval: 0, reps: 0, due: Date.now() };
  }

  function review(state, grade) {
    var s = state ? { ef: state.ef, interval: state.interval, reps: state.reps, due: state.due } : freshState();
    if (grade < 3) {
      s.reps = 0;
      s.interval = 0;
      s.due = Date.now() + 10 * 60 * 1000; // retry in ~10 minutes (same session shows it again)
    } else {
      if (s.reps === 0) s.interval = 1;
      else if (s.reps === 1) s.interval = 6;
      else s.interval = Math.round(s.interval * s.ef);
      s.reps += 1;
      s.ef = Math.max(1.3, s.ef + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)));
      if (grade === 3) s.interval = Math.max(1, Math.round(s.interval * 0.8));
      s.due = Date.now() + s.interval * DAY;
    }
    return s;
  }

  // ——— card sources: seeded deck + user cards ———
  function userCards() { return RIA.db.get('userCards', []); }
  function saveUserCards(cards) { RIA.db.set('userCards', cards); }

  function allCards() {
    return RIA.data.flashcards.concat(userCards());
  }

  function states() { return RIA.db.get('srsStates', {}); }
  function saveStates(s) { RIA.db.set('srsStates', s); }

  function dueCards(now) {
    now = now || Date.now();
    var st = states();
    return allCards().filter(function (c) {
      var s = st[c.id];
      return !s || s.due <= now;
    });
  }

  function gradeCard(cardId, grade) {
    var st = states();
    st[cardId] = review(st[cardId], grade);
    saveStates(st);
    return st[cardId];
  }

  function addUserCard(deck, front, back) {
    var cards = userCards();
    var card = { id: RIA.db.uid('ufc'), deck: deck || 'My Cards', front: front, back: back, user: true };
    cards.push(card);
    saveUserCards(cards);
    return card;
  }

  function deleteUserCard(id) {
    saveUserCards(userCards().filter(function (c) { return c.id !== id; }));
    var st = states();
    delete st[id];
    saveStates(st);
  }

  function deckSummary() {
    var st = states();
    var now = Date.now();
    var decks = {};
    allCards().forEach(function (c) {
      var d = decks[c.deck] || (decks[c.deck] = { name: c.deck, total: 0, due: 0, learned: 0 });
      d.total += 1;
      var s = st[c.id];
      if (!s || s.due <= now) d.due += 1;
      if (s && s.reps >= 2) d.learned += 1;
    });
    return Object.keys(decks).sort().map(function (k) { return decks[k]; });
  }

  return {
    review: review, dueCards: dueCards, gradeCard: gradeCard,
    allCards: allCards, addUserCard: addUserCard, deleteUserCard: deleteUserCard,
    deckSummary: deckSummary, states: states
  };
})();

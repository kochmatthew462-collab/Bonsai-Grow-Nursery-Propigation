/* Radiology Interpretation Academy — tiny shared UI helpers. */
window.RIA = window.RIA || {};

RIA.ui = (function () {
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function fmtDate(ms) {
    if (!ms) return '';
    var d = new Date(ms);
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function chip(text, cls) {
    return '<span class="chip ' + (cls || '') + '">' + esc(text) + '</span>';
  }

  function toast(text) {
    var t = document.createElement('div');
    t.className = 'toast';
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(function () { t.classList.add('show'); }, 10);
    setTimeout(function () { t.classList.remove('show'); setTimeout(function () { t.remove(); }, 400); }, 2600);
  }

  return { esc: esc, fmtDate: fmtDate, chip: chip, toast: toast };
})();

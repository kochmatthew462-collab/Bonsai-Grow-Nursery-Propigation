/*
 * Bonsai charts — small dependency-free SVG charts.
 *
 * Design rules applied throughout: 2px lines with round caps, >=8px markers
 * carrying a 2px surface ring, solid hairline gridlines, a single y-axis per
 * chart, values in text tokens rather than the series colour, a hover and
 * keyboard readout, and a table view so no value is reachable only by hovering.
 */
(function (global) {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';

  function el(name, attrs) {
    var node = document.createElementNS(SVG_NS, name);
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    return node;
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function formatDateLong(iso) {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  }

  // Round a domain out to human-readable tick values (0 / 0.5 / 1.0 ...).
  function niceTicks(min, max, count) {
    if (min === max) {
      var pad = Math.abs(min) > 1 ? Math.abs(min) * 0.1 : 0.5;
      min -= pad;
      max += pad;
    }
    var raw = (max - min) / Math.max(1, count);
    var magnitude = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    // No 2.5 step: a 0.25 gridline cannot be labelled honestly at one decimal.
    var candidates = [1, 2, 5, 10];
    var step = magnitude;
    for (var i = 0; i < candidates.length; i++) {
      if (candidates[i] * magnitude >= raw) { step = candidates[i] * magnitude; break; }
    }
    var start = Math.floor(min / step) * step;
    var end = Math.ceil(max / step) * step;
    var ticks = [];
    for (var v = start; v <= end + step / 2; v += step) {
      ticks.push(Math.round(v * 1e6) / 1e6);
    }
    return { ticks: ticks, min: start, max: end };
  }

  function trimNumber(value, decimals) {
    var fixed = Number(value).toFixed(decimals == null ? 1 : decimals);
    return fixed.replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
  }

  // Fewest decimals that still render every tick exactly, so an axis label
  // never rounds away from the gridline it sits on.
  function exactDecimals(values) {
    for (var d = 0; d <= 4; d++) {
      var exact = values.every(function (v) {
        return Math.abs(v - Number(v.toFixed(d))) < 1e-9;
      });
      if (exact) return d;
    }
    return 4;
  }

  function emptyState(container, message) {
    container.textContent = '';
    var note = document.createElement('p');
    note.className = 'chart-empty';
    note.textContent = message;
    container.appendChild(note);
  }

  /* ---------------------------------------------------------- tooltip */

  function makeTooltip(container) {
    var tip = document.createElement('div');
    tip.className = 'chart-tooltip';
    tip.hidden = true;
    container.appendChild(tip);

    return {
      show: function (x, y, rows) {
        tip.textContent = '';
        rows.forEach(function (row) {
          var line = document.createElement('div');
          line.className = 'chart-tooltip-row';
          if (row.color) {
            var key = document.createElement('span');
            key.className = 'chart-tooltip-key';
            key.style.background = row.color;
            line.appendChild(key);
          }
          // Values lead, labels follow.
          var value = document.createElement('strong');
          value.textContent = row.value;
          line.appendChild(value);
          if (row.label) {
            var label = document.createElement('span');
            label.className = 'chart-tooltip-label';
            label.textContent = row.label;
            line.appendChild(label);
          }
          tip.appendChild(line);
        });
        tip.hidden = false;
        var width = tip.offsetWidth;
        var left = Math.max(4, Math.min(x - width / 2, container.clientWidth - width - 4));
        tip.style.left = left + 'px';
        tip.style.top = Math.max(0, y - tip.offsetHeight - 12) + 'px';
      },
      hide: function () { tip.hidden = true; }
    };
  }

  /* ------------------------------------------------------ trend chart */

  /**
   * A trend over time carrying one or two series. Two series (a low/high
   * range) get a legend from the caller; one needs none, because the card
   * title already names what is plotted. The latest value of each series
   * rides its line as a direct label.
   *
   * options: {
   *   series:   [{ name, color, points: [{ at, value }] }],
   *   bands:    optional target zones [{ good: [lo, hi], label }] — a chart
   *             plotting two series shades and names one band per series, so
   *             it is never ambiguous which zone belongs to which line,
   *   name, unit, decimals
   * }
   */
  function trend(container, options) {
    var series = (options.series || []).filter(function (s) { return s.points && s.points.length; });
    var bands = (options.bands || []).filter(function (b) { return b && b.good; });
    var decimals = options.decimals == null ? 1 : options.decimals;
    var unit = options.unit || '';

    function draw() {
      if (!series.length) {
        emptyState(container, 'No ' + options.name.toLowerCase() + ' readings yet.');
        return;
      }
      container.textContent = '';
      var tooltip = makeTooltip(container);

      var width = Math.max(240, container.clientWidth);
      var padding = { top: 16, right: 62, bottom: 26, left: 44 };
      var plotHeight = 132;
      var height = plotHeight + padding.top + padding.bottom;

      var values = [];
      series.forEach(function (s) {
        s.points.forEach(function (p) { values.push(p.value); });
      });
      // Keep every target band on screen even when readings sit outside them.
      bands.forEach(function (b) { values.push(b.good[0], b.good[1]); });

      var scale = niceTicks(Math.min.apply(null, values), Math.max.apply(null, values), 4);
      var tickDecimals = exactDecimals(scale.ticks);

      var times = [];
      series.forEach(function (s) {
        s.points.forEach(function (p) { if (times.indexOf(p.at) < 0) times.push(p.at); });
      });
      times.sort();
      var stamps = times.map(function (t) { return new Date(t).getTime(); });
      var tMin = Math.min.apply(null, stamps);
      var tMax = Math.max.apply(null, stamps);
      var innerWidth = width - padding.left - padding.right;

      function xOf(time) {
        if (tMax === tMin) return padding.left + innerWidth / 2;
        return padding.left + ((time - tMin) / (tMax - tMin)) * innerWidth;
      }
      function yOf(value) {
        var span = scale.max - scale.min || 1;
        return padding.top + plotHeight - ((value - scale.min) / span) * plotHeight;
      }

      var label = options.name + ' over time, ' + times.length +
        (times.length === 1 ? ' reading' : ' readings');
      var svg = el('svg', {
        width: width, height: height, viewBox: '0 0 ' + width + ' ' + height,
        role: 'img', tabindex: '0', 'aria-label': label
      });
      svg.classList.add('chart-svg');

      // Target bands sit behind everything. They are reference zones rather
      // than data marks, so they wear a neutral wash, never a series hue.
      bands.forEach(function (b) {
        var bandTop = yOf(Math.min(b.good[1], scale.max));
        var bandBottom = yOf(Math.max(b.good[0], scale.min));
        svg.appendChild(el('rect', {
          x: padding.left, y: bandTop, width: innerWidth,
          height: Math.max(1, bandBottom - bandTop), class: 'chart-band'
        }));
        var bandText = el('text', {
          x: padding.left + 4, y: Math.max(10, bandTop - 3), class: 'chart-band-label'
        });
        bandText.textContent = (b.label || 'target') + ' ' +
          trimNumber(b.good[0], tickDecimals) + '–' + trimNumber(b.good[1], tickDecimals);
        svg.appendChild(bandText);
      });

      // Gridlines and y-axis ticks.
      scale.ticks.forEach(function (tick) {
        var y = yOf(tick);
        if (y < padding.top - 1 || y > padding.top + plotHeight + 1) return;
        svg.appendChild(el('line', {
          x1: padding.left, x2: width - padding.right, y1: y, y2: y, class: 'chart-grid'
        }));
        var text = el('text', {
          x: padding.left - 8, y: y + 4, class: 'chart-axis-text', 'text-anchor': 'end'
        });
        text.textContent = trimNumber(tick, tickDecimals);
        svg.appendChild(text);
      });

      // X-axis: first and last reading, plus the middle when there is room.
      var xIndices = times.length > 2
        ? [0, Math.floor(times.length / 2), times.length - 1]
        : [0, times.length - 1];
      xIndices.filter(function (v, i, a) { return a.indexOf(v) === i; }).forEach(function (index) {
        var text = el('text', {
          x: xOf(stamps[index]), y: padding.top + plotHeight + 18, class: 'chart-axis-text',
          'text-anchor': index === 0 ? 'start' : (index === times.length - 1 ? 'end' : 'middle')
        });
        text.textContent = formatDate(times[index]);
        svg.appendChild(text);
      });

      // Lines.
      series.forEach(function (s) {
        if (s.points.length < 2) return;
        var d = s.points.map(function (p, i) {
          return (i ? 'L' : 'M') + xOf(new Date(p.at).getTime()).toFixed(2) +
            ' ' + yOf(p.value).toFixed(2);
        }).join(' ');
        svg.appendChild(el('path', {
          d: d, fill: 'none', stroke: s.color, 'stroke-width': '2',
          'stroke-linejoin': 'round', 'stroke-linecap': 'round'
        }));
      });

      var crosshair = el('line', {
        class: 'chart-crosshair', y1: padding.top, y2: padding.top + plotHeight
      });
      crosshair.style.display = 'none';
      svg.appendChild(crosshair);

      var hoverDots = series.map(function (s) {
        var dot = el('circle', { r: 4, fill: s.color, class: 'chart-hover-dot' });
        dot.style.display = 'none';
        svg.appendChild(dot);
        return dot;
      });

      // Endpoint markers carry a 2px surface ring so they stay legible where
      // two series cross near the right edge.
      var endLabels = [];
      series.forEach(function (s) {
        var last = s.points[s.points.length - 1];
        var x = xOf(new Date(last.at).getTime());
        var y = yOf(last.value);
        svg.appendChild(el('circle', {
          cx: x, cy: y, r: 4, fill: s.color, stroke: 'var(--surface-1)', 'stroke-width': '2'
        }));
        endLabels.push({ x: x + 10, y: y, text: trimNumber(last.value, decimals) + (unit ? ' ' + unit : '') });
      });

      // Nudge colliding end labels apart rather than letting them overlap.
      if (endLabels.length === 2 && Math.abs(endLabels[0].y - endLabels[1].y) < 13) {
        var higher = endLabels[0].y <= endLabels[1].y ? endLabels[0] : endLabels[1];
        var lower = higher === endLabels[0] ? endLabels[1] : endLabels[0];
        higher.y -= 6;
        lower.y += 7;
      }
      endLabels.forEach(function (item) {
        var text = el('text', { x: item.x, y: item.y + 4, class: 'chart-end-label' });
        text.textContent = item.text;
        svg.appendChild(text);
      });

      function valueAt(s, at) {
        for (var i = 0; i < s.points.length; i++) {
          if (s.points[i].at === at) return s.points[i].value;
        }
        return null;
      }

      function selectIndex(index) {
        if (index < 0 || index >= times.length) return;
        var at = times[index];
        var x = xOf(stamps[index]);
        crosshair.setAttribute('x1', x);
        crosshair.setAttribute('x2', x);
        crosshair.style.display = '';

        var rows = [];
        series.forEach(function (s, i) {
          var value = valueAt(s, at);
          if (value == null) {
            hoverDots[i].style.display = 'none';
            return;
          }
          var y = yOf(value);
          hoverDots[i].setAttribute('cx', x);
          hoverDots[i].setAttribute('cy', y);
          hoverDots[i].style.display = '';
          rows.push({
            color: s.color,
            value: trimNumber(value, decimals) + (unit ? ' ' + unit : ''),
            label: series.length > 1 ? s.name : formatDateLong(at)
          });
        });
        if (series.length > 1) rows.push({ value: formatDateLong(at), label: '' });
        if (rows.length) tooltip.show(x, yOf(scale.max), rows);
      }

      function clear() {
        crosshair.style.display = 'none';
        hoverDots.forEach(function (dot) { dot.style.display = 'none'; });
        tooltip.hide();
      }

      // The crosshair snaps to the nearest reading, so the reader aims at a
      // date rather than at a 2px line.
      function nearestTo(clientX) {
        var rect = svg.getBoundingClientRect();
        var x = clientX - rect.left;
        var best = 0;
        var bestDistance = Infinity;
        stamps.forEach(function (stamp, i) {
          var distance = Math.abs(xOf(stamp) - x);
          if (distance < bestDistance) { bestDistance = distance; best = i; }
        });
        return best;
      }

      var current = times.length - 1;
      svg.addEventListener('pointermove', function (event) {
        current = nearestTo(event.clientX);
        selectIndex(current);
      });
      svg.addEventListener('pointerleave', clear);
      svg.addEventListener('focus', function () { selectIndex(current); });
      svg.addEventListener('blur', clear);
      svg.addEventListener('keydown', function (event) {
        if (event.key === 'ArrowRight') current = Math.min(times.length - 1, current + 1);
        else if (event.key === 'ArrowLeft') current = Math.max(0, current - 1);
        else return;
        event.preventDefault();
        selectIndex(current);
      });

      container.appendChild(svg);
    }

    draw();
    observeResize(container, draw);
  }

  /* -------------------------------------------------- care event timeline */

  /**
   * Watering and feeding are events, not a continuous quantity, so they get a
   * dot-per-event lane rather than a line. Two series means a legend.
   */
  function careTimeline(container, options) {
    var rows = options.rows || [];
    var all = rows.reduce(function (acc, row) { return acc.concat(row.events); }, []);

    function draw() {
      if (!all.length) {
        emptyState(container, 'No watering or feeding logged yet.');
        return;
      }
      container.textContent = '';
      var tooltip = makeTooltip(container);

      var width = Math.max(240, container.clientWidth);
      var padding = { top: 12, right: 16, bottom: 26, left: 84 };
      var laneHeight = 30;
      var height = rows.length * laneHeight + padding.top + padding.bottom;

      var times = all.map(function (e) { return new Date(e.at).getTime(); });
      var tMin = Math.min.apply(null, times);
      var tMax = Math.max.apply(null, times);
      var innerWidth = width - padding.left - padding.right;

      function xOf(time) {
        if (tMax === tMin) return padding.left + innerWidth / 2;
        return padding.left + ((time - tMin) / (tMax - tMin)) * innerWidth;
      }

      var svg = el('svg', {
        width: width, height: height, viewBox: '0 0 ' + width + ' ' + height,
        role: 'img', 'aria-label': 'Watering and feeding events over time'
      });
      svg.classList.add('chart-svg');

      rows.forEach(function (row, rowIndex) {
        var y = padding.top + rowIndex * laneHeight + laneHeight / 2;

        svg.appendChild(el('line', {
          x1: padding.left, x2: width - padding.right, y1: y, y2: y, class: 'chart-grid'
        }));

        var laneLabel = el('text', { x: padding.left - 10, y: y + 4, class: 'chart-axis-text', 'text-anchor': 'end' });
        laneLabel.textContent = row.name;
        svg.appendChild(laneLabel);

        row.events.forEach(function (event) {
          var x = xOf(new Date(event.at).getTime());
          svg.appendChild(el('circle', {
            cx: x, cy: y, r: 4, fill: row.color,
            stroke: 'var(--surface-1)', 'stroke-width': '2'
          }));
          // Transparent 24px hit area — an 8px dot is a pinpoint nobody lands on.
          var target = el('circle', { cx: x, cy: y, r: 12, fill: 'transparent', tabindex: '0',
            role: 'button', 'aria-label': row.name + ' ' + formatDateLong(event.at) + ', ' + event.detail });
          function show() {
            tooltip.show(x, y, [{ color: row.color, value: event.detail, label: formatDateLong(event.at) }]);
          }
          target.addEventListener('pointerenter', show);
          target.addEventListener('focus', show);
          target.addEventListener('pointerleave', tooltip.hide);
          target.addEventListener('blur', tooltip.hide);
          svg.appendChild(target);
        });
      });

      [0, 1].forEach(function (which) {
        var time = which === 0 ? tMin : tMax;
        var text = el('text', {
          x: xOf(time), y: height - 8, class: 'chart-axis-text',
          'text-anchor': which === 0 ? 'start' : 'end'
        });
        text.textContent = formatDate(new Date(time).toISOString());
        svg.appendChild(text);
      });

      container.appendChild(svg);
    }

    draw();
    observeResize(container, draw);
  }

  /* ------------------------------------------------------------- helpers */

  function observeResize(container, draw) {
    if (typeof ResizeObserver === 'undefined') return;
    var lastWidth = container.clientWidth;
    var pending = false;
    var observer = new ResizeObserver(function () {
      if (container.clientWidth === lastWidth || pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        lastWidth = container.clientWidth;
        draw();
      });
    });
    observer.observe(container);
  }

  global.BonsaiCharts = {
    trend: trend,
    careTimeline: careTimeline,
    formatDate: formatDate,
    formatDateLong: formatDateLong,
    trimNumber: trimNumber
  };
})(window);

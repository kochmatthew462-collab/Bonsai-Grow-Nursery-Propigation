/*
 * Bonsai QR — a self-contained byte-mode QR Code encoder.
 *
 * Covers versions 1-10 at error-correction levels L and M, which is enough for
 * URLs up to 213 bytes. There is deliberately no CDN dependency: label sheets
 * have to print correctly from a phone in a greenhouse with no signal, and from
 * a plain file:// copy of this folder.
 *
 * Exposed as window.BonsaiQR (and module.exports under Node, for the test).
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.BonsaiQR = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';

  /* ---------------------------------------------------------------- tables */

  // Total codewords (data + error correction) for versions 1-10.
  var TOTAL_CODEWORDS = [26, 44, 70, 100, 134, 172, 196, 242, 292, 346];

  // [ecCodewordsPerBlock, [[blockCount, dataCodewordsPerBlock], ...]]
  var ECC_TABLE = {
    L: [
      [7, [[1, 19]]],
      [10, [[1, 34]]],
      [15, [[1, 55]]],
      [20, [[1, 80]]],
      [26, [[1, 108]]],
      [18, [[2, 68]]],
      [20, [[2, 78]]],
      [24, [[2, 97]]],
      [30, [[2, 116]]],
      [18, [[2, 68], [2, 69]]]
    ],
    M: [
      [10, [[1, 16]]],
      [16, [[1, 28]]],
      [26, [[1, 44]]],
      [18, [[2, 32]]],
      [24, [[2, 43]]],
      [16, [[4, 27]]],
      [18, [[4, 31]]],
      [22, [[2, 38], [2, 39]]],
      [22, [[3, 36], [2, 37]]],
      [26, [[4, 43], [1, 44]]]
    ]
  };

  // Row/column centres of the alignment patterns, indexed by version - 1.
  var ALIGN_CENTERS = [
    [], [6, 18], [6, 22], [6, 26], [6, 30],
    [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50]
  ];

  // The two-bit field the format information carries for each ECC level.
  var ECC_BITS = { L: 1, M: 0, Q: 3, H: 2 };

  /* ------------------------------------------------------- GF(256) & Reed-Solomon */

  var EXP = new Uint8Array(512);
  var LOG = new Uint8Array(256);
  (function () {
    var x = 1;
    for (var i = 0; i < 255; i++) {
      EXP[i] = x;
      LOG[x] = i;
      x <<= 1;
      if (x & 0x100) x ^= 0x11d; // primitive polynomial for QR
    }
    for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255];
  })();

  function gmul(a, b) {
    if (a === 0 || b === 0) return 0;
    return EXP[LOG[a] + LOG[b]];
  }

  // Generator polynomial of degree `degree`, highest-order coefficient first.
  function rsGenerator(degree) {
    var poly = [1];
    for (var i = 0; i < degree; i++) {
      var next = new Array(poly.length + 1);
      for (var k = 0; k < next.length; k++) next[k] = 0;
      for (var j = 0; j < poly.length; j++) {
        next[j] ^= poly[j];
        next[j + 1] ^= gmul(poly[j], EXP[i]);
      }
      poly = next;
    }
    return poly;
  }

  function rsRemainder(data, ecLength) {
    var gen = rsGenerator(ecLength);
    var buf = new Uint8Array(data.length + ecLength);
    buf.set(data, 0);
    for (var i = 0; i < data.length; i++) {
      var coef = buf[i];
      if (coef === 0) continue;
      for (var j = 1; j < gen.length; j++) buf[i + j] ^= gmul(gen[j], coef);
    }
    return buf.slice(data.length);
  }

  /* ------------------------------------------------------------- bit stream */

  function BitBuffer() {
    this.bits = [];
  }
  BitBuffer.prototype.put = function (value, length) {
    for (var i = length - 1; i >= 0; i--) this.bits.push((value >>> i) & 1);
  };

  function utf8Bytes(str) {
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(str);
    var out = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c < 0x80) {
        out.push(c);
      } else if (c < 0x800) {
        out.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
      } else {
        out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
      }
    }
    return new Uint8Array(out);
  }

  function dataCodewordCount(version, ecc) {
    var entry = ECC_TABLE[ecc][version - 1];
    var total = 0;
    entry[1].forEach(function (group) {
      total += group[0] * group[1];
    });
    return total;
  }

  function chooseVersion(byteLength, ecc, minVersion) {
    for (var v = Math.max(1, minVersion || 1); v <= 10; v++) {
      var countBits = v < 10 ? 8 : 16;
      var needed = Math.ceil((4 + countBits + byteLength * 8) / 8);
      if (needed <= dataCodewordCount(v, ecc)) return v;
    }
    return -1;
  }

  // Mode indicator, character count, payload, terminator and the alternating
  // pad bytes, laid out to exactly fill the version's data capacity.
  function encodeData(bytes, version, ecc) {
    var capacity = dataCodewordCount(version, ecc);
    // Without this the writes below run off the end of a Uint8Array, which is
    // a silent no-op and would emit a corrupt symbol rather than an error.
    var needed = Math.ceil((4 + (version < 10 ? 8 : 16) + bytes.length * 8) / 8);
    if (needed > capacity) {
      throw new Error(
        'Payload of ' + bytes.length + ' bytes does not fit version ' + version + '-' + ecc
      );
    }
    var buf = new BitBuffer();
    buf.put(4, 4); // byte mode
    buf.put(bytes.length, version < 10 ? 8 : 16);
    for (var i = 0; i < bytes.length; i++) buf.put(bytes[i], 8);

    var capacityBits = capacity * 8;
    var terminator = Math.min(4, capacityBits - buf.bits.length);
    buf.put(0, terminator);
    while (buf.bits.length % 8 !== 0) buf.bits.push(0);

    var out = new Uint8Array(capacity);
    for (var b = 0; b < buf.bits.length; b += 8) {
      var byteVal = 0;
      for (var k = 0; k < 8; k++) byteVal = (byteVal << 1) | buf.bits[b + k];
      out[b / 8] = byteVal;
    }
    var pads = [0xec, 0x11];
    for (var p = buf.bits.length / 8, n = 0; p < capacity; p++, n++) out[p] = pads[n % 2];
    return out;
  }

  // Split into blocks, append each block's ECC, then interleave both halves.
  function interleave(dataCodewords, version, ecc) {
    var entry = ECC_TABLE[ecc][version - 1];
    var ecPerBlock = entry[0];
    var blocks = [];
    var offset = 0;
    entry[1].forEach(function (group) {
      for (var i = 0; i < group[0]; i++) {
        var chunk = dataCodewords.slice(offset, offset + group[1]);
        offset += group[1];
        blocks.push({ data: chunk, ec: rsRemainder(chunk, ecPerBlock) });
      }
    });

    var maxData = 0;
    blocks.forEach(function (b) {
      if (b.data.length > maxData) maxData = b.data.length;
    });

    var out = [];
    for (var i = 0; i < maxData; i++) {
      for (var j = 0; j < blocks.length; j++) {
        if (i < blocks[j].data.length) out.push(blocks[j].data[i]);
      }
    }
    for (var e = 0; e < ecPerBlock; e++) {
      for (var k = 0; k < blocks.length; k++) out.push(blocks[k].ec[e]);
    }
    return out;
  }

  /* ------------------------------------------------------------ the matrix */

  function makeGrid(size, fill) {
    var grid = new Array(size);
    for (var i = 0; i < size; i++) {
      grid[i] = new Array(size);
      for (var j = 0; j < size; j++) grid[i][j] = fill;
    }
    return grid;
  }

  function placeFinder(modules, reserved, row, col) {
    // The 7x7 finder plus its one-module separator, clipped at the edges.
    for (var r = -1; r <= 7; r++) {
      for (var c = -1; c <= 7; c++) {
        var rr = row + r;
        var cc = col + c;
        if (rr < 0 || rr >= modules.length || cc < 0 || cc >= modules.length) continue;
        var onRing = (r >= 0 && r <= 6 && (c === 0 || c === 6)) ||
                     (c >= 0 && c <= 6 && (r === 0 || r === 6));
        var inCore = r >= 2 && r <= 4 && c >= 2 && c <= 4;
        modules[rr][cc] = onRing || inCore ? 1 : 0;
        reserved[rr][cc] = true;
      }
    }
  }

  function placeAlignment(modules, reserved, version) {
    var centers = ALIGN_CENTERS[version - 1];
    if (!centers.length) return;
    var last = centers[centers.length - 1];
    for (var a = 0; a < centers.length; a++) {
      for (var b = 0; b < centers.length; b++) {
        var row = centers[a];
        var col = centers[b];
        // The three finder corners already own these positions.
        if ((row === 6 && col === 6) || (row === 6 && col === last) || (row === last && col === 6)) continue;
        for (var r = -2; r <= 2; r++) {
          for (var c = -2; c <= 2; c++) {
            var dark = Math.max(Math.abs(r), Math.abs(c)) !== 1;
            modules[row + r][col + c] = dark ? 1 : 0;
            reserved[row + r][col + c] = true;
          }
        }
      }
    }
  }

  function buildFunctionPatterns(version) {
    var size = version * 4 + 17;
    var modules = makeGrid(size, 0);
    var reserved = makeGrid(size, false);

    placeFinder(modules, reserved, 0, 0);
    placeFinder(modules, reserved, 0, size - 7);
    placeFinder(modules, reserved, size - 7, 0);
    placeAlignment(modules, reserved, version);

    // Timing patterns.
    for (var i = 8; i < size - 8; i++) {
      var dark = i % 2 === 0 ? 1 : 0;
      modules[6][i] = dark;
      reserved[6][i] = true;
      modules[i][6] = dark;
      reserved[i][6] = true;
    }

    // Reserve the two format-information strips and the always-dark module.
    for (var k = 0; k <= 8; k++) {
      if (!reserved[8][k]) reserved[8][k] = true;
      if (!reserved[k][8]) reserved[k][8] = true;
    }
    for (var m = 0; m < 8; m++) {
      reserved[size - 1 - m][8] = true;
      reserved[8][size - 1 - m] = true;
    }
    modules[size - 8][8] = 1;
    reserved[size - 8][8] = true;

    // Version information blocks, present from version 7 up.
    if (version >= 7) {
      var rem = version;
      for (var v = 0; v < 12; v++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25);
      var bits = (version << 12) | rem;
      for (var b = 0; b < 18; b++) {
        var bit = (bits >>> b) & 1;
        var r = Math.floor(b / 3);
        var c = size - 11 + (b % 3);
        modules[r][c] = bit;
        reserved[r][c] = true;
        modules[c][r] = bit;
        reserved[c][r] = true;
      }
    }

    return { size: size, modules: modules, reserved: reserved };
  }

  var MASKS = [
    function (r, c) { return (r + c) % 2 === 0; },
    function (r) { return r % 2 === 0; },
    function (r, c) { return c % 3 === 0; },
    function (r, c) { return (r + c) % 3 === 0; },
    function (r, c) { return (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0; },
    function (r, c) { return ((r * c) % 2) + ((r * c) % 3) === 0; },
    function (r, c) { return (((r * c) % 2) + ((r * c) % 3)) % 2 === 0; },
    function (r, c) { return (((r + c) % 2) + ((r * c) % 3)) % 2 === 0; }
  ];

  // Two-module-wide columns walked bottom-to-top then top-to-bottom, skipping
  // the vertical timing column entirely.
  function placeData(modules, reserved, codewords, maskIndex) {
    var size = modules.length;
    var mask = MASKS[maskIndex];
    var bitCount = codewords.length * 8;
    var index = 0;
    var upward = true;

    for (var right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (var step = 0; step < size; step++) {
        var row = upward ? size - 1 - step : step;
        for (var offset = 0; offset < 2; offset++) {
          var col = right - offset;
          if (reserved[row][col]) continue;
          var bit = 0;
          if (index < bitCount) {
            bit = (codewords[index >>> 3] >>> (7 - (index & 7))) & 1;
            index++;
          }
          modules[row][col] = mask(row, col) ? bit ^ 1 : bit;
        }
      }
      upward = !upward;
    }
  }

  function placeFormat(modules, ecc, maskIndex) {
    var size = modules.length;
    var data = (ECC_BITS[ecc] << 3) | maskIndex;
    var rem = data;
    for (var i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
    var bits = ((data << 10) | rem) ^ 0x5412;

    function bit(n) { return (bits >>> n) & 1; }

    // First copy: down column 8, then left along row 8.
    for (var k = 0; k <= 5; k++) modules[k][8] = bit(k);
    modules[7][8] = bit(6);
    modules[8][8] = bit(7);
    modules[8][7] = bit(8);
    for (var j = 9; j <= 14; j++) modules[8][14 - j] = bit(j);

    // Second copy: right along row 8, then up column 8 from the bottom edge.
    for (var a = 0; a <= 7; a++) modules[8][size - 1 - a] = bit(a);
    for (var b = 8; b <= 14; b++) modules[size - 15 + b][8] = bit(b);
    modules[size - 8][8] = 1;
  }

  /* ------------------------------------------------------------- mask score */

  function penalty(modules) {
    var size = modules.length;
    var score = 0;

    // Rule 1 — runs of five or more same-coloured modules in a line.
    for (var pass = 0; pass < 2; pass++) {
      for (var i = 0; i < size; i++) {
        var run = 1;
        var prev = pass === 0 ? modules[i][0] : modules[0][i];
        for (var j = 1; j < size; j++) {
          var cur = pass === 0 ? modules[i][j] : modules[j][i];
          if (cur === prev) {
            run++;
          } else {
            if (run >= 5) score += 3 + (run - 5);
            prev = cur;
            run = 1;
          }
        }
        if (run >= 5) score += 3 + (run - 5);
      }
    }

    // Rule 2 — every 2x2 block of one colour.
    for (var r = 0; r < size - 1; r++) {
      for (var c = 0; c < size - 1; c++) {
        var v = modules[r][c];
        if (v === modules[r][c + 1] && v === modules[r + 1][c] && v === modules[r + 1][c + 1]) score += 3;
      }
    }

    // Rule 3 — finder-like 1:1:3:1:1 sequences with four light modules beside them.
    var A = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0];
    var B = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1];
    function matches(get, start, pattern) {
      for (var n = 0; n < 11; n++) if (get(start + n) !== pattern[n]) return false;
      return true;
    }
    for (var line = 0; line < size; line++) {
      (function (line) {
        var rowGet = function (n) { return modules[line][n]; };
        var colGet = function (n) { return modules[n][line]; };
        for (var s = 0; s + 11 <= size; s++) {
          if (matches(rowGet, s, A) || matches(rowGet, s, B)) score += 40;
          if (matches(colGet, s, A) || matches(colGet, s, B)) score += 40;
        }
      })(line);
    }

    // Rule 4 — deviation of the dark-module share away from 50%.
    var dark = 0;
    for (var y = 0; y < size; y++) for (var x = 0; x < size; x++) dark += modules[y][x];
    var percent = (dark * 100) / (size * size);
    score += Math.floor(Math.abs(percent - 50) / 5) * 10;

    return score;
  }

  /* ------------------------------------------------------------------ public */

  /**
   * Encode `text` and return { version, size, modules } where modules is a
   * size x size array of 0/1 rows. The mask is chosen by the standard penalty
   * score, so output matches any conforming encoder module for module.
   */
  function encode(text, options) {
    options = options || {};
    var ecc = options.ecc || 'M';
    if (!ECC_TABLE[ecc]) throw new Error('Unsupported ECC level: ' + ecc);

    var bytes = utf8Bytes(String(text));
    var version = options.version || chooseVersion(bytes.length, ecc, options.minVersion);
    if (version < 1) {
      throw new Error('Payload of ' + bytes.length + ' bytes exceeds the version 10 capacity');
    }

    var codewords = interleave(encodeData(bytes, version, ecc), version, ecc);
    var base = buildFunctionPatterns(version);

    var best = null;
    var firstMask = options.mask == null ? 0 : options.mask;
    var lastMask = options.mask == null ? 7 : options.mask;
    for (var mask = firstMask; mask <= lastMask; mask++) {
      var modules = base.modules.map(function (row) { return row.slice(); });
      placeData(modules, base.reserved, codewords, mask);
      placeFormat(modules, ecc, mask);
      var score = penalty(modules);
      if (!best || score < best.score) best = { score: score, modules: modules, mask: mask };
    }

    return { version: version, size: base.size, mask: best.mask, modules: best.modules };
  }

  /**
   * Render `text` as a standalone SVG string. Dark modules are merged into
   * horizontal runs so the path stays small and prints crisply at label size.
   */
  function toSvg(text, options) {
    options = options || {};
    var quiet = options.quiet == null ? 4 : options.quiet;
    var result = encode(text, options);
    var span = result.size + quiet * 2;

    var path = [];
    for (var r = 0; r < result.size; r++) {
      var c = 0;
      while (c < result.size) {
        if (!result.modules[r][c]) { c++; continue; }
        var start = c;
        while (c < result.size && result.modules[r][c]) c++;
        path.push('M' + (start + quiet) + ' ' + (r + quiet) + 'h' + (c - start) + 'v1h' + -(c - start) + 'z');
      }
    }

    var size = options.size ? ' width="' + options.size + '" height="' + options.size + '"' : '';
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + span + ' ' + span + '"' + size +
      ' shape-rendering="crispEdges" role="img" aria-label="QR code">' +
      '<rect width="' + span + '" height="' + span + '" fill="#ffffff"/>' +
      '<path d="' + path.join('') + '" fill="#000000"/></svg>';
  }

  return {
    encode: encode,
    toSvg: toSvg,
    // Exposed so test/verify_qr.js can check the stages independently.
    _internals: {
      rsRemainder: rsRemainder,
      encodeData: encodeData,
      interleave: interleave,
      buildFunctionPatterns: buildFunctionPatterns,
      MASKS: MASKS
    }
  };
});

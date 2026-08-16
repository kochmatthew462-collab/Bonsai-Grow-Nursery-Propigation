/*
 * Emit QR matrices from js/qrcode.js as JSON on stdout, for verify_qr.py to
 * decode and cross-check. Also self-checks that automatic version selection
 * always lands on the smallest version that fits.
 */
'use strict';

const path = require('path');
const QR = require(path.join(__dirname, '..', 'js', 'qrcode.js'));

const TEXTS = [
  'A',
  'bonsai',
  'https://example.com/#/p/a1',
  'https://kochmatthew462-collab.github.io/bonsai-grow-nursery-propigation/#/p/k3m9x2',
  '0123456789'.repeat(4),
  "Juniperus procumbens 'Nana' - 2019 nursery stock",
  'pH 6.4 / moisture 3 / growth +2mm',
  'x'.repeat(100),
  'y'.repeat(150),
  'z'.repeat(200)
];

const cases = [];
for (const text of TEXTS) {
  for (const ecc of ['L', 'M']) {
    for (let version = 1; version <= 10; version++) {
      let result;
      try {
        result = QR.encode(text, { ecc, version });
      } catch (error) {
        continue; // does not fit this version
      }
      cases.push({
        text,
        ecc,
        version,
        size: result.size,
        mask: result.mask,
        rows: result.modules.map((row) => row.join('')),
        reserved: QR._internals
          .buildFunctionPatterns(version)
          .reserved.map((row) => row.map((v) => (v ? 1 : 0)).join(''))
      });
    }
  }
}

// Automatic version selection must pick the smallest version that fits.
const versionProblems = [];
for (const ecc of ['L', 'M']) {
  for (let length = 1; length <= 200; length++) {
    const text = 'a'.repeat(length);
    const auto = QR.encode(text, { ecc });
    if (auto.version === 1) continue;
    let smallerFits = true;
    try {
      QR.encode(text, { ecc, version: auto.version - 1 });
    } catch (error) {
      smallerFits = false;
    }
    if (smallerFits) {
      versionProblems.push(`${ecc} len ${length}: chose v${auto.version}, v${auto.version - 1} also fits`);
    }
  }
}

process.stdout.write(JSON.stringify({ cases, versionProblems }));

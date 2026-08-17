/*
 * Care profiles — the target envelope a plant is judged against.
 *
 * Every number here is transcribed from one of three handbooks:
 *
 *   BENCH   Bonsai Bench Environment Packet (Aug 2026) — median card and
 *           per-species temperature and soil envelopes for the indoor bench.
 *   BOOK    The Complete Bonsai Grower — class defaults: substrate pH, leachate
 *           EC by development phase, VWC trigger, light by class, winter floors.
 *   TREE    The Arbequina Olive in Central Maryland, and Bergamot in Central
 *           Maryland — both written for ZIP 20833, USDA zone 7b.
 *
 * Where a species handbook and a class default disagree, the species handbook
 * wins and the disagreement is recorded in the profile's notes. Bands are
 * three-tier, mirroring the bench packet's colour code: good (target zone),
 * warn (act soon), outside both (correct now).
 *
 * Several targets are seasonal — a bergamot's winter rest wants 45–58 °F and
 * its summer wants nothing of the kind — so a band may carry a `rest` variant
 * that applies during the profile's restMonths.
 */
(function (global) {
  'use strict';

  /* Numeric factors the app can record. Light and chill share a palette slot
     because no profile tracks both; vigor is the book's quarterly 1-5 audit. */
  var METRICS = {
    ph:       { key: 'ph',       label: 'pH',          unit: '',      decimals: 1, color: 'var(--series-ph)',       step: '0.1', hint: 'pour-through leachate' },
    moisture: { key: 'moisture', label: 'Moisture',    unit: '%',     decimals: 0, color: 'var(--series-moisture)', step: '1',   hint: 'capacitance probe to mid-pot (VWC)' },
    ec:       { key: 'ec',       label: 'EC',          unit: 'mS/cm', decimals: 2, color: 'var(--series-ec)',       step: '0.1', hint: 'leachate, same pour-through sample' },
    growth:   { key: 'growth',   label: 'Growth',      unit: 'mm',    decimals: 0, color: 'var(--series-growth)',   step: '1',   hint: 'trunk caliper at the base — same measure each time' },
    tempLow:  { key: 'tempLow',  label: 'Low temp',    unit: '°F',    decimals: 0, color: 'var(--series-templow)',  step: '1',   hint: 'coldest at pot level since the last check' },
    tempHigh: { key: 'tempHigh', label: 'High temp',   unit: '°F',    decimals: 0, color: 'var(--series-temphigh)', step: '1',   hint: 'warmest since the last check' },
    humidity: { key: 'humidity', label: 'Humidity',    unit: '%',     decimals: 0, color: 'var(--series-humidity)', step: '1',   hint: 'relative humidity at the tree' },
    light:    { key: 'light',    label: 'Light',       unit: 'lux',   decimals: 0, color: 'var(--series-light)',    step: '100', hint: 'lux meter at the canopy, midday' },
    chill:    { key: 'chill',    label: 'Chill hours', unit: 'h',     decimals: 0, color: 'var(--series-chill)',    step: '1',   hint: 'running hours below 45 °F this winter' },
    vigor:    { key: 'vigor',    label: 'Vigor',       unit: '/5',    decimals: 0, color: 'var(--series-vigor)',    step: '1',   hint: 'quarterly audit, 1-5 — no styling below 4' },
    height:   { key: 'height',   label: 'Height',      unit: 'in',    decimals: 1, color: 'var(--series-height)',   step: '0.5', hint: 'soil line to apex' },
    canopy:   { key: 'canopy',   label: 'Canopy',      unit: 'in',    decimals: 0, color: 'var(--series-canopy)',   step: '1',   hint: 'widest spread; measure the same axis each time' },
    percolation: { key: 'percolation', label: 'Percolation', unit: 's', decimals: 0, color: 'var(--series-percolation)', step: '1', hint: 'seconds for surface water to clear — the book’s monthly test' }
  };

  var PAIRED_CHARTS = [{ id: 'temp', title: 'Air temperature', keys: ['tempLow', 'tempHigh'], unit: '°F', decimals: 0 }];

  // The book's vigor rubric, used for the 1-5 audit.
  var VIGOR_RUBRIC = [
    '1 — declining: little or no extension, thin pale foliage, dieback. Hospital culture only.',
    '2 — weak: short extension, small leaves. Recover before any work.',
    '3 — steady: modest extension, even colour. Light work only.',
    '4 — strong: full flush, good colour, abundant buds. Licenses structural work.',
    '5 — vigorous: repeated flushes, fat account. Licenses defoliation and heavy work.'
  ];

  /* Leachate EC by development phase — BOOK. The plant's stage picks the band. */
  var EC_BY_PHASE = {
    development: { good: [1.0, 1.4], warn: [0.6, 2.0] },
    refinement:  { good: [0.6, 1.0], warn: [0.4, 2.0] },
    maintenance: { good: [0.4, 0.8], warn: [0.3, 2.0] }
  };


  /*
   * The bench drip programme. There is no way to ask the GrowHub outlet how
   * much water it delivered — it is a smart switch, and it reports on/off, not
   * volume — so delivered water is DERIVED: emitters x calibrated flow x
   * runtime, on the days the recipe runs. The packet's catch-cup pass (lift the
   * staked lines into cups, run 2 minutes, mL / 2 = mL per minute per emitter)
   * is what turns the nominal figure below into a measured one.
   *
   * days: 0 = Sunday. Sunday is never scheduled — it is the hand-watering day.
   */
  var BENCH_DRIP = {
    nominalMlPerMin: 11.7,   // 0.7 L/hr per emitter, the kit's nominal figure
    seasons: [
      { label: 'Winter', from: '11-01', to: '03-14', days: [2, 5],             minutes: 6, lightHours: 12 },
      { label: 'Spring', from: '03-15', to: '05-31', days: [1, 3, 5],          minutes: 8, lightHours: 14 },
      { label: 'Summer', from: '06-01', to: '09-15', days: [1, 2, 3, 4, 5, 6], minutes: 8, lightHours: 16 },
      { label: 'Autumn', from: '09-16', to: '10-31', days: [1, 3, 5],          minutes: 8, lightHours: 14 }
    ]
  };

  var PROFILES = [
    {
      id: 'generic',
      name: 'No profile',
      scientific: '',
      setting: 'any',
      summary: 'Records readings without judging them against a target band. Pick a specific profile to get in-band status, shaded targets and the month-by-month calendar.',
      track: ['ph', 'moisture', 'growth'],
      bands: {},
      watch: []
    },

    /* ------------------------------------------------ indoor bonsai bench */
    {
      id: 'bench-median',
      tasks: [
        { id: 'chg-spring', from: '03-15', to: '03-22', category: 'system', title: 'Spring changeover',
          body: 'Lights 12 to 14 h. Humidifier 3 to 2 sessions. Drip to M/W/F, 8 min. Unclamp the pomegranate as buds move. Move all four systems together.' },
        { id: 'chg-summer', from: '06-01', to: '06-08', category: 'system', title: 'Peak-season changeover',
          body: 'Lights 14 to 16 h. Humidifier 2 to 1 session. Drip to Mon-Sat. Arm the heat-pulse habit for days above 85 F.' },
        { id: 'chg-autumn', from: '09-16', to: '09-23', category: 'system', title: 'Autumn changeover',
          body: 'Lights 16 to 14 h. Humidifier 1 to 2 sessions. Drip back to M/W/F. Last wiring of the year.' },
        { id: 'chg-winter', from: '11-01', to: '11-08', category: 'system', title: 'Winter changeover',
          body: 'Lights 14 to 12 h. Humidifier 2 to 3 sessions. Drip to Tue/Fri, 6 min. Clamp the pomegranate. Feed to winter rates.' },
        { id: 'lux-audit', from: '01-05', to: '01-31', category: 'measure', title: 'Annual lux audit',
          body: 'Re-meter lux at every canopy. LEDs depreciate: drop the strips an inch or add a third strip when the top shelf can no longer reach 8,000 lux.' },
        { id: 'descale', from: '12-01', to: '12-31', category: 'system', title: 'Descale the humidifier',
          body: 'Monthly through the season, but do not skip the winter one: 1:1 white vinegar, 30 min, rinse well. Distilled or filtered water only.' },
        { id: 'calibrate-drip', from: '04-01', to: '04-30', category: 'system', title: 'Catch-cup calibration',
          body: 'Lift all staked lines into cups, manual-run exactly 2 minutes, measure each cup: mL divided by 2 is mL per minute per emitter. Enter it on each plant so the auto-logged water volumes are real rather than nominal. Re-run after any repot, substrate or line change.' }
      ],
      drip: { emitters: 2, winterEmitters: 2, schedule: BENCH_DRIP },
      name: 'Bonsai bench — median program',
      scientific: 'shared circuit, USDA zone 7b indoor bench',
      setting: 'indoor',
      source: 'Bench Environment Packet, with class defaults from The Complete Bonsai Grower',
      summary: 'The one set of numbers a single-circuit bench runs on. Every tree sharing the light, drip, humidifier and probe is judged against this median; the per-species profiles carry the tolerances.',
      track: ['ph', 'moisture', 'ec', 'percolation', 'growth', 'height', 'canopy', 'tempLow', 'tempHigh', 'humidity', 'light', 'vigor'],
      restMonths: [10, 11, 0, 1, 2],
      winterFloor: { tempF: 55, note: 'Bench cold floor 55 °F — never below, any tree. Governed by the Gmelina.' },
      bands: {
        ph:       { good: [6.0, 6.5], warn: [5.8, 7.0], target: 6.3, note: 'BOOK class default for a general mix is 5.5–6.5; the bench runs the tighter 6.0–6.5.' },
        moisture: { good: [35, 65],   warn: [30, 75],   target: 50,
                    note: 'BENCH meter convention for the akadama–pumice–lava mix: running 35–65%, water at 33%. NOTE: the BOOK quotes a 20–28% VWC trigger — a different scale for the same thing. These bench numbers follow the packet written for this bench and its probe; do not mix the two conventions.' },
        ec:       { good: [0.5, 1.5], warn: [0.3, 2.0], note: 'BOOK leachate band 0.5–1.5; flush above 2.0. Development-phase trees run at the top of it.' },
        percolation: { good: [0, 5], warn: [0, 15], note: 'Book test: 5-second pass, 15-second fail. A pot that ponds past 15 s goes on the repot list — mixes die by collapse, not by calendar.' },
        tempLow:  { good: [62, 68],   warn: [55, 72],   note: 'Tropicals stall below 55 °F nights.' },
        tempHigh: { good: [72, 78],   warn: [65, 85] },
        humidity: { good: [50, 65],   warn: [45, 70],   note: 'Winter floor 45%. Sustained above 70% is fungus risk.' },
        light:    { good: [8000, 12000], warn: [7500, 13000], note: 'Bench hardware target ≈120–180 PPFD. BOOK wants 25,000–60,000 lux for tropicals summered outdoors.' },
        vigor:    { good: [4, 5],     warn: [3, 5],     note: 'No styling work below vigor 4.' }
      },
      calendar: [
        { month: 'Jan', where: 'Bench', water: 'Tue · Fri, 6 min', feed: '¼× monthly', action: 'Winter program: 12 h light, 3 humidifier sessions. Lux audit.' },
        { month: 'Feb', where: 'Bench', water: 'Tue · Fri, 6 min', feed: '¼× monthly', action: 'Parrot’s beak structural cuts before the spring push.' },
        { month: 'Mar', where: 'Bench', water: '→ M·W·F, 8 min', feed: 'Resume ½× weekly', action: 'Mar 15 changeover: light 12→14 h, humidifier 3→2, unclamp the pomegranate.' },
        { month: 'Apr', where: 'Bench', water: 'M·W·F, 8 min', feed: '½× weekly', action: 'Pellets top-dressed on the Gmelina. Pomegranate repot at bud swell.' },
        { month: 'May', where: 'Bench', water: 'M·W·F, 8 min', feed: '½× weekly', action: 'Schefflera hard cutback; schefflera and ficus repot window.' },
        { month: 'Jun', where: 'Bench', water: '→ Mon–Sat, 8 min', feed: '½× weekly', action: 'Jun 1 changeover: light 14→16 h, humidifier 2→1. Ficus defoliation late in the month.' },
        { month: 'Jul', where: 'Bench', water: 'Mon–Sat, 8 min', feed: '½× weekly', action: 'Peak growth. Wire watch every two weeks — it bites fast in season.' },
        { month: 'Aug', where: 'Bench', water: 'Mon–Sat, 8 min', feed: '½× weekly', action: 'Pinch and ramify. Heat pulse on days above 85 °F.' },
        { month: 'Sep', where: 'Bench', water: '→ M·W·F, 8 min', feed: '½× weekly', action: 'Sep 16 changeover: light 16→14 h, humidifier 1→2. Last wiring of the year.' },
        { month: 'Oct', where: 'Bench', water: 'M·W·F, 8 min', feed: 'Taper', action: 'Tidy; recalibrate emitters after any repot.' },
        { month: 'Nov', where: 'Bench', water: '→ Tue · Fri, 6 min', feed: '→ ¼× monthly', action: 'Nov 1 changeover: light 14→12 h, humidifier 2→3, clamp the pomegranate.' },
        { month: 'Dec', where: 'Bench', water: 'Tue · Fri, 6 min', feed: '¼× monthly', action: 'Rest scan. Pomegranate structural pruning while leafless. Descale the humidifier.' }
      ],
      watch: [
        { title: 'Sunday is the reading day', body: 'Moisture on every tree, pH and EC on the first Sunday of the month, both from the same pour-through sample. Wednesday is a moisture spot-check only.' },
        { title: 'The probe is a conservative sentinel', body: 'It sits in the top box — the warmest, driest shelf. When it reads on target, every shelf below is at or above target. Correct to the probe.' },
        { title: 'Measure, do not guess', body: 'Lux at the canopy, pH and EC in the leachate, moisture in the core. Calibrate the pH pen monthly against 7.0 and 4.0 buffer; a dying moisture meter reads dry and will make you overwater.' },
        { title: 'EC governs the feed, not the calendar', body: 'Under 0.5 in season, step the dose up a notch. Over 2.0, flush two to three pot volumes and skip the next feed. Slow-release pellets count toward EC.' },
        { title: 'Quarantine anything new for 3–4 weeks', body: 'Physically separated, own saucer, own tools, with a soap-and-oil pass at day 1 and day 10 before it joins the circuit. Disease rides on steel — 70% isopropyl between trees, every session.' },
        { title: 'One insult per season per tree', body: 'Repot or defoliate or hard structural work — never stacked. And no styling at all on a tree scoring below vigor 4.' }
      ]
    },
    {
      id: 'parrots-beak',
      tasks: [
        { id: 'pb-struct', from: '02-01', to: '02-28', category: 'prune', title: 'Structural cuts',
          body: 'Before the spring push. Mind the spines. Wire semi-lignified shoots in summer instead.' },
        { id: 'pb-pellets-1', from: '04-01', to: '04-07', category: 'feed', title: 'Top-dress slow-release pellets',
          body: 'Heaviest feeder on the bench. Pellets count toward EC, so read the meter, not the calendar.' },
        { id: 'pb-pellets-2', from: '07-01', to: '07-07', category: 'feed', title: 'Second pellet top-dress', body: 'As April.' },
        { id: 'pb-repot', from: '06-01', to: '06-30', category: 'repot', title: 'Repot window',
          body: 'Early summer, night lows at or above 70 F, every 1-2 years. Shade until new leaves emerge.' }
      ],
      drip: { emitters: 2, winterEmitters: 2, schedule: BENCH_DRIP },
      name: "Parrot's beak",
      scientific: 'Gmelina philippensis · tropical',
      setting: 'indoor',
      source: 'Bench Environment Packet',
      summary: 'Fast, thirsty, heavy feeder; warmth-loving. Governs the bench cold floor at 55 °F and takes the warmest upper shelf.',
      track: ['ph', 'moisture', 'ec', 'percolation', 'growth', 'height', 'canopy', 'tempLow', 'tempHigh', 'humidity', 'vigor'],
      restMonths: [10, 11, 0, 1, 2],
      winterFloor: { tempF: 55, note: 'Stress floor 55 °F. Growth stalls below ~65 °F; foliage damage below 45 °F.' },
      bands: {
        ph:       { good: [6.0, 6.8], warn: [5.8, 7.0] },
        moisture: { good: [45, 65],   warn: [35, 75],   note: 'Bench meter scale. Water at 35–40%; the wettest tree on the bench and never let it go fully dry.' },
        ec:       { good: [1.0, 1.5], warn: [0.6, 2.0], note: 'Heaviest feeder on the bench; development-phase rates.' },
        percolation: { good: [0, 5], warn: [0, 15], note: 'Book test: 5-second pass, 15-second fail. A pot that ponds past 15 s goes on the repot list — mixes die by collapse, not by calendar.' },
        tempLow:  { good: [62, 70],   warn: [55, 74] },
        tempHigh: { good: [70, 85],   warn: [65, 88] },
        humidity: { good: [50, 65],   warn: [45, 70] },
        vigor:    { good: [4, 5],     warn: [3, 5] }
      },
      watch: [
        { title: 'It sets the bench floor', body: 'Growth stalls below about 65 °F and foliage is damaged below 45 °F. Give it the warmest, highest shelf.' },
        { title: 'Heaviest feeder on the bench', body: 'Alternate full- and half-strength Sundays, or half-strength weekly plus slow-release pellets top-dressed Apr 1 and Jul 1.' },
        { title: 'Mind the spines when pinching', body: 'Cut shoots back to 2–3 leaves once they run 6–8, and deadhead spent bracts. Wire semi-lignified shoots in summer; pads set fast.' }
      ]
    },
    {
      id: 'hawaiian-umbrella',
      tasks: [
        { id: 'hu-cutback', from: '05-01', to: '06-30', category: 'prune', title: 'Hard cutback window',
          body: 'Scissors only. Remove oversized leaves at the petiole; direct with guy-lines and light.' },
        { id: 'hu-repot', from: '05-01', to: '06-30', category: 'repot', title: 'Repot window', body: 'Late spring, every 2 years.' },
        { id: 'hu-aerial', from: '06-01', to: '08-31', category: 'prune', title: 'Aerial-root campaign',
          body: 'Chamber this tree individually above 70% RH rather than raising humidity for the whole bench.' }
      ],
      drip: { emitters: 2, winterEmitters: 2, schedule: BENCH_DRIP },
      name: 'Hawaiian umbrella',
      scientific: 'Schefflera arboricola · tropical',
      setting: 'indoor',
      source: 'Bench Environment Packet',
      summary: 'The most forgiving tree on the bench. Scissors-only styling — conventional wire fails on this species.',
      track: ['ph', 'moisture', 'ec', 'percolation', 'growth', 'height', 'canopy', 'tempLow', 'tempHigh', 'humidity', 'vigor'],
      restMonths: [10, 11, 0, 1, 2],
      winterFloor: { tempF: 50, note: 'Stress floor 50 °F — the most tolerant tree on the bench.' },
      bands: {
        ph:       { good: [6.0, 6.5], warn: [5.8, 7.0] },
        moisture: { good: [40, 60],   warn: [30, 70],   note: 'Bench meter scale. Water at 30–35%; likes a slight dry-down between waterings.' },
        ec:       { good: [0.6, 1.2], warn: [0.4, 2.0] },
        percolation: { good: [0, 5], warn: [0, 15], note: 'Book test: 5-second pass, 15-second fail. A pot that ponds past 15 s goes on the repot list — mixes die by collapse, not by calendar.' },
        tempLow:  { good: [60, 68],   warn: [50, 72] },
        tempHigh: { good: [65, 80],   warn: [60, 85] },
        humidity: { good: [50, 65],   warn: [45, 70] },
        vigor:    { good: [4, 5],     warn: [3, 5] }
      },
      watch: [
        { title: 'Drops leaflets on sudden swings', body: 'Steady cool it tolerates; abrupt change it does not. Check it first after any HVAC changeover week.' },
        { title: 'Scissors only', body: 'Conventional wire fails on this species — direct it with guy-lines and light. Hard cutbacks May–June.' },
        { title: 'Pushes aerial roots above 70% RH', body: 'Chamber this tree individually for an aerial-root campaign rather than raising humidity for the whole bench.' }
      ]
    },
    {
      id: 'ginseng-ficus',
      tasks: [
        { id: 'gf-defol', from: '06-20', to: '06-30', category: 'prune', title: 'Defoliation window',
          body: 'Full or partial, late June, healthy trees only (vigor 4-5). Large cuts heal fastest in warmth. Never stack this with a repot in the same year.' },
        { id: 'gf-repot', from: '05-01', to: '07-31', category: 'repot', title: 'Repot window', body: 'Late spring to summer, every 2 years.' },
        { id: 'gf-emitter', from: '01-01', to: '12-31', category: 'system', title: 'Rotate the single emitter',
          body: 'Monthly. One emitter over the densest roots, moved so it does not channel.' },
        { id: 'gf-suckers', from: '03-01', to: '10-31', category: 'prune', title: 'Graft-line sucker check',
          body: 'Through the growing season. Anything below the graft is rootstock and will replace the scion.' }
      ],
      drip: { emitters: 1, winterEmitters: 1, schedule: BENCH_DRIP, note: 'Single emitter over the densest roots — rotate its position monthly.' },
      name: 'Ginseng grafted ficus',
      scientific: 'Ficus microcarpa · tropical',
      setting: 'indoor',
      source: 'Bench Environment Packet, with mix chemistry from The Complete Bonsai Grower',
      summary: 'Steady and reliable, but hates cold drafts and being moved. Grafted — the graft line needs watching.',
      track: ['ph', 'moisture', 'ec', 'percolation', 'growth', 'height', 'canopy', 'tempLow', 'tempHigh', 'humidity', 'vigor'],
      restMonths: [10, 11, 0, 1, 2],
      winterFloor: { tempF: 59, note: 'Chill drafts under 59 °F trigger leaf drop.' },
      bands: {
        ph:       { good: [6.0, 6.5], warn: [5.8, 7.0], note: 'BOOK ficus mix chemistry: pH 6.0–6.5, EC 0.8–1.5.' },
        moisture: { good: [40, 60],   warn: [30, 70],   note: 'Bench meter scale. Water at 30–40%; even moisture, brief dry-downs fine.' },
        ec:       { good: [0.8, 1.5], warn: [0.4, 2.0] },
        percolation: { good: [0, 5], warn: [0, 15], note: 'Book test: 5-second pass, 15-second fail. A pot that ponds past 15 s goes on the repot list — mixes die by collapse, not by calendar.' },
        tempLow:  { good: [62, 70],   warn: [59, 74] },
        tempHigh: { good: [68, 85],   warn: [64, 88] },
        humidity: { good: [50, 65],   warn: [45, 70] },
        vigor:    { good: [4, 5],     warn: [3, 5] }
      },
      watch: [
        { title: 'Remove understock suckers below the graft', body: 'Anything shooting from below the graft line is rootstock and will outcompete the scion if left. Cuttings from this tree grow on their own roots and have no graft line at all.' },
        { title: 'Chill drafts under 59 °F trigger leaf drop', body: 'Keep it clear of window cracks and vent blasts. It also resents being moved — pick a spot and leave it.' },
        { title: 'Wire bites fast', body: 'It holds well but inspect every two weeks in season. Wipe the latex from cuts before it seals dirty. Large cuts heal fastest in warmth.' }
      ]
    },
    {
      id: 'dwarf-pomegranate',
      tasks: [
        { id: 'dp-struct', from: '12-01', to: '02-28', category: 'prune', title: 'Structural pruning while leafless',
          body: 'Dec-Feb, when the lines show. Old wood is brittle: water the day before wiring.' },
        { id: 'dp-repot', from: '03-10', to: '03-31', category: 'repot', title: 'Repot at bud swell',
          body: 'Early spring, roughly mid-March, every 2-3 years. Its share of the mix can run 10% leaner on organics.' },
        { id: 'dp-unclamp', from: '03-15', to: '03-25', category: 'system', title: 'Unclamp the drip',
          body: 'As buds move. Two emitters back on; auto-logging resumes with them.' },
        { id: 'dp-thin', from: '06-01', to: '07-31', category: 'prune', title: 'Thin fruit to 2-3',
          body: 'Blooms come on new wood tips, so leave those shoots unpinched. Suspend feed while flowers are open.' },
        { id: 'dp-clamp', from: '11-01', to: '11-10', category: 'system', title: 'Clamp the drip for winter',
          body: 'Fold each branch line back and clip; hand-water every 7-10 days through the rest. Keep 1 emitter live if it overwinters warm and in leaf.' }
      ],
      drip: { emitters: 2, winterEmitters: 0, schedule: BENCH_DRIP, note: 'Winter bypass: lines clamped, hand-water every 7-10 days. Keep 1 emitter live instead if it overwinters warm and in leaf.' },
      name: 'Dwarf pomegranate',
      scientific: 'Punica granatum var. nana · subtropical',
      setting: 'indoor',
      source: 'Bench Environment Packet, with winter floor from The Complete Bonsai Grower',
      summary: 'The driest and coolest tree on the bench, and its sun-hunger canary. Wants a leaner, dimmer winter rest.',
      track: ['ph', 'moisture', 'ec', 'percolation', 'growth', 'height', 'canopy', 'tempLow', 'tempHigh', 'humidity', 'vigor'],
      restMonths: [10, 11, 0, 1, 2],
      winterFloor: { tempF: 30, note: 'BOOK: protect roots below 28–30 °F; a brief 25 °F is survivable. A cool bright rest at 35–50 °F is optional, not required.' },
      bands: {
        ph:       { good: [5.5, 7.0], warn: [5.2, 7.4] },
        moisture: { good: [35, 55],   warn: [25, 65],   note: 'Bench meter scale. Water at 25–35%; driest tree on the bench and rot-prone if wet.' },
        ec:       { good: [0.6, 1.2], warn: [0.4, 2.0] },
        percolation: { good: [0, 5], warn: [0, 15], note: 'Book test: 5-second pass, 15-second fail. A pot that ponds past 15 s goes on the repot list — mixes die by collapse, not by calendar.' },
        tempLow:  { good: [60, 68],   warn: [41, 72],
                    rest: { good: [35, 50], warn: [30, 60], note: 'Optional cool bright rest, Nov–Feb.' } },
        tempHigh: { good: [65, 85],   warn: [60, 88] },
        humidity: { good: [45, 65],   warn: [40, 70] },
        vigor:    { good: [4, 5],     warn: [3, 5] }
      },
      watch: [
        { title: 'It flags first when light falls short', body: 'Treat it as the bench light meter: if the pomegranate stretches, every tree is underlit.' },
        { title: 'Winter is a bypass, not a drought', body: 'Drip clamped, hand-water every 7–10 days through the rest. If it overwinters warm and in leaf, keep one emitter live instead.' },
        { title: 'Blooms come on new wood tips', body: 'Trim new shoots at 4–6 leaves except those left to flower. Thin fruit to 2–3. Suspend feed while flowers are open. Structural pruning belongs in the leafless rest, Dec–Feb.' }
      ]
    },

    /* --------------------------------------------- container trees, ZIP 20833 */
    {
      id: 'bergamot',
      transitions: {
        acclimationDays: 10,
        fall: {
          window: ['10-15', '10-20'],
          moveAtLow: 48,
          damageLow: 32,
          note: 'Bring it in when overnight lows settle into the 45-50 F band. Foliage and fruit take chill damage below 32 F, and cold media slows root uptake, which is what produces the leaf drop indoors.'
        },
        spring: {
          window: ['05-01', '05-10'],
          moveAboveLow: 50,
          note: 'Out only when nights hold reliably above 50 F. The average last frost is mid-April, but spring cold snaps linger; early May protects tender new growth and gives warm media.'
        }
      },
      tasks: [
        { id: 'bg-prune', from: '02-01', to: '02-28', category: 'prune', title: 'Structural pruning',
          body: 'During the cool rest. Max 20-25% canopy removal per year. Scaffolds 3-5 at 45-60 degree crotch angles, headed 24-30 in above the media.' },
        { id: 'bg-ph-spring', from: '03-25', to: '04-10', category: 'measure', title: 'Test media pH (spring)',
          body: 'Twice-yearly test, before the spring flush. Slurry or pour-through; also read runoff EC. Target media pH 6.0-6.5.' },
        { id: 'bg-micro', from: '03-01', to: '03-31', category: 'feed', title: 'Micronutrient foliar',
          body: 'And resume feeding. 3:1:1 or 2:1:1 N:P:K with micronutrients, 100-150 ppm N in active growth.' },
        { id: 'bg-repot', from: '04-01', to: '04-30', category: 'repot', title: 'Root prune / media refresh if due',
          body: 'Every 2-3 years, in April only. Avoid September through February: transplanting into declining light is how young citrus are lost.' },
        { id: 'bg-harden', from: '04-21', to: '05-01', category: 'move', title: 'Begin hardening off',
          body: 'Two weeks of graduated light and temperature before the move. Skipping this is the usual cause of a bergamot going bare.' },
        { id: 'bg-out', from: '05-01', to: '05-10', category: 'move', title: 'Move outdoors',
          body: 'When nights are reliably above 50 F. Peak bloom follows: do not let it dry out. (Transition schedule window; the handbook says May 10-20. Watch the forecast rather than the date - the weather card holds it indoors if any of the next five nights fall below 50 F.)' },
        { id: 'bg-thin', from: '06-01', to: '06-30', category: 'prune', title: 'Thin fruit after June drop',
          body: '1 fruit per 20-25 leaves. Mature load is 15-30 on a 5-6 ft tree. Pinch the flush.' },
        { id: 'bg-n-stop', from: '08-15', to: '08-15', category: 'feed', title: 'Final nitrogen date',
          body: 'Hard stop. Potassium only after this, so growth hardens before the move indoors.' },
        { id: 'bg-pest', from: '09-01', to: '09-30', category: 'pest', title: 'Pre-move pest treatments',
          body: 'Treat before it joins the indoor station, not after. Scale, mealybug, mites.' },
        { id: 'bg-ph-autumn', from: '09-25', to: '10-10', category: 'measure', title: 'Test media pH (autumn)',
          body: 'Second of the two annual tests, at the move indoors. Deep flush 2-3x container volume at the same time.' },
        { id: 'bg-in', from: '10-15', to: '10-20', category: 'move', title: 'Move indoors',
          body: 'Before nights approach 50 F. Expect leaf drop - it stacks the move with falling light. Do not also repot. (Transition schedule window; the handbook says Oct 1-15, so this is the later of the two. The weather card will pull it forward if nights actually drop.)' },
        { id: 'bg-rest', from: '12-01', to: '12-10', category: 'system', title: 'Cool rest begins',
          body: 'Hold 45-58 F, bright, dry and unfertilised for 8-12 weeks. Never below 40 F at pot level. This is what induces next spring\'s bloom.' }
      ],
      name: 'Italian bergamot — container',
      scientific: 'Citrus bergamia · young stem graft · ZIP 20833, zone 7b',
      setting: 'seasonal',
      source: 'Bergamot in Central Maryland',
      summary: 'Outdoors roughly May 10–20 to Oct 1–15, then a cool bright rest indoors at 45–58 °F. The rest is not storage — it is what induces the following spring’s bloom.',
      track: ['ph', 'moisture', 'ec', 'percolation', 'growth', 'height', 'canopy', 'tempLow', 'tempHigh', 'humidity', 'light', 'vigor'],
      restMonths: [10, 11, 0, 1],
      winterFloor: { tempF: 40, note: 'Never below 40 °F at pot level. Frost is fatal to citrus.' },
      bands: {
        ph:       { good: [6.0, 6.5], warn: [5.5, 7.0], target: 6.25,
                    note: 'Handbook target 6.0–6.5. Above ~7.2 (common with hard tap water) acidify irrigation to pH 5.8–6.2; alkalinity drives media pH up over months.' },
        moisture: { good: [20, 28],   warn: [15, 40],
                    note: 'The handbook rule is the finger test — water when the top 2–3 in are dry in summer, the top 3–4 in in winter, with a 20% leaching fraction every time. The band shown is the BOOK class default of 20–28% VWC on a capacitance probe, for when you prefer a meter.' },
        ec:       { good: [0.5, 1.5], warn: [0.3, 2.0],
        percolation: { good: [0, 5], warn: [0, 15], note: 'Book test: 5-second pass, 15-second fail. A pot that ponds past 15 s goes on the repot list — mixes die by collapse, not by calendar.' },
                    note: 'Runoff EC persistently above 2.0 mS/cm means salt accumulation — deep flush 2–3× container volume.' },
        tempLow:  { good: [55, 95],   warn: [50, 100],
                    rest: { good: [45, 58], warn: [40, 62], note: 'Winter rest 45–58 °F; never below 40 °F at pot level.' } },
        tempHigh: { good: [70, 95],   warn: [60, 100] },
        humidity: { good: [40, 60],   warn: [30, 75],
                    rest: { good: [40, 50], warn: [30, 60], note: 'Winter humidity target 40–50%.' } },
        light:    { good: [25000, 80000], warn: [15000, 110000], note: 'Summer: eight or more hours of direct sun. BOOK Mediterranean class wants ≥50,000 lux midday, DLI 25–45.' },
        vigor:    { good: [4, 5],     warn: [3, 5] }
      },
      calendar: [
        { month: 'Jan', where: 'In, cool', water: '2–4 wks', feed: 'None', action: 'Bud induction. Harvest. Plan the year.' },
        { month: 'Feb', where: 'In, cool', water: '2–4 wks', feed: 'None', action: 'Structural pruning.' },
        { month: 'Mar', where: 'In', water: '10–14 d', feed: 'Resume', action: 'Micronutrient foliar. Finish pruning. Test media pH.' },
        { month: 'Apr', where: 'In → out', water: '5–7 d', feed: 'Full', action: 'Root prune if due (every 2–3 yrs). Bud swell, bloom. Begin harden-off.' },
        { month: 'May', where: 'Out', water: '3–5 d', feed: 'Full + Mg', action: 'Move out 10th–20th. Peak bloom. Do not let it dry out.' },
        { month: 'Jun', where: 'Out', water: '2–3 d', feed: 'Full', action: 'June drop, then thin to 1 fruit per 20–25 leaves. Pinch the flush.' },
        { month: 'Jul', where: 'Out', water: 'Daily', feed: 'Full + K', action: 'Peak demand. Fruit sizing.' },
        { month: 'Aug', where: 'Out', water: 'Daily', feed: 'N stops Aug 15', action: 'Potassium only after the 15th. Plan the move indoors.' },
        { month: 'Sep', where: 'Out', water: '2–4 d', feed: 'K only', action: 'Pest treatments. Begin the move sequence.' },
        { month: 'Oct', where: 'In', water: '7–10 d', feed: 'None', action: 'Move in 1st–15th, before nights approach 50 °F. Expect leaf drop. Test media pH. Deep flush.' },
        { month: 'Nov', where: 'In, cooling', water: '10–21 d', feed: 'None', action: 'Scout weekly. Colour break.' },
        { month: 'Dec', where: 'In, cool', water: '2–4 wks', feed: 'None', action: 'Cool rest begins. Harvest.' }
      ],
      watch: [
        { title: 'The cool rest is the whole game', body: 'Winter is not storage. A bright, cool 45–58 °F rest for 8–12 weeks is what induces next spring’s bloom — a bergamot kept comfortable at living-room temperature stays healthy and never flowers. Never let pot-level temperature fall below 40 °F.', severity: 'high' },
        { title: 'Move on the thermometer, not the calendar', body: 'Out when nights are reliably above 50 °F, typically May 10–20. In when nights approach 50 °F, typically Oct 1–15. Log the low each check so the decision is made on numbers.', severity: 'high' },
        { title: 'Transition slowly in both directions', body: 'Two weeks of graduated light and temperature each way. The autumn move is the hard one — it stacks the shock of moving with falling light, and expected leaf drop follows. Do not also repot in that window.', severity: 'high' },
        { title: 'Rootstock suckers below the graft', body: 'Your tree is a graft. Anything emerging below the union is rootstock — often a vigorous trifoliate — and will replace your bergamot if left. Rub or cut flush the moment you see it, and log the check.', severity: 'high' },
        { title: 'Yellow leaves with green veins', body: 'Check in this order: media pH too high, then iron deficiency (foliar chelate), then alkaline irrigation water. Fix the pH before adding any nutrient — chelate treats the symptom. Test media pH twice yearly, early April and early October.' },
        { title: 'Feed to the ratio, and stop on time', body: '3:1:1 or 2:1:1 N:P:K with micronutrients, at 100–150 ppm N in active growth. Final nitrogen date is August 15 — after that potassium only, so growth hardens before the move indoors.' },
        { title: 'Water quality is an input you measure', body: 'Alkalinity under 100 ppm, total hardness under 150, chloride and sodium under 50 ppm each — citrus is notably chloride-sensitive, and softened water is disqualifying. Above 100 ppm alkalinity, acidify with roughly 1–2 tsp white vinegar per gallon.' },
        { title: 'Pests to scout', body: 'Spider mites in dry indoor winter air — raise humidity, rinse the canopy, treat at 5–7 day intervals. Scale and mealybug on stems and in leaf axils. Citrus leaf miner leaves silvery serpentine trails in soft new flush. Aphids on the newest tips.' },
        { title: 'Bergamot oil is phototoxic', body: 'The rind oil causes severe burns on skin later exposed to sunlight. Wear gloves when handling fruit and peel, and keep the oil off skin that will see sun.' }
      ]
    },
    {
      id: 'arbequina-olive',
      transitions: {
        acclimationDays: 10,
        fall: {
          window: ['11-01', '11-10'],
          moveAtLow: 32,
          damageLow: 28,
          chillBonus: [35, 50],
          note: 'Bring it in as nights approach 30-32 F. It tolerates brief light frost, so it stays out later than the citrus — and mild autumn nights in the 35-50 F band are banking the dormancy and chill the crop depends on.'
        },
        spring: {
          window: ['04-01', '04-10'],
          moveAboveLow: 38,
          note: 'Out when nights hold consistently above 35-40 F. Hardier than the citrus in late chills, so it is the first tree back outside.'
        }
      },
      tasks: [
        { id: 'ol-chill-log', from: '11-01', to: '02-28', category: 'measure', title: 'Log chill hours weekly',
          body: 'Running hours below 45 F, plus weeks held at 50-55 F. When the tree does not flower, this log is the first thing to check — always.' },
        { id: 'ol-prune', from: '02-01', to: '02-28', category: 'prune', title: 'Structural pruning, dry weather only',
          body: 'Olive knot enters through fresh wounds and rain splash is the main infection route. Sterilise tools with 70% isopropyl; no wound sealant. Max 20-25% canopy per year; 3-4 scaffolds at 45-60 degrees, headed 24-30 in.' },
        { id: 'ol-feed-on', from: '03-01', to: '03-31', category: 'feed', title: 'Resume feeding at half strength',
          body: 'Balanced fertiliser, half strength, monthly. Deep flush first.' },
        { id: 'ol-repot', from: '04-01', to: '04-30', category: 'repot', title: 'Root prune / media refresh if due',
          body: 'Every 2-3 years, in April.' },
        { id: 'ol-out', from: '04-01', to: '04-10', category: 'move', title: 'Move outdoors',
          body: 'Nights holding consistently above 35-40 F. Harden gradually - an abrupt move into full sun bleaches leaves. (Transition schedule window; the handbook says mid-to-late April, so this is about two weeks earlier. The weather card holds it in if any of the next five nights fall below 38 F.)' },
        { id: 'ol-thin', from: '06-01', to: '06-30', category: 'prune', title: 'Thin fruit',
          body: '1 fruit per 6-8 in of fruiting shoot, on one-year-old wood. Thin, never shear. Heavy flower drop before this is normal — 1-2% set is a good year.' },
        { id: 'ol-peacock', from: '07-01', to: '07-31', category: 'pest', title: 'Scout for peacock spot',
          body: 'Maryland summer humidity is the foliar risk. Dark rings with pale halos, then defoliation. Keep the canopy open, avoid overhead watering, clear fallen leaves.' },
        { id: 'ol-feed-off', from: '08-15', to: '08-15', category: 'feed', title: 'Feeding stops',
          body: 'Hard stop. Excess nitrogen gives long soft shoots and no fruit — the same picture as inadequate chill.' },
        { id: 'ol-harvest', from: '09-01', to: '10-31', category: 'measure', title: 'Harvest window',
          body: 'Green harvest from September, purple and black through October. Bloom to harvest is 4-5 months; mature yield 2-5 lb.' },
        { id: 'ol-in', from: '11-01', to: '11-10', category: 'move', title: 'Move indoors, ahead of a hard freeze',
          body: 'Deep flush first. Then hold 50-55 F for 10-12 weeks, bright, dry and unfertilised, with a fan for air movement and humidity under 50%. Never below 40 F at pot level.' },
        { id: 'ol-verify-space', from: '09-15', to: '10-15', category: 'system', title: 'Verify the winter space holds 50-55 F',
          body: 'Put a thermometer in the candidate space and watch it through a cold snap BEFORE you need it. Too warm (65-72 F) and induction fails as surely as too cold.' }
      ],
      name: 'Arbequina olive — container',
      scientific: "Olea europaea 'Arbequina' · young stem graft · ZIP 20833, zone 7b",
      setting: 'seasonal',
      source: 'The Arbequina Olive in Central Maryland',
      summary: 'Outdoors mid-April to late October, banking chill, then a cool bright winter indoors at 50–55 °F. Chill is what decides whether there is a crop at all — and it fails from being too warm as readily as too cold.',
      track: ['ph', 'moisture', 'ec', 'percolation', 'growth', 'height', 'canopy', 'tempLow', 'tempHigh', 'humidity', 'light', 'chill', 'vigor'],
      restMonths: [10, 11, 0, 1],
      winterFloor: { tempF: 40, note: 'Never below 40 °F at pot level. Young trees are damaged at 25–28 °F; established trees take a brief 15 °F.' },
      bands: {
        ph:       { good: [6.5, 8.5], warn: [6.0, 8.8], target: 7.5,
                    note: 'Media pH 6.5–8.5 — and do not acidify. This is the one tree here that is happy alkaline.' },
        moisture: { good: [15, 25],   warn: [10, 35],
                    note: 'The handbook rule is the finger test — top 2–3 in completely dry before re-watering, 20% leaching fraction. The band shown sits a step below the BOOK class default because this tree wants to dry down further than anything else you track.' },
        ec:       { good: [0.5, 1.5], warn: [0.3, 2.0],
        percolation: { good: [0, 5], warn: [0, 15], note: 'Book test: 5-second pass, 15-second fail. A pot that ponds past 15 s goes on the repot list — mixes die by collapse, not by calendar.' },
                    note: 'Deep flush 2–3× container volume monthly in season, and always before the move indoors and again in early spring.' },
        tempLow:  { good: [50, 95],   warn: [40, 100],
                    rest: { good: [50, 55], warn: [45, 58], note: 'Chill band 50–55 °F sustained. Induction fails at 39 °F and at 64 °F alike.' } },
        tempHigh: { good: [60, 91],   warn: [45, 100], note: 'Fruit set drops sharply above 91 °F during bloom.' },
        humidity: { good: [40, 60],   warn: [30, 70],
                    rest: { good: [40, 50], warn: [30, 50], note: 'Winter humidity under 50% with air movement — run a fan.' } },
        light:    { good: [25000, 80000], warn: [15000, 110000], note: 'Eight or more hours direct. BOOK Mediterranean class: ≥50,000 lux midday, DLI 25–45.' },
        chill:    { good: [200, 400], warn: [150, 600], note: 'Target 200–400 hours below 45 °F, plus 10–12 weeks at 50–55 °F. Under 200 hours, expect up to a 90% reduction in flowering.' },
        vigor:    { good: [4, 5],     warn: [3, 5] }
      },
      calendar: [
        { month: 'Jan', where: 'In, chill', water: '3–5 wks', feed: 'None', action: 'Chill — the crop is decided now. Log it every week.' },
        { month: 'Feb', where: 'In, chill', water: '3–5 wks', feed: 'None', action: 'Structural pruning, dry weather only.' },
        { month: 'Mar', where: 'In', water: '2–3 wks', feed: 'Resume half', action: 'Bud swell. Finish pruning. Deep flush.' },
        { month: 'Apr', where: 'In → out', water: '10–14 d', feed: 'Half', action: 'Root prune if due (every 2–3 yrs). Move out mid-to-late month, nights above 40 °F.' },
        { month: 'May', where: 'Out', water: '7–10 d', feed: 'Half', action: 'Panicles, bloom starts. Do not let it dry out.' },
        { month: 'Jun', where: 'Out', water: '5–7 d', feed: 'Half', action: 'Bloom and set. Heavy flower drop is normal. Thin to 1 fruit per 6–8 in of shoot.' },
        { month: 'Jul', where: 'Out', water: '3–5 d', feed: 'Half', action: 'Pit hardening — peak water. Watch for peacock spot.' },
        { month: 'Aug', where: 'Out', water: '3–5 d', feed: 'Stops Aug 15', action: 'Fruit fill and oil.' },
        { month: 'Sep', where: 'Out', water: '5–7 d', feed: 'None', action: 'Green harvest. Pest treatments.' },
        { month: 'Oct', where: 'Out', water: '2–3 wks', feed: 'None', action: 'Stay out — banking chill. Purple and black harvest.' },
        { month: 'Nov', where: 'In', water: '2–3 wks', feed: 'None', action: 'Move in late Oct – mid Nov, ahead of a hard freeze. Chill begins. Deep flush first.' },
        { month: 'Dec', where: 'In, chill', water: '3–5 wks', feed: 'None', action: 'Chill. Scout weekly.' }
      ],
      watch: [
        { title: 'Chill decides the crop, and it fails from both ends', body: 'The olive needs 200–400 hours below 45 °F, and 10–12 weeks sustained at 50–55 °F, to induce flower buds. Induction fails at 39 °F and at 64 °F alike — a tree kept comfortable in a heated room all winter stays perfectly healthy and never fruits. Never below 40 °F at pot level. When it does not flower, check the chill log first, always.', severity: 'high' },
        { title: 'A winter space, not the open garden', body: 'Best is an unheated garage, shed or cold room holding 45–58 °F with real light and natural day-to-night fluctuation. Left outdoors through a zone 7b winter (5–10 °F design lows) the roots are killed: a container root zone sits at air temperature, 20–30 °F colder than the same tree would experience in the ground.', severity: 'high' },
        { title: 'Overwatering kills more container olives than cold', body: 'Let the top 2–3 in go completely dry before re-watering, and drain sharply. Wilting with wet media is root rot — unpot and inspect, and do not water. Wilting with dry media is simple underwatering: soak from below if the mix has gone hydrophobic.', severity: 'high' },
        { title: 'Rootstock suckers below the graft', body: 'Olives sucker readily from the base. Anything below the union is rootstock and needs removing flush — check every time you water in the growing season, and log it.', severity: 'high' },
        { title: 'Do not acidify', body: 'Media pH 6.5–8.5 is correct for this tree. Chasing it down toward the bonsai bench’s 6.3 is actively wrong here.' },
        { title: 'Olive knot', body: 'Rough woody galls on stems, a bacterial infection entering through fresh wounds with rain splash. Prune only in dry weather — this matters more for olive than citrus. Sterilise tools with 70% isopropyl before starting and after any cut into suspect tissue. No wound sealant: it slows compartmentalisation and traps pathogens.' },
        { title: 'Maryland summer humidity is the foliar risk', body: 'High summer humidity favours peacock spot — dark rings with pale halos, followed by defoliation. Keep the canopy open and airy (the modified open centre form is partly for this), avoid overhead watering, and clear fallen infected leaves rather than leaving them in the pot.' },
        { title: 'Feed lightly and stop on time', body: 'Balanced fertiliser at half strength, monthly, March to August 15 only. Excess nitrogen produces long soft shoots, a dense canopy and no fruit — the same picture as inadequate chill, so check the log before blaming the feed.' },
        { title: 'What normal looks like at bloom', body: 'Wind-pollinated and self-fertile, late May into June. Heavy flower drop is normal — 1–2% set is a good year. Judge the season by what is still holding in July, not by the drop. Set falls sharply above 91 °F, and indoors it needs a fan for air movement.' }
      ]
    }
  ];

  var BY_ID = {};
  PROFILES.forEach(function (p) { BY_ID[p.id] = p; });

  function isRestMonth(profile, date) {
    if (!profile || !profile.restMonths) return false;
    var month = (date || new Date()).getMonth();
    return profile.restMonths.indexOf(month) >= 0;
  }

  /**
   * The band in force for a factor right now. Several targets are seasonal —
   * a bergamot's winter rest wants 45–58 °F and its summer wants nothing of
   * the kind — so a band may carry a `rest` variant used during restMonths.
   */
  function bandFor(profile, key, date) {
    if (!profile || !profile.bands) return null;
    var band = profile.bands[key];
    if (!band) return null;
    if (band.rest && isRestMonth(profile, date)) {
      return {
        good: band.rest.good,
        warn: band.rest.warn || band.rest.good,
        note: band.rest.note || band.note,
        phase: 'winter rest'
      };
    }
    return {
      good: band.good,
      warn: band.warn || band.good,
      note: band.note,
      target: band.target,
      phase: band.rest ? 'growing season' : null
    };
  }

  /** Judge a value against the band in force, on the packet's three tiers. */
  function evaluate(profile, key, value, date) {
    if (value == null) return { level: 'none' };
    var band = bandFor(profile, key, date);
    if (!band || !band.good) return { level: 'none' };
    if (value >= band.good[0] && value <= band.good[1]) {
      return { level: 'good', label: 'In band', band: band };
    }
    if (value >= band.warn[0] && value <= band.warn[1]) {
      return { level: 'warn', label: 'Act soon', band: band };
    }
    return { level: 'bad', label: 'Correct now', band: band };
  }

  /** This month's row of the profile's annual table. */
  function currentMonth(profile, date) {
    if (!profile || !profile.calendar) return null;
    return profile.calendar[(date || new Date()).getMonth()] || null;
  }

  global.BonsaiProfiles = {
    metrics: METRICS,
    pairedCharts: PAIRED_CHARTS,
    vigorRubric: VIGOR_RUBRIC,
    ecByPhase: EC_BY_PHASE,
    all: function () { return PROFILES.slice(); },
    get: function (id) { return BY_ID[id] || BY_ID.generic; },
    evaluate: evaluate,
    bandFor: bandFor,
    isRestMonth: isRestMonth,
    currentMonth: currentMonth
  };
})(window);

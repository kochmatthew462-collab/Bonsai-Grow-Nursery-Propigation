/*
 * Care profiles — the target envelope a plant is judged against.
 *
 * The bench profiles are transcribed from the Koch Nursery "Bonsai Bench
 * Environment Packet" (Aug 2026): median card, per-species temperature
 * envelopes, and per-species soil envelopes. The bergamot and olive profiles
 * are for container-grown, stem-grafted young trees living outdoors, and are
 * general horticultural guidance rather than anything from that packet.
 *
 * Bands are three-tier, mirroring the packet's own colour code:
 *   good  — target zone
 *   warn  — act soon
 *   else  — out of range, correct now
 */
(function (global) {
  'use strict';

  /* Each numeric factor the app can record. Colours come from the validated
     categorical palette; light and chill share a slot because no profile ever
     tracks both (light is an indoor-bench factor, chill an outdoor one). */
  var METRICS = {
    ph:       { key: 'ph',       label: 'pH',          unit: '',      decimals: 1, color: 'var(--series-ph)',       step: '0.1', hint: 'pour-through leachate' },
    moisture: { key: 'moisture', label: 'Moisture',    unit: '%',     decimals: 0, color: 'var(--series-moisture)', step: '1',   hint: 'capacitive probe, same depth each time' },
    ec:       { key: 'ec',       label: 'EC',          unit: 'mS/cm', decimals: 2, color: 'var(--series-ec)',       step: '0.1', hint: 'nutrient load, same pour-through sample' },
    growth:   { key: 'growth',   label: 'Growth',      unit: 'mm',    decimals: 0, color: 'var(--series-growth)',   step: '1',   hint: 'trunk caliper or leader height — same measure each time' },
    tempLow:  { key: 'tempLow',  label: 'Low temp',    unit: '°F',    decimals: 0, color: 'var(--series-templow)',  step: '1',   hint: 'coldest since the last check' },
    tempHigh: { key: 'tempHigh', label: 'High temp',   unit: '°F',    decimals: 0, color: 'var(--series-temphigh)', step: '1',   hint: 'warmest since the last check' },
    humidity: { key: 'humidity', label: 'Humidity',    unit: '%',     decimals: 0, color: 'var(--series-humidity)', step: '1',   hint: 'probe RH in the box' },
    light:    { key: 'light',    label: 'Light',       unit: 'lux',   decimals: 0, color: 'var(--series-light)',    step: '100', hint: 'lux meter at canopy' },
    chill:    { key: 'chill',    label: 'Chill hours', unit: 'h',     decimals: 0, color: 'var(--series-chill)',    step: '1',   hint: 'running hours below 45 °F this winter' }
  };

  // Temperature low and high share one chart: a range, so they take the
  // diverging cool/warm pair rather than two categorical slots.
  var PAIRED_CHARTS = [{ id: 'temp', title: 'Air temperature', keys: ['tempLow', 'tempHigh'], unit: '°F', decimals: 0 }];

  var PROFILES = [
    {
      id: 'generic',
      name: 'No profile',
      scientific: '',
      setting: 'any',
      summary: 'Records readings without judging them against a target band. Pick a specific profile to get in-band status and shaded targets.',
      track: ['ph', 'moisture', 'growth'],
      bands: {},
      watch: []
    },

    /* ---------------------------------------------- indoor bonsai bench */
    {
      id: 'bench-median',
      name: 'Bonsai bench — median program',
      scientific: 'shared circuit, USDA zone 7 indoor bench',
      setting: 'indoor',
      summary: 'The one set of numbers a single-circuit bench runs on. Every tree on the shared light, drip, humidifier and probe is judged against this median; per-species profiles below carry the tolerances.',
      track: ['ph', 'moisture', 'ec', 'growth', 'tempLow', 'tempHigh', 'humidity', 'light'],
      bands: {
        ph:       { good: [6.0, 6.5], warn: [5.8, 7.0], target: 6.3 },
        moisture: { good: [35, 65],   warn: [30, 75],   target: 50, note: 'water at 33% (trigger 30–35)' },
        ec:       { good: [0.8, 1.5], warn: [0.4, 2.0], target: 1.1, note: 'winter eases to 0.4–0.8; flush above 2.0' },
        tempLow:  { good: [62, 68],   warn: [55, 72],   note: 'bench cold floor 55 °F — never below, any tree' },
        tempHigh: { good: [72, 78],   warn: [65, 85] },
        humidity: { good: [50, 65],   warn: [45, 70],   note: 'winter floor 45%; sustained above 70% is fungus risk' },
        light:    { good: [8000, 12000], warn: [7500, 13000], note: '≈120–180 PPFD; 6 in strip-to-canopy is the sweet spot' }
      },
      program: [
        { season: 'Winter · Nov 1 – Mar 15', light: '12 h', drip: 'Tue · Fri · 6 min', humidifier: '3 sessions', feed: '¼× monthly' },
        { season: 'Spring · Mar 15 – Jun 1', light: '14 h', drip: 'M·W·F · 8 min',    humidifier: '2 sessions', feed: '½× weekly' },
        { season: 'Summer · Jun 1 – Sep 16', light: '16 h', drip: 'Mon–Sat · 8 min',  humidifier: '1 session',  feed: '½× weekly' },
        { season: 'Autumn · Sep 16 – Nov 1', light: '14 h', drip: 'M·W·F · 8 min',    humidifier: '2 sessions', feed: '½× weekly' }
      ],
      watch: [
        { title: 'Sunday is the reading day', body: 'Moisture on every tree, pH and EC on the first Sunday of the month, both from the same pour-through sample. Wednesday is a moisture spot-check only.' },
        { title: 'The probe is a conservative sentinel', body: 'It sits in the top box — the warmest, driest shelf. When it reads on target, every shelf below is at or above target. Correct to the probe.' },
        { title: 'Calibrate before you trust a number', body: 'pH pen against 7.0 and 4.0 buffer monthly. Replace meter batteries at the first flicker: a dying capacitive meter reads dry, and you will overwater on its word.' },
        { title: 'EC governs the feed, not the calendar', body: 'Under 0.4 in season, step the dose up a notch. Over 2.0, flush two to three pot volumes and skip the next feed. Slow-release pellets count toward EC.' },
        { title: 'Condensation on the vinyl means too much', body: 'Crack the fronts until it clears and shorten the next humidifier session. Standing film breeds fungus.' }
      ]
    },
    {
      id: 'parrots-beak',
      name: "Parrot's beak",
      scientific: 'Gmelina philippensis · tropical',
      setting: 'indoor',
      summary: 'Fast, thirsty, heavy feeder; warmth-loving. Governs the bench cold floor at 55 °F and takes the warmest upper shelf.',
      track: ['ph', 'moisture', 'ec', 'growth', 'tempLow', 'tempHigh', 'humidity'],
      bands: {
        ph:       { good: [6.0, 6.8], warn: [5.8, 7.0] },
        moisture: { good: [45, 65],   warn: [35, 75],  note: 'water at 35–40%; never let it go fully dry' },
        ec:       { good: [1.0, 1.5], warn: [0.6, 2.0] },
        tempLow:  { good: [62, 70],   warn: [55, 74],  note: 'stress floor 55 °F' },
        tempHigh: { good: [70, 85],   warn: [65, 88] },
        humidity: { good: [50, 65],   warn: [45, 70] }
      },
      watch: [
        { title: 'Growth stalls below about 65 °F', body: 'Foliage damage risk below 45 °F. This tree sets the bench floor — give it the warmest, highest shelf.' },
        { title: 'Heaviest feeder on the bench', body: 'Alternate full- and half-strength Sundays, or half-strength weekly plus slow-release pellets top-dressed Apr 1 and Jul 1.' },
        { title: 'Mind the spines when pinching', body: 'Cut shoots back to 2–3 leaves once they run 6–8, and deadhead spent bracts.' }
      ]
    },
    {
      id: 'hawaiian-umbrella',
      name: 'Hawaiian umbrella',
      scientific: 'Schefflera arboricola · tropical',
      setting: 'indoor',
      summary: 'The most forgiving tree on the bench. Scissors-only styling — conventional wire fails on this species.',
      track: ['ph', 'moisture', 'ec', 'growth', 'tempLow', 'tempHigh', 'humidity'],
      bands: {
        ph:       { good: [6.0, 6.5], warn: [5.8, 7.0] },
        moisture: { good: [40, 60],   warn: [30, 70],  note: 'water at 30–35%; likes a slight dry-down' },
        ec:       { good: [0.8, 1.2], warn: [0.4, 1.8] },
        tempLow:  { good: [60, 68],   warn: [50, 72],  note: 'stress floor 50 °F' },
        tempHigh: { good: [65, 80],   warn: [60, 85] },
        humidity: { good: [50, 65],   warn: [45, 70] }
      },
      watch: [
        { title: 'Drops leaflets on sudden swings', body: 'Steady cool it tolerates; abrupt change it does not. Check it first after any HVAC changeover week.' },
        { title: 'Pushes aerial roots above 70% RH', body: 'Chamber this tree individually for an aerial-root campaign rather than raising humidity for the whole bench.' }
      ]
    },
    {
      id: 'ginseng-ficus',
      name: 'Ginseng grafted ficus',
      scientific: 'Ficus microcarpa · tropical',
      setting: 'indoor',
      summary: 'Steady and reliable, but hates cold drafts and being moved. Grafted — watch the graft line.',
      track: ['ph', 'moisture', 'ec', 'growth', 'tempLow', 'tempHigh', 'humidity'],
      bands: {
        ph:       { good: [6.0, 6.5], warn: [5.8, 7.0] },
        moisture: { good: [40, 60],   warn: [30, 70],  note: 'water at 30–40%; brief dry-downs are fine' },
        ec:       { good: [0.8, 1.2], warn: [0.4, 1.8] },
        tempLow:  { good: [62, 70],   warn: [59, 74],  note: 'stress floor 59 °F' },
        tempHigh: { good: [68, 85],   warn: [64, 88] },
        humidity: { good: [50, 65],   warn: [45, 70] }
      },
      watch: [
        { title: 'Chill drafts under 59 °F trigger leaf drop', body: 'Keep it clear of window cracks and vent blasts. It also resents being moved — pick a spot and leave it.' },
        { title: 'Remove understock suckers below the graft', body: 'Anything shooting from below the graft line is rootstock and will outcompete the scion if left.' },
        { title: 'Wire bites fast', body: 'It holds well but inspect every two weeks in season. Wipe the latex from cuts before it seals dirty.' }
      ]
    },
    {
      id: 'dwarf-pomegranate',
      name: 'Dwarf pomegranate',
      scientific: 'Punica granatum var. nana · subtropical',
      setting: 'indoor',
      summary: 'The driest and coolest tree on the bench, and its sun-hunger canary. Wants a leaner, dimmer winter rest.',
      track: ['ph', 'moisture', 'ec', 'growth', 'tempLow', 'tempHigh', 'humidity'],
      bands: {
        ph:       { good: [5.5, 7.0], warn: [5.2, 7.4] },
        moisture: { good: [35, 55],   warn: [25, 65],  note: 'water at 25–35%; driest tree on the bench and rot-prone if wet' },
        ec:       { good: [0.8, 1.2], warn: [0.4, 1.8] },
        tempLow:  { good: [60, 68],   warn: [41, 72],  note: 'stress floor 41 °F; a 40–55 °F rest is optional, not required' },
        tempHigh: { good: [65, 85],   warn: [60, 88] },
        humidity: { good: [45, 65],   warn: [40, 70] }
      },
      watch: [
        { title: 'It flags first when light falls short', body: 'Treat it as the bench light meter: if the pomegranate stretches, every tree is underlit.' },
        { title: 'Winter is a bypass, not a drought', body: 'Drip clamped, hand-water every 7–10 days through the rest. If it overwinters warm and in leaf, keep one emitter live instead.' },
        { title: 'Blooms come on new wood tips', body: 'Trim new shoots at 4–6 leaves except those left to flower. Thin fruit to 2–3. Suspend feed while flowers are open.' }
      ]
    },

    /* ------------------------------------------- outdoor full-size trees */
    {
      id: 'bergamot',
      name: 'Italian bergamot — container',
      scientific: 'Citrus bergamia · young stem graft',
      setting: 'seasonal',
      summary: 'Outdoors late spring through summer and a short while into autumn, indoors for the cold months. A grafted young citrus in a pot: cold timing, the graft line, and drainage are what actually decide how it does.',
      track: ['ph', 'moisture', 'ec', 'growth', 'tempLow', 'tempHigh', 'humidity'],
      bands: {
        ph:       { good: [6.0, 7.0], warn: [5.5, 7.5], target: 6.5, note: 'above 7.0 locks up iron and the new growth yellows' },
        moisture: { good: [35, 60],   warn: [25, 70],   note: 'water when the top inch is dry; citrus will not tolerate standing wet' },
        ec:       { good: [1.0, 2.0], warn: [0.6, 2.5], target: 1.5, note: 'a hungrier feeder than anything on the bonsai bench' },
        tempLow:  { good: [55, 95],   warn: [40, 100],  note: 'bring it in before nights sit below ~50 °F; damage risk below ~30 °F' },
        tempHigh: { good: [70, 95],   warn: [60, 100] },
        humidity: { good: [45, 65],   warn: [35, 75],   note: 'indoor winter air below ~35% is what invites spider mites' }
      },
      watch: [
        { title: 'Rootstock suckers below the graft', body: 'This is the single highest-value check on a grafted citrus. Anything emerging below the graft union is rootstock — often a vigorous trifoliate type that will outgrow and eventually replace your bergamot. Rub or cut them off flush the moment you see them, and log the check so you can see you have actually been doing it.', severity: 'high' },
        { title: 'Move it in and out gradually', body: 'Citrus drop leaves when light and temperature change abruptly. Give it one to two weeks of transition each way — a shaded porch on the way out in spring, a bright window on the way in during autumn. A sudden move is the usual cause of a bergamot going bare in October.', severity: 'high' },
        { title: 'Cold timing, not cold hardiness', body: 'Do not wait for frost. Bring it in when night lows start settling below about 50 °F, which in zone 7 is usually well before the first freeze. Log the low temperature each check so the decision is made on numbers rather than on how the evening felt.', severity: 'high' },
        { title: 'Iron chlorosis: yellow leaves, green veins', body: 'On new growth this means iron is unavailable, and pH above about 6.8 is usually why. Fix the pH first; chelated iron treats the symptom. Check the pour-through pH before reaching for a supplement.' },
        { title: 'Drainage decides everything', body: 'Root rot in a saturated pot kills more container citrus than cold does. Sharp-draining mix, a pot that actually drains, and never a saucer of standing water.' },
        { title: 'Feed it like citrus, not like bonsai', body: 'A citrus-specific fertiliser with micronutrients — nitrogen plus iron, manganese, zinc and magnesium. Feed through the growing season, then taper in late summer so the new growth hardens before it comes indoors.' },
        { title: 'Pests to scout', body: 'Citrus leaf miner leaves silvery serpentine trails in soft new flush. Scale and mealybug hide on stems and in leaf axils. Spider mites arrive indoors in dry winter air. Aphids cluster on the newest tips.' },
        { title: 'Bloom and fruit are worth recording', body: 'Note flowering and fruit set. On a young grafted tree it is usually better to remove early fruit so energy goes into the frame, but either way the record tells you what the tree is actually doing year over year.' }
      ]
    },
    {
      id: 'arbequina-olive',
      name: 'Arbequina olive — container',
      scientific: "Olea europaea 'Arbequina' · young stem graft",
      setting: 'outdoor',
      summary: 'Outdoors all year. Two things dominate: winter cold on a container root zone, and not overwatering it. Chill hours are tracked because without them there is no bloom.',
      track: ['ph', 'moisture', 'ec', 'growth', 'tempLow', 'tempHigh', 'chill'],
      bands: {
        ph:       { good: [6.5, 8.0], warn: [6.0, 8.5], target: 7.0, note: 'happily alkaline — unlike the bonsai bench, do not chase it down to 6.3' },
        moisture: { good: [20, 45],   warn: [15, 60],   note: 'water at about 20%; it wants to dry down further than anything else you are tracking' },
        ec:       { good: [0.8, 1.5], warn: [0.4, 2.0], note: 'more salt-tolerant than citrus, but container salts still accumulate' },
        tempLow:  { good: [20, 95],   warn: [15, 100],  note: 'container roots track air temperature — see the winter note below' },
        tempHigh: { good: [60, 95],   warn: [45, 105] },
        chill:    { good: [200, 600], warn: [100, 800], note: 'roughly 200–300 h below 45 °F needed to set flower buds' }
      },
      watch: [
        { title: 'Winter in a pot is the real risk in zone 7', body: 'Arbequina is among the hardier olives, but published hardiness figures — around 15–20 °F — describe an established tree in the ground. A young grafted olive in a container has almost none of that buffer: a pot root zone tracks air temperature instead of being insulated by soil mass, so roots see the actual low. Zone 7 design lows run 0–10 °F. Plan protection before you need it: an unheated garage or shed for the coldest snaps, the pot wrapped or sunk in mulch, and a sheltered spot against a south wall. Log the low each check so you know what it has actually been through.', severity: 'high' },
        { title: 'Overwatering kills more container olives than cold', body: 'Olives evolved on thin, sharply drained hillside soils. Let the mix dry well down between waterings and make sure the pot drains freely. Soggy roots in cool weather is the classic way to lose one.', severity: 'high' },
        { title: 'Rootstock suckers below the graft', body: 'Same rule as the bergamot: your tree is a graft, so anything shooting from below the union is rootstock and needs removing flush. Olives sucker readily from the base — check every time you water in the growing season.', severity: 'high' },
        { title: 'Chill hours are why it does or does not flower', body: 'Olives need roughly 200–300 hours below about 45 °F, with some day-night fluctuation, to set flower buds. In zone 7 you will get this easily outdoors — which is the upside of it wintering outside. Keep a running total each winter so a bloom-free spring has an explanation.' },
        { title: 'Olive knot', body: 'Rough woody galls on stems and branches, a bacterial infection spread by rain splashing into fresh wounds. Prune only in dry weather, sterilise between cuts, and cut out galled wood well below the gall.' },
        { title: 'Peacock spot', body: 'Dark rings with pale halos on leaves in cool wet spells, followed by defoliation. Improve air movement, avoid overhead watering, and clear fallen infected leaves rather than leaving them in the pot.' },
        { title: 'Feed lightly and stop early', body: 'Moderate nitrogen in spring and early summer only. Feeding late pushes soft growth that will not harden before frost — exactly what you do not want on a tree that overwinters outdoors. Olives are also one of the few trees genuinely responsive to boron.' },
        { title: 'Stake so it can still flex', body: 'A young grafted olive needs support against rock in wind, but a rigidly tied trunk never builds taper or strength. Tie low and loose, and expect to remove the stake within a couple of seasons.' }
      ]
    }
  ];

  var BY_ID = {};
  PROFILES.forEach(function (p) { BY_ID[p.id] = p; });

  /**
   * Judge a value against a band. Returns a level matching the packet's own
   * three-tier colour code, plus a label so status never rests on colour.
   */
  function evaluate(profile, key, value) {
    if (value == null || !profile || !profile.bands) return { level: 'none' };
    var band = profile.bands[key];
    if (!band || !band.good) return { level: 'none' };
    var warn = band.warn || band.good;
    if (value >= band.good[0] && value <= band.good[1]) {
      return { level: 'good', label: 'In band', band: band };
    }
    if (value >= warn[0] && value <= warn[1]) {
      return { level: 'warn', label: 'Act soon', band: band };
    }
    return { level: 'bad', label: 'Correct now', band: band };
  }

  function bandFor(profile, key) {
    return profile && profile.bands ? profile.bands[key] || null : null;
  }

  global.BonsaiProfiles = {
    metrics: METRICS,
    pairedCharts: PAIRED_CHARTS,
    all: function () { return PROFILES.slice(); },
    get: function (id) { return BY_ID[id] || BY_ID.generic; },
    evaluate: evaluate,
    bandFor: bandFor
  };
})(window);

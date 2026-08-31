/* Radiology Interpretation Academy — Normal measurements & thresholds.
   Values are commonly taught reference ranges; local protocols and age/body habitus adjustments apply. */
window.RIA = window.RIA || {};
RIA.data = RIA.data || {};

RIA.data.measurements = [
  {
    group: 'Chest & cardiovascular (adult)',
    rows: [
      ['Cardiothoracic ratio (PA erect)', '< 0.5', 'AP and supine films magnify the heart — do not apply the ratio strictly.'],
      ['Right paratracheal stripe', '< 5 mm', 'Widening: adenopathy, thyroid, hemorrhage.'],
      ['Ascending thoracic aorta', '< 4 cm', 'Aneurysm thresholds guide surveillance/repair per guidelines.'],
      ['Main pulmonary artery (CT)', '≤ ~29 mm', 'Also compare with adjacent ascending aorta; larger suggests pulmonary hypertension.'],
      ['ETT tip above carina', '3–5 cm (neutral neck)', 'Tip moves ~2 cm with flexion/extension.'],
      ['Azygos vein (erect)', '< 1 cm', 'Distends with volume overload/right heart pressure.'],
      ['Pericardium (CT)', '≤ 2–3 mm', 'Thicker: pericarditis, constriction.']
    ]
  },
  {
    group: 'Abdomen & pelvis (adult)',
    rows: [
      ['Small bowel / colon / cecum', '< 3 / 6 / 9 cm', 'The 3-6-9 rule for dilation on radiograph or CT.'],
      ['Small bowel wall (distended)', '≤ 3 mm', 'Thicker = edema, inflammation, ischemia, tumor.'],
      ['Common bile duct', '≤ 6 mm', 'Allow ~+1 mm/decade over 60; up to ~10 mm post-cholecystectomy.'],
      ['Gallbladder wall', '≤ 3 mm', 'Thicker: cholecystitis, hepatitis, ascites, heart failure (nonspecific when diffuse).'],
      ['Pancreatic duct', '≤ 3 mm', 'Dilated duct + parenchymal atrophy: obstructing lesion until excluded.'],
      ['Appendix (compressed, outer diameter)', '≤ 6 mm', 'Also: wall thickening, appendicolith, periappendiceal stranding.'],
      ['Abdominal aorta', '< 3 cm', '≥3 cm = aneurysm; rupture risk climbs steeply above 5–5.5 cm.'],
      ['Spleen (craniocaudal)', '≤ ~12–13 cm', 'Mild variation with height/sex.'],
      ['Kidneys (length)', '9–13 cm', 'Asymmetry > 2 cm deserves explanation.'],
      ['Bladder wall (distended)', '≤ 3 mm', 'Trabeculation/thickening: outlet obstruction, neurogenic, cystitis, tumor.'],
      ['Endometrial stripe (postmenopausal, bleeding)', '≤ 4–5 mm', 'Thicker warrants sampling; premenopausal thickness varies with cycle (~4–14 mm).'],
      ['Prostate volume', '≤ ~30 mL', 'Larger = BPH by convention.']
    ]
  },
  {
    group: 'Neuro & spine',
    rows: [
      ['Atlanto-dental interval', '< 3 mm adult; < 5 mm child', 'Widened: transverse ligament injury, RA, Down syndrome laxity.'],
      ['Basion–dens interval (CT)', '< ~8.5–9.5 mm', 'Craniocervical dissociation screening.'],
      ['Prevertebral soft tissue at C2 / C7', '< ~7 mm / < ~22 mm (adult)', 'Children: < half a vertebral body width at C2–C4; beware expiration/flexion false thickening.'],
      ['Ventricles (Evans index)', '< 0.3', 'Frontal horn width / max internal skull width; higher suggests hydrocephalus/atrophy context-dependent.'],
      ['Midline shift', '0 mm', 'Any shift is a finding; > 5 mm is a strong surgical signal in trauma.'],
      ['Optic nerve sheath (US/CT)', '< ~5–6 mm', 'Dilated sheath correlates with raised ICP.']
    ]
  },
  {
    group: 'Pediatric-specific',
    rows: [
      ['Pyloric muscle thickness / channel length (US)', '< 3 mm / < 15 mm', '≥3 mm and ≥15–17 mm with failure to open = hypertrophic pyloric stenosis.'],
      ['Appendix (child, US)', '≤ 6 mm', 'Same threshold as adult; graded compression, look for appendicolith.'],
      ['Intussusception target diameter (US)', '> 2.5 cm = ileocolic', 'Small (<2 cm) transient small-bowel–small-bowel intussusceptions often resolve.'],
      ['Infant cardiothoracic ratio (AP)', 'up to ~0.55–0.6', 'Technique-dependent; use vascularity and clinical context.'],
      ['Graf alpha angle (hip US)', '≥ 60°', 'DDH screening before ~4–6 months; femoral head coverage ≥ 50%.'],
      ['Conus medullaris level', 'at/above L2–L3 (infant)', 'Lower = suspect tethered cord (screen with US before ~3–4 months).'],
      ['C2–C3 pseudosubluxation', '≤ ~3 mm', 'Normal if the spinolaminar (Swischuk) line stays intact.'],
      ['Retropharyngeal soft tissue (child)', '< half vertebral body width (C2–C4)', 'Crying/expiration/flexion cause false thickening — repeat in extension-inspiration.'],
      ['ETT tip (neonate)', 'mid-trachea ~T1–T2', 'Roughly midway between clavicles and carina.'],
      ['UVC tip', 'IVC–RA junction (~T8–T9)', 'Avoid portal/hepatic venous position.'],
      ['UAC tip', 'high T6–T10 (or low L3–L4)', 'Away from major aortic branch origins.']
    ]
  },
  {
    group: 'Approximate effective doses (context for justification)',
    rows: [
      ['Chest radiograph (PA)', '~0.02 mSv', '≈ a few days of background radiation.'],
      ['Mammogram (two view)', '~0.4 mSv', ''],
      ['Head CT', '~2 mSv', ''],
      ['Chest CT', '~5–7 mSv', 'Low-dose nodule protocols ~1–2 mSv.'],
      ['Abdomen/pelvis CT', '~7–10 mSv', 'Modern iterative reconstruction lowers this.'],
      ['FDG PET/CT', '~8–15 mSv', 'Tracer + CT component.'],
      ['Ultrasound / MRI', '0 mSv', 'No ionizing radiation — first-line in children and pregnancy when adequate.']
    ]
  }
];

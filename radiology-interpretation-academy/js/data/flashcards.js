/* Radiology Interpretation Academy — Seeded flashcards (users can add their own).
   Each card: { id, deck, front, back }. SRS state is stored separately per user. */
window.RIA = window.RIA || {};
RIA.data = RIA.data || {};

RIA.data.flashcards = [
  // Densities & physics
  { id: 'fc-phys-1', deck: 'Physics & Safety', front: 'Name the five radiographic densities from darkest to brightest.', back: 'Gas → fat → soft tissue/fluid → bone/calcium → metal/contrast.' },
  { id: 'fc-phys-2', deck: 'Physics & Safety', front: 'Hounsfield units: water, air, fat, acute blood.', back: 'Water 0 · air −1000 · fat −100 to −50 · acute clotted blood 50–80 HU.' },
  { id: 'fc-phys-3', deck: 'Physics & Safety', front: 'On which projection does the heart appear magnified, and why?', back: 'AP — the heart sits farther from the detector, so the diverging beam magnifies it. Use PA erect for cardiothoracic ratio.' },
  { id: 'fc-phys-4', deck: 'Physics & Safety', front: 'Ultrasound: what does higher transducer frequency trade away, and for what?', back: 'Penetration decreases as resolution improves. High-frequency linear probes = superficial detail; low-frequency curvilinear = deep abdomen.' },
  { id: 'fc-phys-5', deck: 'Physics & Safety', front: 'How do you identify a T1- vs T2-weighted MR image at a glance?', back: 'Find fluid (CSF, bladder): dark = T1, bright = T2. Bright everything-else but dark CSF = FLAIR.' },
  { id: 'fc-phys-6', deck: 'Physics & Safety', front: 'Bright DWI + bright ADC — restriction or not?', back: 'Not restriction — T2 shine-through. True restriction is bright DWI with DARK ADC.' },
  { id: 'fc-phys-7', deck: 'Physics & Safety', front: 'Approximate effective dose: chest X-ray vs chest CT.', back: '~0.02 mSv vs ~5–7 mSv — a few hundred times more; justify and child-size every CT.' },
  { id: 'fc-phys-8', deck: 'Physics & Safety', front: 'Suspected GI perforation: which oral contrast and why?', back: 'Water-soluble iodinated contrast — barium causes peritonitis/mediastinitis if it leaks.' },
  { id: 'fc-phys-9', deck: 'Physics & Safety', front: 'Which CT phase shows urothelium? Which shows an intramural hematoma of the aorta?', back: 'Excretory/delayed phase (CT urogram); non-contrast shows the crescentic hyperdensity of intramural hematoma.' },

  // Chest
  { id: 'fc-cxr-1', deck: 'Chest', front: 'Lost right heart border on frontal CXR localizes disease to…', back: 'Right middle lobe (medial segment) — silhouette sign.' },
  { id: 'fc-cxr-2', deck: 'Chest', front: 'ETT and CVC: correct tip positions.', back: 'ETT 3–5 cm above the carina (neutral neck). CVC at the lower SVC / cavoatrial junction.' },
  { id: 'fc-cxr-3', deck: 'Chest', front: 'Supine patient, sharp deep lateral costophrenic angle. Diagnosis?', back: 'Deep sulcus sign — supine pneumothorax.' },
  { id: 'fc-cxr-4', deck: 'Chest', front: 'How much pleural fluid blunts the costophrenic angle on an erect PA film?', back: '≈200–300 mL. Lateral decubitus and ultrasound detect far less.' },
  { id: 'fc-cxr-5', deck: 'Chest', front: 'List four hidden areas of the chest radiograph.', back: 'Apices (behind clavicles), hila, retrocardiac area, below the diaphragm — plus the image corners/edges.' },
  { id: 'fc-cxr-6', deck: 'Chest', front: 'Golden S sign — what and who?', back: 'RUL collapse around a central mass creating a reverse-S minor fissure; classic for obstructing bronchogenic carcinoma.' },
  { id: 'fc-cxr-7', deck: 'Chest', front: 'Which way do atelectasis and effusion move the mediastinum?', back: 'Atelectasis pulls structures toward the volume loss; large effusion/mass pushes them away.' },
  { id: 'fc-cxr-8', deck: 'Chest', front: 'UIP pattern on HRCT — key features and distribution.', back: 'Honeycombing + traction bronchiectasis, reticulation; basal and subpleural predominance.' },

  // Neuro
  { id: 'fc-neuro-1', deck: 'Neuro', front: 'Epidural vs subdural hematoma — shape and boundaries.', back: 'Epidural: lentiform, limited by sutures, often skull fracture/arterial. Subdural: crescentic, crosses sutures, limited by falx/tentorium.' },
  { id: 'fc-neuro-2', deck: 'Neuro', front: 'Three early CT signs of MCA infarction.', back: 'Hyperdense MCA, insular ribbon loss, obscured lentiform nucleus (+ sulcal effacement).' },
  { id: 'fc-neuro-3', deck: 'Neuro', front: 'Blood Can Be Very Bad — expand it.', back: 'Blood, Cisterns, Brain (grey-white, shift), Ventricles, Bone — the head CT search order.' },
  { id: 'fc-neuro-4', deck: 'Neuro', front: 'When is a subdural hematoma isodense to brain, and how do you catch it?', back: 'Subacute (~1–3 weeks). Look for effaced sulci that stop short of the skull, displaced grey-white interface; use subdural windows.' },
  { id: 'fc-neuro-5', deck: 'Neuro', front: 'Ring-enhancing lesion with restricted diffusion in its core — favors what?', back: 'Pyogenic abscess (pus restricts). Tumor necrosis typically does not restrict centrally.' },
  { id: 'fc-neuro-6', deck: 'Neuro', front: 'Uncal herniation — two CT clues.', back: 'Effaced suprasellar cistern and dilated contralateral temporal horn (plus CN III palsy clinically).' },

  // Abdomen
  { id: 'fc-abd-1', deck: 'Abdomen', front: 'The 3-6-9 rule.', back: 'Upper limits of normal: small bowel 3 cm, colon 6 cm, cecum 9 cm.' },
  { id: 'fc-abd-2', deck: 'Abdomen', front: 'Supine signs of pneumoperitoneum (name three).', back: 'Rigler (double wall), falciform ligament outline, football sign, lucent liver, gas triangles.' },
  { id: 'fc-abd-3', deck: 'Abdomen', front: 'Portal venous gas vs pneumobilia.', back: 'Portal venous gas is peripheral (within 2 cm of capsule) — ominous (ischemia/NEC). Pneumobilia is central — usually post-sphincterotomy/biliary-enteric.' },
  { id: 'fc-abd-4', deck: 'Abdomen', front: 'CT criteria for appendicitis.', back: 'Appendix >6 mm, wall thickening/enhancement, periappendiceal fat stranding, ± appendicolith; free fluid/abscess if perforated.' },
  { id: 'fc-abd-5', deck: 'Abdomen', front: 'Adrenal nodule: 5 HU on non-contrast CT. Interpretation?', back: 'Lipid-rich adenoma (≤10 HU) — benign; no further workup in most contexts.' },
  { id: 'fc-abd-6', deck: 'Abdomen', front: 'Closed-loop obstruction — CT clues.', back: 'Two adjacent transition points, radially arranged loops, whirl sign, mesenteric edema, reduced wall enhancement = ischemia risk → surgical emergency.' },
  { id: 'fc-abd-7', deck: 'Abdomen', front: 'Coffee bean sign arising from the pelvis.', back: 'Sigmoid volvulus — ahaustral folded loop; urgent decompression.' },

  // MSK
  { id: 'fc-msk-1', deck: 'MSK', front: 'Elbow trauma: visible posterior fat pad but no fracture line. Call?', back: 'Occult fracture until proven otherwise — supracondylar in children, radial head in adults.' },
  { id: 'fc-msk-2', deck: 'MSK', front: 'Monteggia vs Galeazzi.', back: 'Monteggia: ulna fracture + radial head dislocation. Galeazzi: radius fracture + DRUJ injury. Always image the joints above and below.' },
  { id: 'fc-msk-3', deck: 'MSK', front: 'Salter-Harris types (SALTR).', back: 'I Slipped (physis), II Above (physis+metaphysis, most common), III Lower (physis+epiphysis), IV Through all, V Rammed (crush).' },
  { id: 'fc-msk-4', deck: 'MSK', front: 'Describe a fracture completely (checklist).', back: 'Bone + location, pattern, intra-articular?, displacement, angulation, shortening, rotation, open/closed, pediatric physeal involvement.' },
  { id: 'fc-msk-5', deck: 'MSK', front: 'Lipohemarthrosis on a knee film means…', back: 'Intra-articular fracture (marrow fat in the joint) — often occult tibial plateau; CT next.' },
  { id: 'fc-msk-6', deck: 'MSK', front: 'Aggressive vs benign periosteal reaction.', back: 'Benign: solid, thick, uniform. Aggressive: lamellated (onion-skin), spiculated (sunburst), Codman triangle.' },
  { id: 'fc-msk-7', deck: 'MSK', front: 'Lisfranc injury — the key alignment.', back: 'Medial border of the 2nd metatarsal base must align with the medial border of the middle cuneiform on AP; weight-bearing views unmask it.' },

  // Pediatrics
  { id: 'fc-peds-1', deck: 'Pediatrics', front: 'Bilious vomiting in a neonate — study and finding?', back: 'Emergent upper GI series. Normal DJ junction lies left of the left pedicle at bulb height; corkscrew = midgut volvulus.' },
  { id: 'fc-peds-2', deck: 'Pediatrics', front: 'CRITOE with approximate ages.', back: 'Capitellum 1y, Radial head 3y, Internal epicondyle 5y, Trochlea 7y, Olecranon 9y, External epicondyle 11y.' },
  { id: 'fc-peds-3', deck: 'Pediatrics', front: 'Pyloric stenosis ultrasound thresholds.', back: 'Muscle ≥3 mm thick, channel ≥15 mm, failure to open — 2–8 week old with projectile nonbilious vomiting.' },
  { id: 'fc-peds-4', deck: 'Pediatrics', front: 'NEC — four radiographic stages of concern.', back: 'Fixed dilated loops → pneumatosis intestinalis → portal venous gas → pneumoperitoneum (surgery).' },
  { id: 'fc-peds-5', deck: 'Pediatrics', front: 'High-specificity fractures for non-accidental injury.', back: 'Classic metaphyseal (corner/bucket-handle) lesions, posterior rib, scapular, sternal, spinous process fractures; multiple ages.' },
  { id: 'fc-peds-6', deck: 'Pediatrics', front: 'Steeple vs thumb sign.', back: 'Steeple (frontal, subglottic narrowing) = croup. Thumb (lateral, swollen epiglottis) = epiglottitis.' },
  { id: 'fc-peds-7', deck: 'Pediatrics', front: 'Pediatric hip pain by age.', back: '0–6 mo DDH; 4–10 y Perthes (AVN); 10–16 y SCFE (Klein line, frog-leg lateral).' },
  { id: 'fc-peds-8', deck: 'Pediatrics', front: 'Ingested disc with a double-rim/halo on X-ray.', back: 'Button battery — esophageal position is an emergency (liquefactive necrosis within hours). A coin is uniform.' },
  { id: 'fc-peds-9', deck: 'Pediatrics', front: 'Neuroblastoma vs Wilms on CT.', back: 'Neuroblastoma: arises off kidney, crosses midline, ENCASES vessels, calcifies. Wilms: arises FROM kidney (claw sign), displaces vessels.' },

  // Signs & measurements quick hits
  { id: 'fc-sign-1', deck: 'Classic Signs', front: 'Empty delta sign.', back: 'Non-enhancing thrombus with enhancing dural walls in the superior sagittal sinus — venous sinus thrombosis.' },
  { id: 'fc-sign-2', deck: 'Classic Signs', front: 'Double duct sign.', back: 'Dilated CBD + pancreatic duct — pancreatic head/ampullary mass until proven otherwise.' },
  { id: 'fc-sign-3', deck: 'Classic Signs', front: 'Barcode sign on M-mode lung US.', back: 'Absent lung sliding — pneumothorax; confirm with the lung point.' },
  { id: 'fc-sign-4', deck: 'Classic Signs', front: 'Halo sign around a lung nodule in a neutropenic patient.', back: 'Ground-glass hemorrhage rim — angioinvasive aspergillosis.' },
  { id: 'fc-meas-1', deck: 'Measurements', front: 'CBD normal caliber and allowances.', back: '≤6 mm; +~1 mm/decade after 60; up to ~10 mm post-cholecystectomy.' },
  { id: 'fc-meas-2', deck: 'Measurements', front: 'Abdominal aortic aneurysm definition and high-risk size.', back: '≥3 cm = aneurysm; repair discussion typically ≥5–5.5 cm or rapid growth.' },
  { id: 'fc-meas-3', deck: 'Measurements', front: 'Atlanto-dental interval limits.', back: '<3 mm adult, <5 mm child.' },
  { id: 'fc-meas-4', deck: 'Measurements', front: 'Postmenopausal endometrial stripe with bleeding — threshold?', back: '≤4–5 mm reassuring; thicker warrants sampling.' }
];

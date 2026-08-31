/* Radiology Interpretation Academy — Quiz bank.
   Each quiz: { id, name, icon, desc, questions: [{ q, opts, a (index), why }] }. */
window.RIA = window.RIA || {};
RIA.data = RIA.data || {};

RIA.data.quizzes = [
  {
    id: 'quiz-physics',
    name: 'Modality Physics & Safety',
    icon: '⚛️',
    desc: 'Image formation, HU, sequences, dose, and contrast safety across modalities.',
    questions: [
      {
        q: 'A lesion measures −80 HU on CT. It is most likely composed of:',
        opts: ['Simple fluid', 'Fat', 'Acute blood', 'Calcification'],
        a: 1,
        why: 'Fat measures roughly −100 to −50 HU. Simple fluid is ~0–20, acute blood 50–80, calcium 150+. Macroscopic fat is a powerful benign marker (lipoma, dermoid, angiomyolipoma, adrenal myelolipoma).'
      },
      {
        q: 'On an MR sequence, CSF is bright and the periventricular white matter lesions are also bright. CSF in the ventricles being bright identifies this as:',
        opts: ['T1', 'T2', 'FLAIR', 'GRE'],
        a: 1,
        why: 'Bright CSF = T2-weighting. FLAIR suppresses CSF (dark ventricles, bright lesions), which is why it is the demyelination workhorse.'
      },
      {
        q: 'Which is the correct pairing of ultrasound artifact and use?',
        opts: ['Posterior enhancement — confirms a stone', 'Clean posterior shadowing — confirms a calculus', 'Mirror image — confirms torsion', 'Anisotropy — confirms tendinosis'],
        a: 1,
        why: 'Stones/calcium cast clean shadows; fluid causes posterior enhancement; mirror artifact duplicates structures across the diaphragm; anisotropy is a false hypoechogenicity of obliquely-imaged tendons — a pitfall, not a confirmation.'
      },
      {
        q: 'A patient with suspected esophageal perforation needs a fluoroscopic contrast study. Best first agent:',
        opts: ['Thick barium', 'Water-soluble low-osmolar iodinated contrast', 'High-osmolar ionic contrast if aspiration risk', 'Air only'],
        a: 1,
        why: 'Barium causes mediastinitis/peritonitis if it leaks. Water-soluble contrast is used first; low-osmolar non-ionic agents are safer if aspirated (high-osmolar agents cause pulmonary edema).'
      },
      {
        q: 'Approximate effective dose of an abdomen/pelvis CT compared with a PA chest radiograph:',
        opts: ['About 10× higher', 'About 50× higher', 'Several hundred× higher', 'About the same'],
        a: 2,
        why: 'Abdomen/pelvis CT ~7–10 mSv vs chest X-ray ~0.02 mSv — several hundred times. This gap is why justification and pediatric dose-tailoring matter.'
      },
      {
        q: 'Which patient scenario is the strongest indication for V/Q scan over CTPA?',
        opts: ['Obese patient', 'Pregnant patient with prior severe iodinated contrast anaphylaxis', 'ICU patient', 'Patient with a pacemaker'],
        a: 1,
        why: 'Contrast allergy (and pregnancy pathways at some centers, often with reduced-dose perfusion-only technique) are the classic V/Q niches. Pacemakers are irrelevant to CT.'
      },
      {
        q: 'FDG PET/CT shows intense symmetric uptake in the supraclavicular regions of a cold, anxious young patient. Most likely explanation:',
        opts: ['Bilateral nodal metastases', 'Brown adipose tissue uptake', 'Lymphoma', 'Artifacts'],
        a: 1,
        why: 'Brown fat is a classic symmetric benign FDG trap in young/cold patients; CT correlation shows fat density, not nodes. Warming and protocols reduce it.'
      },
      {
        q: 'The single most important principle of MRI safety is:',
        opts: ['Gadolinium dosing', 'The static field is always on — ferromagnetic screening is absolute', 'Acoustic noise protection', 'Avoiding claustrophobia'],
        a: 1,
        why: 'Projectile injuries and implant interactions come from the always-on static field; zoned access and screening are the foundation of MR safety.'
      }
    ]
  },
  {
    id: 'quiz-cxr',
    name: 'Chest Radiograph Interpretation',
    icon: '🫁',
    desc: 'Technique, silhouettes, collapse patterns, lines, and hidden areas.',
    questions: [
      {
        q: 'A frontal CXR shows loss of the left heart border. The disease is in the:',
        opts: ['Left lower lobe', 'Lingula', 'Left upper lobe apex', 'Anterior mediastinum'],
        a: 1,
        why: 'The silhouette sign: the lingula touches the left heart border. The left lower lobe touches the left hemidiaphragm — LLL disease effaces the diaphragm, not the heart border.'
      },
      {
        q: 'On a supine trauma film, a deep, sharply lucent lateral costophrenic sulcus indicates:',
        opts: ['Hyperinflation', 'Pneumothorax', 'Pneumoperitoneum', 'Effusion'],
        a: 1,
        why: 'The deep sulcus sign — pleural air collects anteroinferiorly when supine, deepening and lucent-ing the sulcus rather than forming an apical line.'
      },
      {
        q: 'An endotracheal tube tip sits 1 cm above the carina with the neck in neutral position. Correct action:',
        opts: ['No action — normal', 'Advance 2 cm', 'Withdraw to 3–5 cm above carina', 'Remove immediately'],
        a: 2,
        why: 'Ideal tip is 3–5 cm above the carina in neutral position; flexion drives the tube down ~2 cm, risking right mainstem intubation from this position.'
      },
      {
        q: 'RUL collapse with a focal bulge in the medial fissure contour ("reverse S") should make you hunt for:',
        opts: ['Foreign body', 'Central obstructing carcinoma', 'Pleural effusion', 'Prior surgery'],
        a: 1,
        why: 'Golden S sign — lobar collapse around a central mass; in an adult this is bronchogenic carcinoma until bronchoscopy proves otherwise.'
      },
      {
        q: 'Elevated "hemidiaphragm" with the apparent dome peaking more laterally than usual. Next best step for suspected subpulmonic effusion:',
        opts: ['CT chest', 'Lateral decubitus film or ultrasound', 'Bronchoscopy', 'Repeat PA in one week'],
        a: 1,
        why: 'Subpulmonic effusion mimics a raised diaphragm (lateralized dome peak, increased distance from gastric bubble on the left). A decubitus film or US shows the mobile fluid without CT dose.'
      },
      {
        q: 'Which comparison best detects a slow-growing lung nodule?',
        opts: ['Yesterday\'s film', 'Last week\'s film', 'The oldest available comparable study', 'No comparison needed'],
        a: 2,
        why: 'Slow change is invisible over short intervals — compare against the oldest useful prior. This is a core habit for nodules and every indolent process.'
      },
      {
        q: 'A dense (white) left hilum with a convex aortopulmonary window in a smoker most likely represents:',
        opts: ['Normal variant', 'Hilar/AP window mass or adenopathy', 'Pericardial cyst', 'Rotated film only'],
        a: 1,
        why: 'The AP window should be concave or straight; convexity plus hilar density means mass/nodes. Rotation is a mimic — check the clavicles, then still explain the density.'
      },
      {
        q: 'Free air is suspected but the patient cannot stand. Best plain-film maneuver:',
        opts: ['Supine AP only', 'Left lateral decubitus (right side up)', 'Lordotic view', 'Expiratory film'],
        a: 1,
        why: 'Left lateral decubitus lets free air rise over the liver, away from the confusing gastric bubble; keep the patient positioned several minutes first. (An erect chest film is the most sensitive if standing is possible.)'
      }
    ]
  },
  {
    id: 'quiz-neuro',
    name: 'Head CT & Neuroimaging',
    icon: '🧠',
    desc: 'Hemorrhage compartments, early stroke, herniation, windows, and MRI logic.',
    questions: [
      {
        q: 'A lens-shaped (biconvex) hyperdense extra-axial collection that does not cross sutures is a:',
        opts: ['Subdural hematoma', 'Epidural hematoma', 'Subarachnoid hemorrhage', 'Contusion'],
        a: 1,
        why: 'Epidural blood strips dura from bone and is bounded by sutures; classically arterial (middle meningeal) with an overlying fracture and a lucid interval.'
      },
      {
        q: 'Two weeks after a fall, an elderly patient\'s CT shows effaced sulci over one convexity that stop short of the skull, with subtle grey-white interface displacement — but no obvious blood. Best explanation:',
        opts: ['Artifact', 'Isodense subacute subdural hematoma', 'Old infarct', 'Normal atrophy'],
        a: 1,
        why: 'Subacute subdural blood passes through an isodense phase (~1–3 weeks) and hides on brain windows. Subdural windows and the displaced interface catch it.'
      },
      {
        q: 'Earliest CT sign set of MCA infarction includes all EXCEPT:',
        opts: ['Hyperdense MCA', 'Loss of insular ribbon', 'Obscured lentiform nucleus', 'Well-defined hypodensity with volume loss'],
        a: 3,
        why: 'Sharply-defined hypodensity with volume loss (encephalomalacia) is a CHRONIC infarct. Early signs are subtle: dense vessel, insular ribbon and lentiform obscuration, sulcal effacement.'
      },
      {
        q: 'Effacement of the suprasellar cistern with dilation of the contralateral temporal horn indicates:',
        opts: ['Subfalcine herniation', 'Uncal herniation', 'Tonsillar herniation', 'Communicating hydrocephalus'],
        a: 1,
        why: 'The uncus crowds the suprasellar cistern and obstructs CSF flow at the contralateral foramen — trapping the temporal horn. CN III palsy is the clinical partner.'
      },
      {
        q: 'Thunderclap headache, normal non-contrast CT at 3 days. Concern remains for SAH. Why is the CT insufficient?',
        opts: ['CT never shows SAH', 'Sensitivity for SAH falls substantially after the first hours-days', 'Wrong windows', 'SAH is only visible on bone windows'],
        a: 1,
        why: 'CT is near-perfect within ~6 hours of onset but blood becomes isodense as it dilutes/degrades; at days out, LP or further imaging is needed per protocol.'
      },
      {
        q: 'A cortical/subcortical lesion is bright on DWI and bright on ADC. Interpretation:',
        opts: ['Acute infarct', 'T2 shine-through, not true restriction', 'Abscess', 'Hypercellular tumor'],
        a: 1,
        why: 'True restriction pairs bright DWI with DARK ADC. Bright-bright is shine-through from underlying T2 signal.'
      },
      {
        q: 'A young patient with headache has a hyperdense superior sagittal sinus on non-contrast CT. Next step:',
        opts: ['Reassure', 'CT or MR venography', 'Catheter angiogram', 'Lumbar puncture'],
        a: 1,
        why: 'Dense sinus (cord sign) suggests venous sinus thrombosis; venography confirms (empty delta on contrast). Venous infarcts don\'t respect arterial territories and often hemorrhage.'
      },
      {
        q: 'Multiple bilateral lesions at the grey-white junction with surrounding edema in a 60-year-old favor:',
        opts: ['Multiple sclerosis', 'Metastases', 'Lacunar infarcts', 'Neurocysticercosis always'],
        a: 1,
        why: 'The grey-white junction is where emboli — including tumor emboli — lodge; multiple junctional enhancing lesions in an adult = metastases first.'
      }
    ]
  },
  {
    id: 'quiz-abdo',
    name: 'Abdominal Imaging',
    icon: '🫃',
    desc: 'Gas patterns, obstruction, inflammation, and organ-specific rules.',
    questions: [
      {
        q: 'Dilated central loops with valvulae crossing the full lumen and a gasless colon indicate:',
        opts: ['Ileus', 'Small bowel obstruction', 'Sigmoid volvulus', 'Normal'],
        a: 1,
        why: 'Valvulae conniventes mark small bowel; disproportionate small-bowel dilation with a collapsed colon means mechanical SBO — hunt the transition point and check hernial orifices.'
      },
      {
        q: 'Both walls of several bowel loops are crisply visible on a supine radiograph. This is:',
        opts: ['Normal', 'Rigler sign — pneumoperitoneum', 'Pneumatosis', 'Ascites'],
        a: 1,
        why: 'Bowel wall is only visible when gas sits on both sides — intraluminal plus free intraperitoneal air.'
      },
      {
        q: 'RLQ pain: CT shows a 9 mm blind-ending tubular structure with wall enhancement and periappendiceal fat stranding. Diagnosis:',
        opts: ['Normal appendix', 'Acute appendicitis', 'Meckel diverticulum', 'Cecal diverticulitis'],
        a: 1,
        why: '>6 mm with mural enhancement and stranding = appendicitis. Look additionally for appendicolith, perforation (abscess, extraluminal gas).'
      },
      {
        q: 'A 2 cm adrenal nodule measures 4 HU on unenhanced CT. Interpretation:',
        opts: ['Metastasis', 'Lipid-rich adenoma — benign', 'Pheochromocytoma', 'Needs biopsy'],
        a: 1,
        why: '≤10 HU unenhanced = lipid-rich adenoma with high specificity. Indeterminate nodules go to washout CT or chemical-shift MRI, not straight to biopsy.'
      },
      {
        q: 'Peripheral branching gas extending to within 1 cm of the liver capsule in a hypotensive patient with abdominal pain suggests:',
        opts: ['Pneumobilia', 'Portal venous gas from bowel ischemia', 'Abscess', 'Recent ERCP'],
        a: 1,
        why: 'Portal venous gas is peripheral (portal flow carries it outward); pneumobilia is central. With ischemic clinical context and pneumatosis, this is dead-bowel physiology — surgical emergency.'
      },
      {
        q: 'Hemoperitoneum is present after trauma. The highest-density clot sits along the splenorenal recess. Most likely injured organ:',
        opts: ['Liver', 'Spleen', 'Bladder', 'Pancreas'],
        a: 1,
        why: 'The sentinel clot sign: clot is densest adjacent to its source. Fluid density measurement (blood 30–45+ HU, clot higher) is a routine act in trauma reads.'
      },
      {
        q: 'CT for flank pain: delayed nephrogram, hydroureter to the pelvic brim, and a 6 mm opacity at the ureterovesical junction... which is the best descriptor of stone-detection on CT?',
        opts: ['Most stones are invisible', 'Nearly all stones are radiopaque on CT', 'Only calcium stones are visible', 'US is superior for ureteric stones'],
        a: 1,
        why: 'Virtually all stones (except rare protease-inhibitor stones) are dense on non-contrast CT — the reference standard. The three narrowings (UPJ, brim, UVJ) are the lodging points.'
      },
      {
        q: 'Two transition points with a radial cluster of fluid-filled loops, whirled mesentery, and poor wall enhancement mean:',
        opts: ['Simple SBO — conservative care', 'Closed-loop obstruction with ischemia — surgery now', 'Ileus', 'Crohn flare'],
        a: 1,
        why: 'Closed loops strangulate. Reduced enhancement, mesenteric edema/haziness, and the whirl are the ischemia flags that change management from drip-and-suck to the OR.'
      }
    ]
  },
  {
    id: 'quiz-msk',
    name: 'MSK & Trauma',
    icon: '🦴',
    desc: 'Fracture detection, description, alignment lines, and classic injury pairings.',
    questions: [
      {
        q: 'A child falls on an outstretched hand. Elbow films show an elevated anterior fat pad and a visible posterior fat pad, no fracture line. Management assumption:',
        opts: ['Normal elbow', 'Occult supracondylar fracture', 'Septic joint', 'Dislocation'],
        a: 1,
        why: 'Any posterior fat pad = effusion; in trauma this means occult fracture — supracondylar in children, radial head in adults. Immobilize and follow up.'
      },
      {
        q: 'An "isolated" midshaft ulna fracture requires dedicated views of:',
        opts: ['The wrist only', 'The elbow — radial head alignment (Monteggia)', 'The shoulder', 'The contralateral arm'],
        a: 1,
        why: 'Monteggia = ulna fracture + radial head dislocation. The radiocapitellar line must intersect the capitellum on every view. Forearm bones are a ring with the joints.'
      },
      {
        q: 'A Salter-Harris fracture crossing the metaphysis, physis, and epiphysis is type:',
        opts: ['II', 'III', 'IV', 'V'],
        a: 2,
        why: 'Type IV traverses all three zones (SALTR: Through). It is intra-articular and physeal-bar-prone — anatomic reduction matters.'
      },
      {
        q: 'After a seizure, the AP shoulder shows a fixed internally rotated "light bulb" humeral head with a normal-appearing joint space. Next step:',
        opts: ['Discharge', 'Axillary or scapular-Y view for posterior dislocation', 'MRI rotator cuff', 'CT chest'],
        a: 1,
        why: 'Posterior dislocations hide on AP views; seizures and electrocution are the classic mechanisms. Orthogonal views make the diagnosis.'
      },
      {
        q: 'Fall from height with calcaneal fractures. Which associated site must be imaged?',
        opts: ['Skull', 'Thoracolumbar spine', 'Pelvis only', 'Ribs'],
        a: 1,
        why: 'Axial loading pairs calcaneal fractures with thoracolumbar compression/burst fractures (~10%). Injury pairings are part of the search pattern.'
      },
      {
        q: 'Weight-bearing foot film: 3 mm lateral offset between the 2nd metatarsal base and the middle cuneiform. Diagnosis:',
        opts: ['Normal variant', 'Lisfranc injury', 'Jones fracture', 'Stress fracture'],
        a: 1,
        why: 'The 2nd MT base–middle cuneiform alignment is the Lisfranc checkpoint; even subtle offset (or a fleck avulsion) means tarsometatarsal disruption — orthopedic referral.'
      },
      {
        q: 'A lytic lesion with a wide zone of transition, cortical destruction, and sunburst periosteal reaction in a teenager\'s distal femur suggests:',
        opts: ['Non-ossifying fibroma', 'Osteosarcoma', 'Simple bone cyst', 'Osteochondroma'],
        a: 1,
        why: 'Aggressive features (wide transition, aggressive periosteal patterns, soft-tissue mass) + metaphyseal location + age = osteosarcoma until proven otherwise. Benign lesions have narrow, sclerotic margins.'
      },
      {
        q: 'Elderly patient, hip pain after a fall, cannot bear weight, radiographs normal. Best next test:',
        opts: ['Repeat films in 6 weeks', 'MRI (or CT if MRI unavailable)', 'Bone scan same day', 'Ultrasound'],
        a: 1,
        why: 'Occult hip fractures are common and MRI is the most sensitive immediate test; missing one risks displacement and AVN. Clinical suspicion overrides a normal film.'
      }
    ]
  },
  {
    id: 'quiz-peds',
    name: 'Pediatric Imaging',
    icon: '🧸',
    desc: 'Age-keyed emergencies, normal variants, and dose-aware pathways.',
    questions: [
      {
        q: 'A 3-week-old has projectile nonbilious vomiting. First-line study and threshold:',
        opts: ['Upper GI series', 'Ultrasound — pyloric muscle ≥3 mm, channel ≥15 mm', 'CT abdomen', 'MRI'],
        a: 1,
        why: 'Hypertrophic pyloric stenosis is an ultrasound diagnosis. Upper GI is for BILIOUS vomiting (malrotation/volvulus) — the vomit color routes the workup.'
      },
      {
        q: 'A neonate has bilious vomiting and a NORMAL abdominal radiograph. Correct response:',
        opts: ['Reassure and feed', 'Emergent upper GI series — volvulus can have a normal film', 'Schedule US next week', 'Repeat film in 24 h'],
        a: 1,
        why: 'Midgut volvulus strangulates the entire midgut within hours and the plain film may look normal. Bilious vomiting in a neonate = emergent UGI, full stop.'
      },
      {
        q: 'A 9-month-old with intermittent colicky pain and lethargy has a 3 cm target sign in the right abdomen on US. Next step:',
        opts: ['CT confirmation', 'Air or hydrostatic enema reduction', 'MRI', 'Observation'],
        a: 1,
        why: 'Ileocolic intussusception (>2.5 cm target) proceeds directly to image-guided enema reduction with surgery on standby — no CT needed.'
      },
      {
        q: 'A preemie on feeds develops distension. Radiograph shows curvilinear lucency within the bowel wall. This represents:',
        opts: ['Normal gas', 'Pneumatosis intestinalis — NEC', 'Free air', 'Meconium'],
        a: 1,
        why: 'Intramural gas = pneumatosis, the hallmark of necrotizing enterocolitis. Watch next for portal venous gas and free air (surgical).'
      },
      {
        q: 'An 8-year-old\'s elbow film shows an ossific fragment near the joint. The trochlea is ossified but no internal (medial) epicondyle is seen in its normal position. Interpretation:',
        opts: ['Normal CRITOE variation', 'Avulsed medial epicondyle trapped in the joint', 'Loose body of no significance', 'Lateral condyle fracture'],
        a: 1,
        why: 'CRITOE order is fixed: internal epicondyle (5y) ossifies before trochlea (7y). If the trochlea is present but the medial epicondyle is "missing", the fragment in the joint IS the epicondyle.'
      },
      {
        q: 'A 2-year-old\'s chest film shows one hyperlucent lung that stays inflated on the decubitus view with that side down. Diagnosis:',
        opts: ['Normal', 'Airway foreign body with air trapping', 'Pneumonia', 'Pleural effusion'],
        a: 1,
        why: 'The dependent lung should deflate; persistent inflation = ball-valve air trapping from an (often radiolucent) aspirated foreign body → bronchoscopy.'
      },
      {
        q: 'An infant not yet walking presents with a femur fracture and "found like that" history. Films show healing posterior rib fractures. Next step:',
        opts: ['Cast and discharge', 'Full skeletal survey + child-protection evaluation per protocol', 'Repeat femur film only', 'Bone density testing'],
        a: 1,
        why: 'Long-bone fracture in a non-ambulatory infant plus high-specificity fractures (posterior ribs, metaphyseal corners) mandates a protocolized NAT workup including skeletal survey (and neuroimaging in young infants).'
      },
      {
        q: 'A 12-year-old with weeks of limp and knee pain has a frontal pelvis where the Klein line fails to intersect the left epiphysis. Diagnosis and confirming view:',
        opts: ['Perthes — bone scan', 'SCFE — frog-leg lateral', 'Toddler fracture — oblique tibia', 'Septic hip — MRI'],
        a: 1,
        why: 'SCFE is the adolescent hip diagnosis; the epiphysis slips posteromedially, best seen on frog-leg lateral. Knee pain referral is the classic trap. (Avoid forced positioning if unstable.)'
      }
    ]
  }
];

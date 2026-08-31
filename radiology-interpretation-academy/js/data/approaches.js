/* Radiology Interpretation Academy — Systematic approaches & checklists.
   Each approach: interactive checklist steps + pearls + classic misses. */
window.RIA = window.RIA || {};
RIA.data = RIA.data || {};

RIA.data.approaches = [
  {
    id: 'cxr-adult',
    name: 'Chest Radiograph (Adult)',
    icon: '🫁',
    scope: 'adult',
    intro: `<p>The chest film rewards ritual. Use the same order every time so that a distracting finding cannot derail your search. The sequence below runs outside-in, then targets the classic blind spots.</p>`,
    steps: [
      { t: 'Confirm patient, date, side markers, and comparison priors', d: 'Wrong-patient and wrong-date errors are real. Pull the most recent prior AND an older baseline — slow change is invisible against yesterday\'s film.' },
      { t: 'Assess adequacy (RIPE)', d: 'Rotation (spinous process between clavicles), Inspiration (5–6 anterior ribs), Projection (PA vs AP, erect vs supine), Exposure (spine just visible through heart).' },
      { t: 'Tubes, lines, devices first', d: 'ETT tip 3–5 cm above carina (neck position moves it); enteric tube below diaphragm, tip in stomach or beyond; CVC tip in lower SVC/cavoatrial junction; chest drains, pacemaker leads, valves. Malposition is an immediate-action finding.' },
      { t: 'Airway and mediastinum', d: 'Trachea midline (allow slight right deviation at the aortic knob), carinal angle, tracheal narrowing. Mediastinal width (widening on erect PA > ~8 cm concerning), contours: aortic knob, AP window, azygos, paratracheal stripe (&lt;5 mm).' },
      { t: 'Heart and hila', d: 'Cardiothoracic ratio &lt;0.5 on PA. Chamber-specific enlargement patterns. Hila: left normally up to 1.5 cm higher than right; compare density and convexity — a dense or lumpy hilum means mass or adenopathy until explained.' },
      { t: 'Lungs — systematic sweep and side-to-side comparison', d: 'Scan apices to bases comparing symmetric zones. Name findings by pattern: consolidation (fluffy, air bronchograms), interstitial (lines, reticulation, Kerley B), nodules/masses, atelectasis (volume loss: fissure/hilar displacement, elevated diaphragm), hyperlucency.' },
      { t: 'Pleura and costophrenic angles', d: 'Blunted angle ≈ 200–300 mL effusion on erect PA. Trace the pleural edge for pneumothorax (visible visceral pleural line, absent markings beyond). Supine pneumothorax → deep sulcus sign. Pleural thickening, plaques, masses.' },
      { t: 'Diaphragm and below', d: 'Right hemidiaphragm normally up to ~3 cm higher than left. Free air under the diaphragm on erect film = perforation until proven otherwise (distinguish from Chilaiditi — haustrated colon interposed). Gastric bubble position, sub-diaphragmatic masses.' },
      { t: 'Bones and soft tissues', d: 'Ribs (fractures, lytic lesions — count them deliberately), clavicles, shoulders, spine (paraspinal lines), vertebral heights. Soft tissues: subcutaneous emphysema, mastectomy, calcifications.' },
      { t: 'The hidden areas — a second targeted look', d: 'Apices (behind clavicles/first ribs), hila, retrocardiac left lower lobe (spine sign on lateral), below the diaphragm, and the film edges (shoulders, neck, upper abdomen). Most misses live here.' },
      { t: 'Synthesize and answer the clinical question', d: 'Findings → pattern → differential ranked by clinical context → clear impression with recommendation. If the question is not answered, say what test would answer it.' }
    ],
    pearls: [
      'Silhouette sign localizes: lost right heart border = middle lobe/lingula-equivalent (RML); lost left heart border = lingula; lost hemidiaphragm = lower lobe.',
      'On the lateral: vertebral bodies should get darker caudally — increasing whiteness (spine sign) = lower-lobe disease.',
      'Volume loss (atelectasis) pulls structures toward it; masses and effusions push.',
      'An apparently elevated hemidiaphragm may be a subpulmonic effusion — lateral or ultrasound settles it.',
      'Compare current with the OLDEST relevant prior for slow-growing nodules.'
    ],
    misses: [
      'Pneumothorax on supine films (look for deep sulcus, sharp cardiac border, hyperlucent upper abdomen).',
      'Small apical lung cancer behind the clavicle.',
      'Retrocardiac pneumonia or hiatal hernia.',
      'Rib metastasis and shoulder pathology at the image corners.',
      'Malpositioned lines: esophageal ETT, arterial CVC, coiled enteric tube in the airway.'
    ]
  },

  {
    id: 'cxr-peds',
    name: 'Chest Radiograph (Pediatric)',
    icon: '🧸',
    scope: 'peds',
    intro: `<p>The pediatric chest film uses the adult ritual plus age-specific normals and a different differential. Rotation and expiration are far more common — judge technique first, aggressively.</p>`,
    steps: [
      { t: 'Technique: rotation and lung volumes', d: 'Rotated infant films create false mediastinal shift and false hyperlucency. Expiratory films fake cardiomegaly and perihilar haze. Anterior rib count 5–6 for adequate inspiration.' },
      { t: 'Recognize the thymus as normal', d: 'The infant thymus is a soft anterior mediastinal density: sail sign (triangular right lobe), wave sign (rippled by rib cartilages), notch at the cardiothymic junction. It involutes with stress and age. Do not call it a mass or consolidation.' },
      { t: 'Lines and tubes (neonatal ICU films)', d: 'ETT mid-trachea (T1–T2, moves with head position). UVC: up the umbilical vein via ductus venosus to IVC/RA junction. UAC: down then up the aorta — high position T6–T10 (or low L3–L4), tip away from major branch origins. NG below diaphragm.' },
      { t: 'Airway assessment', d: 'On lateral neck films: epiglottis (thumb sign = epiglottitis), subglottic narrowing (steeple sign = croup, on frontal), retropharyngeal soft tissue (&lt; vertebral body width at C2–C4 in children; thick = abscess — beware flexion/expiration false positives).' },
      { t: 'Lungs by age-typical differential', d: 'Neonate: RDS (granular, low volumes, air bronchograms in preemie), TTN (wet fissures, streaky, term/C-section), meconium aspiration (patchy, hyperinflated, term), congenital lesions. Infant/toddler: bronchiolitis (hyperinflation, peribronchial cuffing, atelectasis). Child: round pneumonia is real — a "mass" in a febrile child is usually pneumonia.' },
      { t: 'Foreign body check', d: 'Most aspirated foreign bodies are radiolucent. Look for unilateral hyperinflation (air trapping) — confirm with expiratory or bilateral decubitus films (the dependent lung should deflate; a foreign-body lung stays inflated).' },
      { t: 'Heart and situs', d: 'Infant CTR up to ~0.55–0.6 can be normal (AP, expiration). Check aortic arch side, stomach bubble/liver position (situs), pulmonary vascularity (increased in shunts, decreased in some cyanotic lesions).' },
      { t: 'Bones — with non-accidental injury awareness', d: 'Healing posterior rib fractures and classic metaphyseal lesions are highly specific for inflicted injury. Also check clavicles, proximal humeri, vertebral bodies.' },
      { t: 'Review areas and synthesize', d: 'Airway, thymus vs mass, behind heart, under diaphragm, soft tissues (subcutaneous air, edema). State the age-appropriate differential.' }
    ],
    pearls: [
      'Spinnaker/angel-wing sign = thymus lifted by pneumomediastinum — that one IS pathology.',
      'Bilateral decubitus films substitute for expiratory views in uncooperative toddlers.',
      'A normal chest film is common in early bronchiolitis; imaging is not routinely needed.',
      'In suspected NAT the chest film is part of a full skeletal survey done to protocol.'
    ],
    misses: [
      'Air-trapping from an occult foreign body read as "asthma".',
      'Posterior rib fractures (healing) in infants.',
      'Esophageal coin oriented in coronal plane vs tracheal foreign body (sagittal) — and button batteries (halo/double-rim sign) which are emergencies.',
      'Duct-dependent congenital heart disease behind a "normal-looking" film.'
    ]
  },

  {
    id: 'axr',
    name: 'Abdominal Radiograph',
    icon: '🎈',
    scope: 'both',
    intro: `<p>The abdominal film is mostly a gas-pattern study. Its two emergency jobs: obstruction and perforation. Everything else (calcifications, bones, soft tissues) rides along.</p>`,
    steps: [
      { t: 'Technique and coverage', d: 'Supine is standard; erect or left-lateral decubitus for free air and air–fluid levels. Coverage must include hernial orifices and both hemidiaphragms (or pair with an erect chest film — the most sensitive plain film for free air).' },
      { t: 'Bowel gas pattern — the 3/6/9 rule', d: 'Small bowel &lt;3 cm, colon &lt;6 cm, cecum &lt;9 cm. Identify loops: small bowel is central with valvulae conniventes crossing the full lumen; colon is peripheral with haustra that do not cross. Dilated small bowel with a gasless colon = SBO; look for transition and consider hernias/adhesions.' },
      { t: 'Volvulus patterns', d: 'Sigmoid volvulus: coffee-bean loop from the pelvis toward the RUQ, ahaustral. Cecal volvulus: displaced dilated cecum toward the LUQ. Both need urgent decompression.' },
      { t: 'Free air (pneumoperitoneum)', d: 'Erect: crescent under the diaphragm. Supine signs: Rigler (both walls of bowel visible), falciform ligament outlined, football sign (large central lucency — classic in neonates), lucent liver, triangles of gas between loops.' },
      { t: 'Abnormal gas elsewhere', d: 'Pneumatosis (gas in bowel wall — ischemia; in neonates = NEC), portal venous gas (branching lucency to liver periphery — worse than pneumobilia which is central), gas in biliary tree, retroperitoneal air, gas in the bladder wall or an abscess.' },
      { t: 'Calcifications', d: 'Look at: RUQ (gallstones — only ~10–20% opaque), renal shadows and ureteric lines (stones — most are opaque), pancreas (chronic pancreatitis), appendicolith (RLQ, supports appendicitis), aorta (aneurysm rim), pelvis (phleboliths have lucent centers), teratoma (teeth).' },
      { t: 'Solid organ outlines and soft tissues', d: 'Liver and spleen size, renal outlines, psoas margins (loss is nonspecific), bladder, properitoneal fat stripes. Displacement of gas can mark masses or organomegaly.' },
      { t: 'Bones and review areas', d: 'Lower ribs, lumbar spine (fractures, metastases, sacroiliitis), hips and sacrum. Review: hernial orifices, lung bases on included slices of chest, and always the corners.' }
    ],
    pearls: [
      'An erect chest X-ray detects as little as 1–2 mL of free air — order it with the abdomen for suspected perforation.',
      'A "gasless abdomen" in a vomiting neonate can itself be a sign of high obstruction or midgut volvulus.',
      'Left lateral decubitus (right side up) shows free air over the liver when the patient cannot stand.',
      'CT has largely replaced AXR for diagnosis — the plain film screens and follows (e.g., tube positions, stool burden is NOT a validated use).'
    ],
    misses: [
      'Closed-loop obstruction with little gas (fluid-filled loops).',
      'Small free air collections read as bowel gas — check for Rigler carefully.',
      'Appendicolith in a child with abdominal pain.',
      'Femoral/inguinal hernia gas at the image edge.'
    ]
  },

  {
    id: 'axr-neonate',
    name: 'Neonatal Abdomen (incl. NEC & obstruction)',
    icon: '👶',
    scope: 'peds',
    intro: `<p>Neonatal bowel gas reads differently: haustra are not developed, so small and large bowel are hard to tell apart — think "proximal vs distal obstruction" by the number of dilated loops instead.</p>`,
    steps: [
      { t: 'Count dilated loops: proximal vs distal obstruction', d: 'Single bubble = gastric/pyloric; double bubble = duodenal atresia (trisomy 21 association) — but double bubble PLUS distal gas can be malrotation/volvulus → emergent upper GI. Few loops = jejunal atresia. Many loops = distal: ileal atresia, meconium ileus, Hirschsprung, small left colon → contrast enema differentiates.' },
      { t: 'Necrotizing enterocolitis (NEC) checklist', d: 'Preemie with distension/feeding intolerance: fixed dilated loops on serial films, pneumatosis intestinalis (bubbly or curvilinear intramural gas), portal venous gas, and the feared pneumoperitoneum (football sign, Rigler) = perforation → surgery. Left lateral decubitus for subtle free air.' },
      { t: 'Malrotation vigilance', d: 'Bilious vomiting in a neonate is midgut volvulus until proven otherwise — the plain film may be NORMAL. Emergent upper GI: duodenojejunal junction must reach left of the left pedicle at bulb height; corkscrew = volvulus.' },
      { t: 'Lines: UVC/UAC positions', d: 'Check on every NICU babygram along with ETT and NG. UVC tip at IVC/RA junction; malposition into portal/hepatic veins risks thrombosis and TPN extravasation. UAC high T6–T10 or low L3–L4.' },
      { t: 'Wall, calcifications, and masses', d: 'Meconium peritonitis: scattered calcifications from in-utero perforation. Adrenal calcification (old hemorrhage). Masses displacing gas: renal (hydronephrosis, multicystic dysplastic kidney), neuroblastoma.' }
    ],
    pearls: [
      'Normal newborn: gas reaches the rectum by ~24 hours — absent rectal gas supports distal obstruction.',
      'In NEC, serial films every 6–12 h track progression; a persistent fixed loop is a bad sign.',
      'Contrast enema in distal obstruction is both diagnostic and often therapeutic (meconium ileus, small left colon).'
    ],
    misses: [
      'Normal film falsely reassuring in early midgut volvulus.',
      'Subtle pneumatosis dismissed as stool.',
      'UVC tip in the portal system.'
    ]
  },

  {
    id: 'head-ct',
    name: 'Non-contrast Head CT',
    icon: '🧠',
    scope: 'both',
    intro: `<p>The emergency head CT question set: blood, brain, ventricles, bone. The mnemonic <strong>"Blood Can Be Very Bad"</strong> orders the search. Review in brain, subdural, stroke, and bone windows — every study, every time.</p>`,
    steps: [
      { t: 'Blood', d: 'Acute blood is hyperdense (50–80 HU). Locate it by compartment: Epidural (lentiform, bounded by sutures, usually arterial/skull fracture), Subdural (crescentic, crosses sutures not midline dural reflections — check subdural windows for thin films), Subarachnoid (sulci, cisterns, sylvian fissures — aneurysmal until proven otherwise), Intraparenchymal (location suggests cause: basal ganglia = hypertension; lobar in elderly = amyloid; any = underlying lesion), Intraventricular (dependent layering, hydrocephalus risk).' },
      { t: 'Cisterns', d: 'The basal cisterns (suprasellar, perimesencephalic, quadrigeminal) must be open and symmetric. Effacement = mass effect/herniation; blood in cisterns = SAH. Know herniation patterns: subfalcine (midline shift), uncal (effaced suprasellar cistern, dilated contralateral temporal horn, CN III), central, tonsillar.' },
      { t: 'Brain parenchyma', d: 'Grey–white differentiation intact? Early infarct signs: loss of the insular ribbon, obscured lentiform nucleus, sulcal effacement, hyperdense vessel (MCA) sign. Hypodensity respecting a vascular territory = infarct; not respecting territories = edema/tumor/infection. Check symmetry systematically, including posterior fossa (beam-hardening territory — be deliberate).' },
      { t: 'Ventricles', d: 'Size appropriate for age? Dilated out of proportion to sulci = hydrocephalus (temporal horns dilate early); effaced = swelling. Trapped horn, colloid cyst at the foramen of Monro, shunt catheter position.' },
      { t: 'Bone and air spaces', d: 'Bone windows: skull vault and base fractures (distinguish from sutures — sutures are corticated, bilateral, at known sites), facial bones. Air–fluid levels in sphenoid/mastoids suggest basilar fracture; intracranial air = dural breach. Scalp hematoma marks the coup site — look contrecoup for contusion.' },
      { t: 'Review areas', d: 'Highest vertex slices, orbits, sella, craniocervical junction and odontoid on scout/sagittal, soft tissues of neck on included slices.' }
    ],
    pearls: [
      'Symmetry is your friend but midline pathology (central herniation, bilateral subdurals) can look deceptively "symmetric" — check cistern spaces and sulci against expected age norms.',
      'Subacute subdural becomes isodense to cortex (~1–3 weeks): look for displaced grey-white interface and effaced sulci that do not reach the skull.',
      'CT is near-perfect for SAH within 6 hours of headache onset; sensitivity falls with time.',
      'An elderly or anticoagulated patient with trauma warrants a low threshold for repeat imaging — delayed hemorrhage happens.'
    ],
    misses: [
      'Thin convexity or tentorial subdural on brain windows only.',
      'Isodense subacute subdural hematoma.',
      'Early ischemia — subtle grey-white loss (use stroke windows).',
      'Basilar skull fracture signaled only by a sphenoid air-fluid level.',
      'Cerebral venous sinus thrombosis (hyperdense sinus/cord sign) in the young headache patient.'
    ]
  },

  {
    id: 'cspine-ct',
    name: 'Cervical Spine CT (Trauma)',
    icon: '🦒',
    scope: 'both',
    intro: `<p>CT has replaced radiographs for adult trauma c-spine clearance (use NEXUS/Canadian C-spine rules for who to image). The read is alignment → bones → cartilage/joints → soft tissues, on all three planes.</p>`,
    steps: [
      { t: 'Alignment on sagittal images', d: 'Four lines: anterior vertebral, posterior vertebral, spinolaminar, spinous process tips. Smooth lordotic curves; any step-off is a finding. Check the craniocervical junction specifically: basion–dens interval &lt;8.5–9.5 mm (CT), atlanto-dental interval &lt;3 mm adult / &lt;5 mm child.' },
      { t: 'Bone integrity, vertebra by vertebra', d: 'Trace every cortex on sagittal and axial: C1 ring (Jefferson burst), odontoid (type I–III), C2 pars (hangman), vertebral bodies (compression vs burst — check posterior wall retropulsion), facets, laminae, spinous processes (clay-shoveler).' },
      { t: 'Joints and spacing', d: 'Facet alignment (perched/jumped facets — "naked facet" on axial), interspinous distance (widening = posterior ligamentous injury), disc spaces (widened disc = distraction injury).' },
      { t: 'Soft tissues', d: 'Prevertebral soft tissue thickness (~&lt;7 mm at C2, &lt;22 mm at C7 in adults) — swelling may be the only clue to ligamentous injury. Check vertebral artery foramina fractures (transverse foramen involvement → CTA per criteria).' },
      { t: 'Know when CT is not enough', d: 'Obtunded patients, neurologic deficits with normal CT, or suspected ligamentous/cord injury → MRI (STIR for ligaments and marrow, cord signal). SCIWORA (cord injury without CT abnormality) is classically pediatric.' }
    ],
    pearls: [
      'Pseudosubluxation of C2 on C3 (up to ~3 mm, spinolaminar line intact) is a normal pediatric variant.',
      'In children the fulcrum is higher (C2–C3) and the odontoid synchondrosis can mimic fracture — know the synchondroses.',
      'One spine fracture found = image the whole spine; non-contiguous fractures are common.',
      'Ankylosed spines (AS/DISH) fracture through disc spaces with minimal trauma and are unstable — scan generously.'
    ],
    misses: [
      'Craniocervical dissociation with "nearly normal" alignment.',
      'Type II odontoid fracture in osteopenic elderly.',
      'Facet fracture-subluxation seen only on one plane.',
      'Vertebral artery injury with transverse foramen fracture.'
    ]
  },

  {
    id: 'chest-ct',
    name: 'Chest CT',
    icon: '🌬️',
    scope: 'adult',
    intro: `<p>Read chest CT as loops through systems, each in its best window: lungs (lung window), mediastinum/hila (soft tissue), pleura, heart/vessels, bones, upper abdomen. On CTPA add a dedicated pulmonary artery sweep.</p>`,
    steps: [
      { t: 'Scout, technique, comparison', d: 'Phase (non-contrast, CTA, venous), slice thickness, inspiration adequacy, priors for nodule change.' },
      { t: 'Airways', d: 'Trachea and bronchi to segmental level: endoluminal lesions, wall thickening, bronchiectasis (signet ring, lack of tapering), mucus plugging.' },
      { t: 'Lungs — pattern-based', d: 'Nodules (size, density: solid/part-solid/ground-glass, location — Fleischner follow-up applies to incidentals). Consolidation vs ground-glass opacity. Interstitial pattern: reticulation, honeycombing (UIP = basal/peripheral honeycombing + traction bronchiectasis), septal thickening (smooth = edema/lymphangitic). Distribution is diagnosis: upper vs lower, central vs peripheral, perilymphatic vs centrilobular vs random for micronodules. Mosaic attenuation: air trapping vs vascular.' },
      { t: 'Pleura', d: 'Effusion density (simple vs hemothorax ~35–70 HU), loculation, enhancing thickened pleura (empyema — split pleura sign), pneumothorax, plaques (asbestos), nodularity (mets/mesothelioma).' },
      { t: 'Mediastinum and hila', d: 'Nodal stations — short axis &gt;1 cm generally abnormal (size alone is imperfect). Thymus, thyroid extension, esophagus (wall thickening, dilation), anterior/middle/posterior compartment masses differential.' },
      { t: 'Heart and vessels', d: 'Coronary calcification (report it), chamber size, pericardial effusion/thickening. Aorta: aneurysm, dissection flap, intramural hematoma (crescentic high density on non-contrast). Pulmonary arteries on CTPA: filling defects central to subsegmental; RV strain signs (RV:LV &gt;1, septal bowing, reflux into IVC).' },
      { t: 'Bones and soft tissues', d: 'Sclerotic/lytic lesions in every vertebra and rib on bone windows, shoulder girdle, sternum (fractures post-trauma/CPR), breast tissue (masses seen on CT need dedicated workup), axillae, chest wall.' },
      { t: 'Upper abdomen review', d: 'Adrenals (nodules), liver dome lesions, upper pole kidneys, stomach — the imaged abdomen is your responsibility.' }
    ],
    pearls: [
      'Always scroll lungs on cine with a fixed window; nodules pop with motion better than with staring.',
      'RV:LV ratio and septal flattening on CTPA convert "PE present" into "PE with strain" — a management-changing distinction.',
      'Intramural hematoma is invisible on arterial phase alone — check the non-contrast series.',
      'Fleischner guidelines apply only to incidental nodules in adults ≥35 without cancer or immunosuppression.'
    ],
    misses: [
      'Subsegmental PE and in-transit clot on suboptimal opacification.',
      'Breast mass at the edge of the field.',
      'Adrenal nodule and thyroid nodule on the first/last slices.',
      'Esophageal thickening (cancer) behind the heart.',
      'Sternal or scapular fracture after trauma.'
    ]
  },

  {
    id: 'ct-ap',
    name: 'CT Abdomen & Pelvis',
    icon: '🍑',
    scope: 'both',
    intro: `<p>Organ-by-organ loops beat freestyle scrolling. Note the phase — many "lesions" are phase artifacts, and many real lesions need a specific phase to show. Finish with the mandatory review areas.</p>`,
    steps: [
      { t: 'Technique and phase', d: 'Oral/IV contrast? Which phase(s)? Portal venous is the workhorse; arterial for bleeding/hypervascular lesions; delayed for urothelium.' },
      { t: 'Liver, biliary, gallbladder', d: 'Parenchymal density (steatosis: liver &gt;10 HU less than spleen), focal lesions (cyst/hemangioma/mets — enhancement pattern), portal and hepatic vein patency. Gallbladder: stones, wall &gt;3 mm, pericholecystic fat stranding. Ducts: CBD ≤6 mm (older/post-chole allowances), intrahepatic dilation.' },
      { t: 'Spleen, pancreas, adrenals', d: 'Spleen size (≤~13 cm) and lesions. Pancreas: enhancement (necrosis in pancreatitis), ductal dilation (&gt;3 mm — with atrophy think obstructing mass), peripancreatic stranding, cystic lesions. Adrenals: nodules — ≤10 HU non-contrast = adenoma.' },
      { t: 'Kidneys, ureters, bladder', d: 'Symmetric nephrograms (delayed/striated = obstruction, pyelonephritis), stones (nearly all opaque on CT), hydronephrosis, masses (enhancement &gt;15–20 HU = solid), perinephric stranding. Trace both ureters end to end. Bladder wall, diverticula, intraluminal lesions.' },
      { t: 'GI tract — trace it', d: 'Stomach to rectum: wall thickening (small bowel &gt;3 mm, colon segmentally), dilation with transition point (SBO — hunt the point, check for closed loop and ischemia: reduced wall enhancement, mesenteric edema, whirl), appendix (find it: &gt;6 mm, fat stranding, appendicolith), diverticulitis, pneumatosis.' },
      { t: 'Peritoneum, mesentery, retroperitoneum', d: 'Free fluid (density! simple vs blood — sentinel clot marks the injured organ), free air (lung windows help find tiny bubbles), fat stranding follows disease, mesenteric/portal venous gas, nodularity/omental caking (carcinomatosis), retroperitoneal nodes and hematoma.' },
      { t: 'Vessels', d: 'Aorta (aneurysm ≥3 cm; rupture signs: draped aorta, retroperitoneal hematoma), iliac vessels, SMA/SMV patency and orientation (SMV should sit right of SMA — reversed = malrotation), portal vein, IVC filling defects.' },
      { t: 'Pelvic organs', d: 'Uterus/adnexa (ovarian cysts by menopausal-status rules; a dermoid has fat and calcium), prostate/seminal vesicles, rectum. Free pelvic fluid: small amount physiologic in reproductive-age women.' },
      { t: 'Bones, soft tissues, lung bases, review areas', d: 'Every vertebra and both hips on bone windows; abdominal wall (hernias — hunt the hernial orifices), inguinal canals, lung bases (nodules, PE on venous phase sometimes visible, effusions). Corners of every image.' }
    ],
    pearls: [
      'Fat stranding is your searchlight: find the stranding, then find the organ that caused it.',
      'Measure fluid density routinely — hemoperitoneum changes the differential instantly.',
      'In SBO, the small-bowel feces sign helps localize the transition.',
      'The normal appendix must be actively found in the RLQ pain patient; "not seen" is a real result only after a real search.'
    ],
    misses: [
      'The second finding: satisfaction of search after the obvious diagnosis (find the appendicitis AND the ovarian lesion).',
      'Aortoenteric fistula and mycotic aneurysm in the septic patient.',
      'Internal hernia with closed-loop obstruction.',
      'Isolated free air from a tiny perforation — check lung windows under the anterior abdominal wall.',
      'Bone metastases in every trauma and cancer scan.'
    ]
  },

  {
    id: 'brain-mri',
    name: 'Brain MRI',
    icon: '🧲',
    scope: 'both',
    intro: `<p>Read brain MRI sequence-by-sequence with a purpose for each pass, then synthesize. Identify each sequence before interpreting it (find the CSF).</p>`,
    steps: [
      { t: 'DWI/ADC first in any acute setting', d: 'Bright DWI + dark ADC = restriction: acute infarct (respect vascular territories; check both MCA, ACA, PCA, watershed, posterior fossa), abscess core, hypercellular tumor, CJD cortex. Confirm on ADC to exclude shine-through.' },
      { t: 'FLAIR pass', d: 'Edema, gliosis, demyelination (periventricular ovoid Dawson fingers), cortical signal (encephalitis — medial temporal in HSV), sulcal hyperintensity (SAH, meningitis, slow flow).' },
      { t: 'T2 pass', d: 'Lesion characterization, ventricles and extra-axial spaces, posterior fossa detail, flow voids of major vessels (absent flow void = thrombosis/occlusion?).' },
      { t: 'T1 pass', d: 'Anatomy, atrophy pattern, intrinsic T1-bright things: fat, methemoglobin (subacute blood), melanin, protein, some calcifications, posterior pituitary. Marrow signal in the clivus and calvarium (mets replace bright fatty marrow).' },
      { t: 'GRE/SWI pass', d: 'Blooming: microbleeds (amyloid = lobar, hypertensive = deep), cavernomas, DAI at grey-white junctions, superficial siderosis, dense vein/sinus thrombus.' },
      { t: 'Post-contrast pass (when given)', d: 'Pattern matters: ring (mets, GBM, abscess — thin smooth ring + restricted core favors abscess; tumor rings are thicker/nodular), leptomeningeal vs pachymeningeal enhancement, cranial nerve enhancement.' },
      { t: 'Systematic anatomy loop', d: 'Ventricles/midline (shift, hydrocephalus, corpus callosum), sella/pituitary, cavernous sinuses, orbits, IACs (vestibular schwannoma check on high-res T2), skull base, paranasal sinuses and mastoids, scalp. Cervicomedullary junction and visible upper cord.' },
      { t: 'Localize then differentiate', d: 'Intra-axial vs extra-axial (CSF cleft, buckled grey matter, dural tail = extra-axial, likely meningioma). Single vs multiple (multiple at grey-white junction = mets). Age and immune status reshape every differential.' }
    ],
    pearls: [
      'The ADC map is the honesty check for every "bright DWI" claim.',
      'An incomplete ring of enhancement (open toward cortex) favors demyelination over tumor/abscess.',
      'Symmetric signal abnormality suggests toxic/metabolic causes; asymmetric favors vascular/neoplastic/infectious.',
      'In children, the myelination stage changes normal signal — compare against age-matched norms before calling white matter disease.'
    ],
    misses: [
      'Small acute infarct visible only on DWI.',
      'Dural venous sinus thrombosis (check flow voids and post-contrast filling defects).',
      'Pituitary and IAC lesions outside the "brain proper".',
      'Leptomeningeal carcinomatosis without a parenchymal met.',
      'Skull-base marrow replacement on T1.'
    ]
  },

  {
    id: 'msk-xr',
    name: 'MSK Radiograph & Fracture Description',
    icon: '🦴',
    scope: 'both',
    intro: `<p>Two jobs: find the abnormality (ABCS) and describe it so a surgeon can treat from your words. Always two views, always the joint above and below for forearm/leg injuries.</p>`,
    steps: [
      { t: 'A — Adequacy & Alignment', d: 'Correct views (a fracture invisible on AP may be obvious on lateral — and vice versa). Joint congruity, dedicated alignment lines by region (e.g., anterior humeral line and radiocapitellar line at the elbow; Shenton line at the hip; carpal arcs at the wrist).' },
      { t: 'B — Bones', d: 'Trace every cortex out loud with your eyes; a cortical step, break, or buckle is a fracture. Then trabecular pattern (impaction bands), density (lucent lesions, sclerosis, periosteal reaction — aggressive vs benign).' },
      { t: 'C — Cartilage & joints', d: 'Joint space width (symmetric loss = inflammatory; asymmetric weight-bearing loss + osteophytes = OA), erosions (marginal in RA; juxta-articular with overhanging edge in gout), chondrocalcinosis (CPPD), subchondral lucency (osteochondral lesions, AVN crescent).' },
      { t: 'S — Soft tissues', d: 'Effusions (elbow fat pads: visible posterior fat pad = effusion = occult fracture in trauma; suprapatellar fullness at the knee; lipohemarthrosis = intra-articular fracture), swelling, foreign bodies, gas, calcifications.' },
      { t: 'Describe the fracture completely', d: 'Which bone + which part (proximal/middle/distal third; intra-articular?), pattern (transverse/oblique/spiral/comminuted/segmental), displacement (of the DISTAL fragment, in %), angulation (direction of apex or distal fragment — state your convention), shortening, rotation, open vs closed correlation.' },
      { t: 'Pediatric fracture types', d: 'Buckle (torus), greenstick, plastic bowing, and physeal injuries by Salter-Harris: I through the physis, II physis+metaphysis (most common), III physis+epiphysis (intra-articular), IV through all, V crush. SALTR mnemonic: Slipped/Above/Lower/Through/Rammed.' },
      { t: 'The "second fracture" and associations rule', d: 'Ring structures break twice (pelvis, mandible, forearm — a "single" forearm fracture demands elbow and wrist views: Monteggia = ulna fracture + radial head dislocation; Galeazzi = radius fracture + DRUJ injury). Calcaneal fracture → check spine (axial load).' }
    ],
    pearls: [
      'The posterior fat pad rule at the elbow: trauma + effusion + no visible fracture = treat as occult fracture (supracondylar in children, radial head in adults).',
      'Scaphoid, hip, and tibial plateau fractures can be radiographically occult — clinical suspicion trumps a normal film; MRI or CT settles it.',
      'Periosteal reaction: solid/thick = benign/slow; lamellated, spiculated (sunburst), or Codman triangle = aggressive.',
      'Compare with the contralateral side in children rather than over-calling normal physes.'
    ],
    misses: [
      'Second fractures in ring structures and the joint above/below.',
      'Posterior shoulder dislocation on a single AP view (light-bulb sign — get axillary/Y view).',
      'Lisfranc injury: alignment of 2nd metatarsal base with middle cuneiform on weight-bearing views.',
      'Pathologic fracture through a lytic lesion — look at the bone, not just the break.',
      'Salter-Harris I with normal-looking films (physeal tenderness).'
    ]
  },

  {
    id: 'us-approach',
    name: 'Ultrasound Study Approach',
    icon: '🔊',
    scope: 'both',
    intro: `<p>Interpreting ultrasound means judging both the anatomy and the scan quality: was the target adequately interrogated? A negative study is only negative if the sweep was complete.</p>`,
    steps: [
      { t: 'Orient yourself', d: 'Probe marker convention: in transverse the marker points to the patient\'s right (screen left); in sagittal it points cephalad. Check depth, gain, and focus appropriateness on the saved images.' },
      { t: 'Characterize every lesion the same way', d: 'Location, size (3 axes), echogenicity vs host organ, contents (uniform, debris, septations, mural nodules), margins, posterior artifacts (enhancement vs shadowing), vascularity (color/power Doppler), compressibility/mobility where relevant.' },
      { t: 'Apply strict simple-cyst criteria', d: 'Anechoic + imperceptible wall + posterior enhancement + no internal flow = simple cyst. Any missing criterion = complex → apply organ-specific rules (thyroid TI-RADS, ovarian O-RADS, renal Bosniak logic via CT/MR).' },
      { t: 'Use dynamic maneuvers', d: 'Sonographic Murphy (cholecystitis), graded compression (appendix, DVT — a compressible vein excludes thrombus at that level), Valsalva (varicocele, hernia), positional rolling (mobile stones vs fixed polyps).' },
      { t: 'Doppler with intent', d: 'Set scale/gain for the question: high-sensitivity power Doppler for torsion and slow flow; spectral waveforms for stenosis, resistive indices, portal flow direction (hepatofugal = portal hypertension).' },
      { t: 'Document negatives that matter', d: 'Normal appendix seen, ovaries with flow, lung sliding present — the pertinent negative is a finding.' }
    ],
    pearls: [
      'Artifacts confirm diagnoses: clean shadow = stone; dirty shadow = gas; enhancement = fluid; twinkle = calculus.',
      'The most common cause of "no flow" is technique — verify settings on a normal structure before calling torsion or thrombosis.',
      'WES sign (wall-echo-shadow) = gallbladder packed with stones, easy to miss as bowel gas.'
    ],
    misses: [
      'Torsed ovary with "normal" arterial flow (venous flow lost first; an enlarged edematous ovary with peripheral follicles is the key finding).',
      'Retrocecal appendix not seen on graded compression.',
      'Isoechoic lesions (thyroid, testis, liver) without careful sweep + Doppler.',
      'Ectopic pregnancy with an "empty uterus" and positive hCG — free fluid and adnexal ring.'
    ]
  },

  {
    id: 'reporting',
    name: 'Structured Reporting & Communication',
    icon: '📝',
    scope: 'both',
    intro: `<p>The report is the product. A great search wasted on a vague report helps no one. Structure, clarity, and closed-loop communication of critical results are core interpretive skills.</p>`,
    steps: [
      { t: 'Frame the clinical question', d: 'Read the history, then restate the question in your head. Every impression must answer it explicitly — even if the answer is "no evidence of X".' },
      { t: 'Standard report skeleton', d: 'Exam & technique (modality, contrast, phases) → Comparison (name the date) → Findings (organ-by-organ, same order every time) → Impression (numbered, most important first, each item actionable).' },
      { t: 'Findings language discipline', d: 'Describe, then conclude — "a 3 cm spiculated right upper lobe mass" (finding) before "suspicious for primary lung malignancy" (interpretation). Measure reproducibly (series/image numbers for follow-up). Avoid hedging stacks ("cannot exclude possible") — quantify confidence instead.' },
      { t: 'The impression is triage', d: 'Numbered, ranked by importance. Answer the clinical question first. Include concrete next steps with justification (e.g., Fleischner category for nodules, adrenal washout protocol, MRI for characterization). Never bury a critical finding at item 5.' },
      { t: 'Critical results — closed loop', d: 'Emergent findings (tension pneumothorax, midgut volvulus, free air, PE with strain, unexpected hemorrhage, malpositioned airway/lines, ectopic pregnancy) require direct verbal communication to the treating clinician, documented with name and time in the report.' },
      { t: 'Compare, addend, and own errors', d: 'Compare against the oldest useful prior for slow processes. When new information changes your read, addend promptly and communicate. Peer-learning from misses is how search patterns improve.' }
    ],
    pearls: [
      'Write the impression for the 2 a.m. intern: short sentences, no unexplained jargon, actions explicit.',
      'Pertinent negatives targeted to the question ("no free air; normal appendix") add more value than boilerplate normals.',
      'If a finding needs follow-up imaging, name the modality AND the interval.',
      'Dictate findings in the same anatomic order you search — the checklist and the report reinforce each other.'
    ],
    misses: [
      'The unanswered clinical question ("evaluate for PE" report that never says PE present/absent).',
      'Critical result documented but never verbally communicated.',
      'Incidental findings with no follow-up recommendation (adrenal nodule, thyroid nodule, aneurysm).',
      'Copy-forward errors from a prior report template.'
    ]
  },

  {
    id: 'search-cognition',
    name: 'Search Patterns & Cognitive Error',
    icon: '🧭',
    scope: 'both',
    intro: `<p>Most radiologic error is perceptual or cognitive, not knowledge failure. Training your search pattern and knowing your failure modes is as important as knowing the findings.</p>`,
    steps: [
      { t: 'Commit to a fixed scan order per study type', d: 'The order matters less than its consistency. A ritual immunizes you against distraction and lets you notice when a step was skipped.' },
      { t: 'Satisfaction of search — the big one', d: 'After ANY positive finding, deliberately restart the checklist: "I found the fracture; now I look for the second fracture, the effusion, the lung nodule at the film edge." One finding statistically blinds you to the next.' },
      { t: 'Anchoring & framing', d: 'The clinical history is a hypothesis, not a verdict. Read once with the history in mind and once against it ("what else could this be?"). Beware the handoff diagnosis ("known pneumonia") that was never actually proven.' },
      { t: 'Satisfaction of report / alliterative error', d: 'The prior report\'s language biases you to repeat it. Re-read the images, not the prior impression — errors propagate down report chains.' },
      { t: 'Use gaze-forcing tools', d: 'Review areas lists (film corners, review areas per modality), inverted grayscale for subtle lung nodules, cine scrolling at fixed windows, side-by-side symmetric comparison, and comparison with the OLDEST prior for slow change.' },
      { t: 'Calibrate confidence and fatigue', d: 'Error rates rise with shift length, interruption, and case-volume pressure. Flag low-confidence reads for second review; discrepancy/peer-learning review of your own misses is the fastest route to a better search pattern.' }
    ],
    pearls: [
      'The most commonly missed finding is the second one.',
      '"Where would I hide a finding on this study?" is a productive final question — then look there.',
      'Perception research: most misses were fixated on but not recognized — slow down at review areas, do not just glance.',
      'Checklists feel slow for the first month and become automatic (and faster) after.'
    ],
    misses: [
      'Second fractures, second nodules, second tumors.',
      'The corners of every image and the first/last slices of every stack.',
      'Findings contradicting the provided history.',
      'Slow-growing lesions "stable" against last week\'s film.'
    ]
  }
];

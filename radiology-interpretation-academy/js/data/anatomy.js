/* Radiology Interpretation Academy — Radiologic anatomy by region (adult + pediatric). */
window.RIA = window.RIA || {};
RIA.data = RIA.data || {};

RIA.data.anatomy = [
  {
    id: 'brain',
    name: 'Brain (CT & MRI)',
    icon: '🧠',
    intro: `<p>Learn the brain by <strong>axial CT levels</strong> plus <strong>vascular territories</strong> — nearly every emergency read hangs on these two frameworks.</p>`,
    sections: [
      {
        h: 'Key axial CT levels (caudal to cranial)',
        body: `<ul>
          <li><strong>Posterior fossa level</strong> — medulla/pons anteriorly, cerebellum posteriorly, fourth ventricle between them (a thin midline crescent; effacement = posterior fossa mass effect). Petrous bones cause beam-hardening streaks here.</li>
          <li><strong>Midbrain level</strong> — the "Mickey Mouse" midbrain within the suprasellar/perimesencephalic cisterns; interpeduncular fossa; temporal horns (should be barely visible slits — visible dilation = early hydrocephalus); circle of Willis vessels.</li>
          <li><strong>Basal ganglia level</strong> — the classic level: frontal horns, caudate heads, anterior limb / genu / posterior limb of internal capsule, lentiform nucleus (putamen + globus pallidus), thalami flanking the third ventricle, insula with the <em>insular ribbon</em> lateral to it. Hypertensive hemorrhage and lacunes live here.</li>
          <li><strong>Ventricular body level</strong> — lateral ventricle bodies, corpus callosum between them, centrum semiovale white matter.</li>
          <li><strong>Vertex / high convexity</strong> — paired parasagittal cortex; the falx; convexity subdurals and parasagittal (ACA-territory) infarcts hide up here.</li>
        </ul>`
      },
      {
        h: 'Vascular territories',
        body: `<ul>
          <li><strong>ACA</strong> — medial frontal/parietal strip (leg weakness).</li>
          <li><strong>MCA</strong> — lateral hemisphere convexity, basal ganglia via lenticulostriates (face/arm, language on the dominant side). Largest and most commonly infarcted.</li>
          <li><strong>PCA</strong> — occipital lobe and medial temporal (visual field cuts).</li>
          <li><strong>Basilar/vertebral</strong> — brainstem, cerebellum (PICA/AICA/SCA), thalami (via perforators and PCA).</li>
          <li><strong>Watershed zones</strong> — border strips between ACA/MCA and MCA/PCA; infarcted in hypotension ("string of pearls" deep watershed).</li>
        </ul>
        <p>An area of hypodensity that maps to one territory = infarct; crossing territories = think edema, tumor, infection, or venous infarction (venous territories follow sinuses, not arteries — parasagittal for the superior sagittal sinus, temporal for the vein of Labbé/transverse sinus).</p>`
      },
      {
        h: 'Grey–white and the deep landmarks',
        body: `<p>Grey matter is denser (whiter) than white matter on CT; loss of that distinction is the earliest infarct sign (insular ribbon, lentiform obscuration). On MRI T1 the relationship reverses visually (white matter brighter, from myelin). Know on sight: internal capsule limbs, corona radiata, corpus callosum (genu/body/splenium), pineal region, sella and pituitary, cavernous sinuses (carotid flow voids, cranial nerves III–VI).</p>`
      },
      {
        h: 'Extra-axial spaces and dura',
        body: `<p>The dura defines compartments: falx and tentorium do not let subdural blood cross midline (but sutures do not stop it); epidural blood is bounded by sutures (but can cross midline). CSF spaces: sulci should reach the inner table symmetrically; basal cisterns open. Age matters — generous sulci are normal atrophy in the elderly and abnormal in a 30-year-old.</p>`
      }
    ],
    peds: `<p><strong>Pediatric:</strong> Neonatal brain is best screened with cranial US through the anterior fontanelle: germinal matrix hemorrhage grading (I caudothalamic groove → IV parenchymal), ventricular size, periventricular flare. Myelination progresses posterior→anterior, central→peripheral, complete by ~2 years on T2 — do not read an unmyelinated infant brain against adult norms. Open sutures and fontanelles change fracture mechanics and allow head growth in chronic hydrocephalus (macrocephaly). The pediatric posterior fossa deserves extra care: medulloblastoma, pilocytic astrocytoma, ependymoma are the classic midline/paramidline tumors.</p>`
  },

  {
    id: 'headneck',
    name: 'Head & Neck',
    icon: '👤',
    intro: `<p>Head and neck imaging is compartment thinking: sinuses and facial skeleton, orbits, temporal bones, and the fascia-defined neck spaces.</p>`,
    sections: [
      {
        h: 'Paranasal sinuses & facial skeleton',
        body: `<p>Maxillary, ethmoid, frontal, sphenoid sinuses — aerated black on CT; mucosal thickening, air–fluid levels (acute sinusitis or fracture blood), and the ostiomeatal complex drainage pathway. Facial buttresses organize fracture patterns: orbital blowout (floor/medial wall — check for muscle herniation and the "teardrop"), zygomaticomaxillary complex, Le Fort I–III (all involve the pterygoid plates), mandible (a ring — expect two fractures).</p>`
      },
      {
        h: 'Orbits',
        body: `<p>Globe, lens, optic nerve/sheath, extraocular muscles (enlarged bellies sparing tendons = thyroid eye disease; tendon involvement = pseudotumor), intraconal vs extraconal compartments, superior ophthalmic vein. Never MRI a suspected metallic orbital foreign body.</p>`
      },
      {
        h: 'Neck spaces (suprahyoid & infrahyoid)',
        body: `<ul>
          <li><strong>Parapharyngeal fat</strong> — the displacement compass: which way the fat moves tells you which space a mass arose from.</li>
          <li><strong>Pharyngeal mucosal space</strong> — squamous cell carcinoma territory; tonsils, adenoids (large in kids, normal).</li>
          <li><strong>Parotid & masticator spaces</strong> — salivary tumors; odontogenic infection spread.</li>
          <li><strong>Carotid space</strong> — vessels, paraganglioma, nerve sheath tumors.</li>
          <li><strong>Retropharyngeal & danger spaces</strong> — abscess highway to the mediastinum; in children retropharyngeal abscess is common (node suppuration).</li>
          <li><strong>Visceral space</strong> — thyroid, larynx, trachea, esophagus.</li>
        </ul>
        <p>Lymph node levels I–VII organize cancer staging; a necrotic node is metastatic (or in the right setting, suppurative/TB) regardless of size.</p>`
      },
      {
        h: 'Temporal bone (orientation level)',
        body: `<p>External canal → tympanic membrane → ossicles in the middle ear → labyrinth (cochlea, vestibule, semicircular canals) → internal auditory canal (CN VII/VIII). Mastoid air cells opacify in otomastoiditis. Cholesteatoma erodes the scutum and ossicles.</p>`
      }
    ],
    peds: `<p><strong>Pediatric:</strong> Adenoids and tonsils are normally prominent — size alone is not pathology. Retropharyngeal soft tissue on lateral neck: roughly less than half a vertebral body width at C2–C4; crying/flexion fakes thickening. Croup (steeple sign) vs epiglottitis (thumb sign) vs retropharyngeal abscess is a lateral-neck-film classic triad. Congenital neck masses by location: midline moving with swallowing = thyroglossal duct cyst; lateral along SCM = branchial cleft cyst; posterior triangle trans-spatial = lymphatic malformation.</p>`
  },

  {
    id: 'spine',
    name: 'Spine',
    icon: '🦴',
    intro: `<p>Spine anatomy reading is lines, columns, and levels — the same on radiograph, CT, and MRI.</p>`,
    sections: [
      {
        h: 'The building blocks',
        body: `<p>Vertebral body, pedicles (owl\'s eyes on AP — a missing pedicle is classic for metastasis), transverse processes, facet (zygapophyseal) joints, laminae meeting at the spinous process. Disc = annulus + nucleus. Cord ends at ~L1–L2 in adults (conus), below which the cauda equina fills the thecal sac. Cervical: C1 (no body) and C2 (dens) are unique — learn them on all planes.</p>`
      },
      {
        h: 'Alignment lines & normal measurements',
        body: `<ul>
          <li>Anterior vertebral, posterior vertebral, spinolaminar, spinous-tip lines — smooth curves on lateral views.</li>
          <li>Atlanto-dental interval: &lt;3 mm adult, &lt;5 mm child.</li>
          <li>Prevertebral soft tissue (cervical): ~&lt;7 mm at C2, &lt;22 mm at C7 (adult).</li>
          <li>Vertebral body heights and disc spaces should transition gradually; an abrupt change is a finding.</li>
        </ul>
        <p>Three-column concept (Denis): anterior and middle columns (body + posterior wall) and posterior elements; two-column failure = unstable.</p>`
      },
      {
        h: 'MRI layers',
        body: `<p>Sagittal T2 is the survey: bright CSF outlines the cord (uniform caliber and signal), discs (bright nucleus when young, desiccated dark with age), marrow (fatty bright on T1 in adults; diffuse T1-dark marrow = infiltration or hematopoietic reconversion). STIR lights up acute fractures (edema) vs old collapsed vertebrae. Post-contrast for infection (discitis-osteomyelitis: disc-centered enhancement + endplate destruction) vs metastasis (body-centered, disc-sparing).</p>`
      },
      {
        h: 'Degenerative vocabulary',
        body: `<p>Disc bulge vs protrusion vs extrusion vs sequestration (migrated free fragment); central canal vs lateral recess vs foraminal stenosis; the exiting nerve root leaves UNDER its pedicle (L4-L5 paracentral disc typically hits the traversing L5 root; a far-lateral disc hits the exiting L4 root). Modic endplate changes I–III.</p>`
      }
    ],
    peds: `<p><strong>Pediatric:</strong> Normal synchondroses of C2 mimic fractures; pseudosubluxation C2-on-C3 is normal (intact spinolaminar line). The infant cord can be screened by ultrasound before posterior element ossification (~3–4 months): conus should sit at or above L2–L3 — lower suggests tethering. Scheuermann disease, spondylolysis (pars defects in young athletes — oblique "Scotty dog collar"), and the higher cervical fulcrum (C2–C3) in young children are staples.</p>`
  },

  {
    id: 'chest',
    name: 'Chest & Mediastinum',
    icon: '🫁',
    intro: `<p>Chest anatomy for interpreters: lobes and fissures, the hila, the mediastinal lines and compartments, and how each rib of anatomy explains a silhouette.</p>`,
    svg: 'cxr',
    sections: [
      {
        h: 'Lobes, fissures, segments',
        body: `<p>Right lung: upper, middle, lower lobes; minor (horizontal) fissure visible on frontal and lateral, major (oblique) fissure on lateral. Left lung: upper (including lingula) and lower lobes; single oblique fissure. Each lobe divides into bronchopulmonary segments — segmental consolidation follows bronchial anatomy. Lobar collapse has signatures: RUL collapse tents the minor fissure upward (Golden S with a central mass); LLL collapse hides behind the heart (sail/double-density); RML collapse blurs the right heart border.</p>`
      },
      {
        h: 'Silhouette localization map',
        body: `<ul>
          <li>Right heart border ↔ right middle lobe (medial segment).</li>
          <li>Left heart border ↔ lingula.</li>
          <li>Right hemidiaphragm ↔ right lower lobe; left hemidiaphragm ↔ left lower lobe.</li>
          <li>Ascending aorta/right paratracheal ↔ right upper lobe (anterior segment).</li>
          <li>Aortic knob ↔ left upper lobe (apicoposterior).</li>
        </ul>`
      },
      {
        h: 'Hila',
        body: `<p>The hilar shadows are the pulmonary arteries and superior pulmonary veins (bronchi are lucent; normal nodes are invisible on radiographs). Left hilum sits up to 1.5 cm higher than right. Hilar enlargement: bilateral & lumpy = adenopathy (sarcoid classic) or pulmonary arterial hypertension (smooth); unilateral = mass/adenopathy until explained.</p>`
      },
      {
        h: 'Mediastinal compartments & lines',
        body: `<p>Compartments (lateral view): <strong>anterior</strong> (thymus, thyroid extension, teratoma/germ cell, lymphoma — the "terrible T\'s"), <strong>middle</strong> (nodes, duplication cysts, aortic arch), <strong>posterior</strong> (neurogenic tumors, esophageal lesions, descending aorta). Frontal-film lines that break when disease appears: right paratracheal stripe (&lt;5 mm), azygoesophageal recess, aortopulmonary window (concave/straight; convex = mass or nodes), paraspinal lines.</p>`
      }
    ],
    peds: `<p><strong>Pediatric:</strong> The thymus dominates the infant anterior mediastinum (sail/wave/notch signs) and can involute with stress then rebound. Normal infant airways are compliant — buckling of the trachea on expiration/flexion is normal, not a mass. Pediatric mediastinal masses by compartment: anterior = lymphoma/germ cell; middle = foregut duplication cysts and adenopathy (TB); posterior = neuroblastoma family until proven otherwise.</p>`
  },

  {
    id: 'cardiac',
    name: 'Cardiac & Great Vessels',
    icon: '❤️',
    intro: `<p>Reading the cardiomediastinal silhouette means knowing which chamber makes which border — then CT/MRI confirms chamber-level detail.</p>`,
    sections: [
      {
        h: 'Borders on the frontal radiograph',
        body: `<ul>
          <li><strong>Right border</strong> (top→bottom): SVC, ascending aorta (in elders), right atrium.</li>
          <li><strong>Left border</strong>: aortic knob, main pulmonary artery, left atrial appendage (straightening = LA enlargement), left ventricle.</li>
          <li>Left atrium enlarges invisibly at first: splayed carina (&gt;90°), double density behind the right heart, posterior displacement of the esophagus.</li>
          <li>RV enlargement fills the retrosternal space on the lateral; LV enlargement extends the apex down-and-out.</li>
        </ul>`
      },
      {
        h: 'Vascular pedicle & pulmonary vessels',
        body: `<p>Pulmonary vascularity grading: cephalization (upper-lobe vessels ≥ lower on erect film = elevated venous pressure) → interstitial edema (Kerley B lines, peribronchial cuffing) → alveolar edema (perihilar bat-wing). Enlarged central PAs with peripheral pruning = pulmonary arterial hypertension. Main PA on CT ≤ ~29 mm (or smaller than adjacent ascending aorta).</p>`
      },
      {
        h: 'Aorta & great vessels',
        body: `<p>Course: root → ascending (&lt;4 cm) → arch with three branches (brachiocephalic, left common carotid, left subclavian — variants like bovine arch are common) → descending. Dissection classification: Stanford A involves the ascending (surgical), B does not. Right-sided arch with aberrant left subclavian and the diverticulum of Kommerell — a vascular ring cause in children.</p>`
      },
      {
        h: 'Cross-sectional chambers & pericardium',
        body: `<p>On axial CT at the four-chamber level: RA right, RV most anterior (behind sternum), LA most posterior (in front of esophagus), LV left. Interventricular septum bows toward the RV normally — flattening/bowing left = RV pressure/volume overload. Pericardium is a pencil line (&le;2–3 mm); effusion surrounds, fat sits outside. Coronary origins: left main from left sinus, RCA from right sinus — an interarterial course of an anomalous coronary matters.</p>`
      }
    ],
    peds: `<p><strong>Pediatric:</strong> Congenital heart disease reading starts with situs (stomach/liver, atrial morphology), arch side, and pulmonary vascularity: increased = left-to-right shunt (VSD, PDA); decreased + cyanosis = right outflow obstruction (Tetralogy — boot-shaped heart); "egg on a string" = transposition; "snowman" = supracardiac TAPVR. Rib notching + figure-3 contour = coarctation in the older child.</p>`
  },

  {
    id: 'abdomen',
    name: 'Abdomen',
    icon: '🫃',
    intro: `<p>Cross-sectional abdominal anatomy: solid organ segmentation, peritoneal vs retroperitoneal geography, and the vascular map that organizes it all.</p>`,
    sections: [
      {
        h: 'Liver & biliary',
        body: `<p>Couinaud segments I–VIII, divided by the hepatic veins (vertical planes) and portal bifurcation (horizontal): right lobe V–VIII, left lobe II–IVb, caudate I with direct IVC drainage. Portal triads (portal vein + hepatic artery + bile duct) run centrally within segments; hepatic veins run between. CBD ≤6 mm (add allowance with age/post-cholecystectomy); gallbladder wall ≤3 mm. Normal liver spans ≤~16 cm midclavicular.</p>`
      },
      {
        h: 'Pancreas, spleen, adrenals',
        body: `<p>Pancreas drapes over the SMV/SMA (head/uncinate wrap the SMV; tail reaches the splenic hilum); duct ≤3 mm. Spleen ≤~12–13 cm (splenules are common normal variants). Adrenals: inverted-Y/V above the kidneys; limbs should be thinner than the diaphragmatic crura beside them.</p>`
      },
      {
        h: 'Peritoneum vs retroperitoneum',
        body: `<p>Retroperitoneal: <strong>SAD PUCKER</strong> — Suprarenals, Aorta/IVC, Duodenum (2nd–4th parts), Pancreas (except tail), Ureters, Colon (ascending/descending), Kidneys, Esophagus, Rectum. Everything else hangs on mesentery in the peritoneal cavity. Fluid geography: Morison pouch (hepatorenal) and the pelvis are the dependent recesses; the right paracolic gutter is the highway between them. Disease spreads along defined ligaments and mesenteries (gastrocolic, gastrohepatic, transverse mesocolon).</p>`
      },
      {
        h: 'GI tract landmarks',
        body: `<p>Duodenum C-loop frames the pancreatic head; duodenojejunal flexure at the ligament of Treitz (left of midline, at the level of the bulb — the malrotation checkpoint). Small bowel: jejunum (left upper, feathery folds) → ileum (right lower, featureless). Colon frame with haustra; the appendix hangs from the cecal pole (find the ileocecal valve, follow down). Wall thickness: small bowel ≤3 mm distended; colon ≤3–5 mm segmentally.</p>`
      },
      {
        h: 'Vessels',
        body: `<p>Aorta branches in order: celiac (hepatic/splenic/left gastric), SMA (~1 cm below), renals, IMA, bifurcation at ~L4. SMV joins splenic vein behind the pancreatic neck → portal vein. Normal SMA/SMV relationship: vein to the RIGHT of artery (reversal suggests malrotation). Aorta &lt;3 cm; iliacs &lt;1.5 cm.</p>`
      }
    ],
    peds: `<p><strong>Pediatric:</strong> Scant visceral fat makes planes subtle — ultrasound compensates. Age-specific organ rules: infant liver extends below the costal margin normally; the neonatal adrenal is proportionally huge; the pediatric appendix threshold is the same (&gt;6 mm) but graded-compression US is the first test. Pyloric muscle ≥3 mm thick / channel ≥15 mm = hypertrophic pyloric stenosis (2–8 week old with projectile vomiting). Intussusception target sign &gt;2.5 cm in the right abdomen.</p>`
  },

  {
    id: 'pelvis',
    name: 'Pelvis (incl. GU)',
    icon: '🦴',
    intro: `<p>Pelvic anatomy splits into the bony ring, the urinary tract, and sex-specific organs — with ultrasound and MRI carrying most of the soft-tissue work.</p>`,
    sections: [
      {
        h: 'Bony pelvis',
        body: `<p>A ring (expect two breaks). On the AP pelvis trace: iliopectineal (anterior column) and ilioischial (posterior column) lines, acetabular roof, Shenton line (medial femoral neck → superior obturator foramen arc — broken in hip fracture/dislocation/DDH), sacral arcuate lines (sacral fractures hide here), symphysis (≤5 mm) and SI joints (2–4 mm).</p>`
      },
      {
        h: 'Urinary tract',
        body: `<p>Kidneys 9–13 cm with echogenic sinus fat; ureters cross the iliacs at the pelvic brim (a stone checkpoint) and insert at the trigone — the three narrowings (UPJ, pelvic brim, UVJ) are where stones lodge. Bladder wall ≤3 mm distended. Prostate ≤~30 mL classic normal; zonal anatomy on MRI (peripheral zone T2-bright — most cancers; transition zone — BPH).</p>`
      },
      {
        h: 'Female pelvis',
        body: `<p>Uterus (endometrial stripe cycles ~4–14 mm premenopausal; postmenopausal threshold ~4–5 mm with bleeding), junctional zone on MRI (thickened = adenomyosis), cervix, vagina. Ovaries with follicles (normal ≤~10 mL volume in reproductive age); corpus luteum is a normal thick-walled vascular "ring" — do not call every ring an ectopic. Free fluid in the cul-de-sac: small = physiologic; echogenic = blood.</p>`
      },
      {
        h: 'Male pelvis & scrotum',
        body: `<p>Testes: homogeneous, symmetric echotexture and flow — asymmetric absent flow = torsion (surgical clock running); heterogeneous avascular areas post-trauma = rupture/hematoma. Epididymis head at the upper pole (enlarged hyperemic = epididymitis). Varicocele: dilated pampiniform veins &gt;2–3 mm enlarging with Valsalva, left-sided predominance.</p>`
      }
    ],
    peds: `<p><strong>Pediatric:</strong> DDH ultrasound (before ~4–6 months): Graf alpha angle ≥60°, femoral head coverage ≥50%. Ossification of the acetabulum/femoral head follows a known timetable — the femoral head center appears ~2–8 months. Ovarian and testicular torsion both present atypically in children; volume asymmetry and the whirlpool sign help. Sacrococcygeal teratoma and rhabdomyosarcoma are the classic pediatric pelvic masses.</p>`
  },

  {
    id: 'upperlimb',
    name: 'Upper Limb',
    icon: '💪',
    intro: `<p>Upper limb interpretation is dominated by trauma lines and pediatric ossification — the elbow is the classic testing ground.</p>`,
    svg: 'critoe',
    sections: [
      {
        h: 'Shoulder',
        body: `<p>Glenohumeral congruity on AP + axillary/Y views (posterior dislocation hides on the AP alone — fixed internal rotation "light bulb"). Acromioclavicular alignment; the coracoclavicular distance. Greater tuberosity fractures and Hill-Sachs/Bankart lesions after anterior dislocation. Rotator cuff is MRI/US territory: supraspinatus over the top (impingement under the acromion), subscapularis anterior, infraspinatus/teres minor posterior.</p>`
      },
      {
        h: 'Elbow',
        body: `<ul>
          <li><strong>Fat pads</strong>: a thin anterior fat pad is normal; an elevated "sail" anterior pad or ANY visible posterior fat pad = effusion → occult fracture in trauma (child: supracondylar; adult: radial head).</li>
          <li><strong>Anterior humeral line</strong> should intersect the middle third of the capitellum (falls anterior in supracondylar extension fractures).</li>
          <li><strong>Radiocapitellar line</strong>: the radial shaft axis passes through the capitellum on EVERY view — failure = radial head dislocation (check for Monteggia).</li>
        </ul>`
      },
      {
        h: 'Wrist & hand',
        body: `<p>Carpal arcs of Gilula (three smooth arcs; a step = ligamentous disruption). Scapholunate interval ≤3 mm (wider = "Terry Thomas" sign, scapholunate dissociation). Lateral view alignment: radius–lunate–capitate colinear; lunate tipped like a spilled teacup = perilunate vs lunate dislocation. Scaphoid fractures: often occult — scaphoid views, then MRI or repeat films; proximal pole risks AVN. Ulnar variance affects load (positive variance ↔ ulnolunate impaction).</p>`
      }
    ],
    peds: `<p><strong>Pediatric — CRITOE:</strong> Elbow ossification centers appear in order — <strong>C</strong>apitellum (~1 y), <strong>R</strong>adial head (~3 y), <strong>I</strong>nternal (medial) epicondyle (~5 y), <strong>T</strong>rochlea (~7 y), <strong>O</strong>lecranon (~9 y), <strong>E</strong>xternal (lateral) epicondyle (~11 y). The rule that matters: if the trochlea is ossified, the internal epicondyle MUST be visible in place — if "missing", it is avulsed and trapped in the joint. Supracondylar fracture is the classic pediatric elbow injury; also know lateral condyle fractures (unstable, easily undercalled) and the buckle/greenstick patterns of the distal radius.</p>`
  },

  {
    id: 'lowerlimb',
    name: 'Lower Limb',
    icon: '🦵',
    intro: `<p>Hips, knees, ankles: alignment lines, occult-fracture awareness, and the pediatric hip timeline.</p>`,
    sections: [
      {
        h: 'Hip & femur',
        body: `<p>Shenton line continuity; neck cortices traced on both views (subcapital fractures can be a subtle trabecular angulation — MRI for occult fracture in the elderly who cannot bear weight). Femoral head AVN: sclerosis → crescent sign → collapse. Trochanteric avulsions in adolescents map to muscle origins.</p>`
      },
      {
        h: 'Knee',
        body: `<p>Effusion fills the suprapatellar recess; <strong>lipohemarthrosis</strong> (fat–fluid level on horizontal-beam lateral) = intra-articular fracture, often an occult tibial plateau — CT next. Ottawa knee/ankle rules govern imaging. Segond fragment (lateral tibial rim avulsion) = ACL tear marker. Patellar height (alta/baja) and the deep lateral femoral notch sign. On MRI: menisci are uniformly dark triangles (linear signal touching an articular surface = tear), ACL/PCL bands, collateral ligaments, cartilage, and bone-marrow edema patterns that reconstruct the mechanism (pivot-shift pattern).</p>`
      },
      {
        h: 'Ankle & foot',
        body: `<p>Mortise congruity: symmetric clear space around the talus; medial clear space ≤4 mm. Weber classification by fibular fracture level vs the syndesmosis (A below, B at, C above — C implies syndesmotic injury; check the proximal fibula: Maisonneuve). Base of 5th metatarsal: avulsion vs Jones fracture (different healing risk). Lisfranc: 2nd metatarsal base must align with the middle cuneiform on AP — weight-bearing views unmask subtle injury. Calcaneal fractures: Böhler angle 20–40° (flattened in compression fracture) — and image the spine (axial-load pairing).</p>`
      }
    ],
    peds: `<p><strong>Pediatric hip timeline:</strong> 0–6 months: DDH (ultrasound). ~4–10 years: Legg-Calvé-Perthes (AVN — small sclerotic fragmented femoral head). ~10–16 years: SCFE — the epiphysis slips posteromedially; on frontal view the Klein line along the superior neck should intersect the epiphysis (it fails in SCFE); frog-leg lateral is more sensitive. Transient synovitis vs septic hip is a clinical+US effusion problem. Toddler fracture: spiral tibial hairline in a newly limping 1–3 year old. Normal irregular ossification (e.g., distal femoral condyles, calcaneal apophysis sclerosis) mimics disease — know the variants.</p>`
  },

  {
    id: 'peds-skeleton',
    name: 'Pediatric Skeletal Development',
    icon: '🌱',
    intro: `<p>Children\'s bones are growing organs. The physis is the interpretive center of gravity: it creates unique fracture types, unique tumors locations, and endless normal-variant traps.</p>`,
    sections: [
      {
        h: 'Anatomy of a growing bone',
        body: `<p>Diaphysis (shaft) → metaphysis (flared, most vascular — infection and many tumors start here) → physis (growth plate, radiolucent cartilage) → epiphysis (secondary ossification center). Apophyses are growth centers at tendon attachments (traction injuries: Osgood-Schlatter at the tibial tubercle, pelvic avulsions in sprinters).</p>`
      },
      {
        h: 'Salter-Harris physeal injuries',
        body: `<p>Type I: through the physis only (may look normal — clinical physeal tenderness counts). Type II: physis + metaphyseal corner (most common). Type III: physis + epiphysis (intra-articular). Type IV: through metaphysis, physis, and epiphysis. Type V: crush (diagnosed late by growth arrest). Growth disturbance risk rises with type and with certain sites (distal femur is high-risk at any type).</p>`
      },
      {
        h: 'Bone age & maturation',
        body: `<p>A left-hand/wrist radiograph compared against standards (Greulich-Pyle atlas or Tanner-Whitehouse scoring) estimates skeletal age for endocrine and growth questions. Ossification sequences (like elbow CRITOE) let you distinguish avulsed fragments from normal centers.</p>`
      },
      {
        h: 'Fracture patterns unique to children',
        body: `<p>Buckle (torus) — cortical wrinkle from axial load; Greenstick — one cortex breaks, the other bows; Plastic bowing — bend without discrete fracture (check the pair bone). Remodeling potential means many displaced fractures do fine — but rotational deformity and physeal bars do not remodel.</p>`
      },
      {
        h: 'Non-accidental injury (NAI) imaging',
        body: `<p>High-specificity fractures: classic metaphyseal lesions (corner/bucket-handle), posterior rib fractures, scapular, spinous process, and sternal fractures. Multiple fractures of differing ages, and fractures inconsistent with the stated mechanism or developmental stage (long-bone fracture in a non-ambulatory infant), require a formal skeletal survey per protocol plus neuroimaging in young infants.</p>`
      },
      {
        h: 'Normal variants that fool people',
        body: `<p>Growth plates mistaken for fractures (compare margins: physes are smooth, corticated, at known locations), accessory ossicles (os trigonum, os naviculare, bipartite patella — corticated, characteristic sites), vascular channels in the skull, ischiopubic synchondrosis asymmetry, calcaneal apophyseal sclerosis (normal!), and distal femoral cortical irregularity (avulsive cortical irregularity — a leave-me-alone lesion).</p>`
      }
    ],
    peds: `<p><strong>Core habit:</strong> for any pediatric bone question, state the child\'s age first — the differential, the normal appearance, and the injury pattern all key off it. When unsure between variant and fracture: point tenderness, comparison views, and short-interval follow-up are legitimate tools.</p>`
  },

  {
    id: 'peds-chestabd',
    name: 'Pediatric Chest & Abdomen Differences',
    icon: '🍼',
    intro: `<p>A rapid-reference for how the pediatric torso differs from the adult — the deltas that generate most interpretive errors.</p>`,
    sections: [
      {
        h: 'Chest deltas',
        body: `<ul>
          <li><strong>Thymus</strong> occupies the anterior mediastinum through infancy (sail/wave signs) — normal.</li>
          <li><strong>Cardiothoracic ratio</strong> up to ~0.55–0.6 acceptable in infants (AP, expiration).</li>
          <li><strong>Airways</strong> are compliant: expiratory buckling of the trachea is normal; true fixed narrowing is not.</li>
          <li><strong>Neonatal lung disease</strong> is a timing/history differential: RDS (preemie, granular), TTN (term, wet, resolves ~48 h), meconium aspiration (term, patchy + hyperinflation), congenital lesions (CPAM, sequestration, congenital diaphragmatic hernia — bowel in chest, mediastinal shift).</li>
          <li><strong>Round pneumonia</strong> (under ~8 years) mimics a mass — treat and follow, don\'t biopsy first.</li>
        </ul>`
      },
      {
        h: 'Abdomen deltas',
        body: `<ul>
          <li><strong>Bowel gas pattern</strong>: neonates have undifferentiated loops (no reliable haustra) — think proximal-vs-distal obstruction by loop count.</li>
          <li><strong>Age-keyed emergencies</strong>: 0–1 mo: malrotation/volvulus, NEC, atresias, Hirschsprung. 2–8 wk: pyloric stenosis. 3 mo–3 y: intussusception. Any age: appendicitis (peaks school-age/adolescent).</li>
          <li><strong>Ultrasound first</strong> for nearly everything: pylorus, intussusception, appendix, ovaries/testes, kidneys.</li>
          <li><strong>Lines</strong>: UVC/UAC course and tips are a mandatory NICU checklist item.</li>
          <li><strong>Masses by age</strong>: neonatal flank = hydronephrosis or multicystic dysplastic kidney; infant/toddler solid = neuroblastoma (crosses midline, encases vessels, calcifies) vs Wilms (arises FROM kidney, claw sign, displaces vessels).</li>
        </ul>`
      },
      {
        h: 'Dose culture',
        body: `<p>Image Gently: ultrasound/MRI first when they can answer; single-phase, weight-based CT protocols when CT is needed; no routine "pan-scans". The best dose reduction is the study not done — decision rules (PECARN head, appendicitis pathways) exist to be used.</p>`
      }
    ],
    peds: ``
  }
];

/* Inline schematic SVG diagrams referenced by anatomy sections (theme-aware via currentColor). */
RIA.data.anatomySvgs = {
  cxr: `<svg viewBox="0 0 460 400" role="img" aria-label="Schematic frontal chest radiograph with labeled borders" style="max-width:520px;width:100%">
    <style>.ln{stroke:currentColor;stroke-width:1.6;fill:none}.lbl{font:12px sans-serif;fill:currentColor}.soft{opacity:.35}.ll{stroke:currentColor;stroke-width:.8;opacity:.6}</style>
    <ellipse cx="150" cy="185" rx="95" ry="150" class="ln soft"/>
    <ellipse cx="315" cy="185" rx="95" ry="150" class="ln soft"/>
    <path d="M232 60 L232 130" class="ln"/>
    <path d="M212 132 q-14 40 -6 92 q30 46 82 30 q26 -34 12 -78 q-10 -34 -34 -44 q-34 -12 -54 0 Z" class="ln"/>
    <path d="M212 118 q20 -10 44 -2" class="ln"/>
    <path d="M70 322 q80 -38 160 0" class="ln"/>
    <path d="M240 330 q80 -34 156 -6" class="ln"/>
    <path d="M255 208 L342 194" class="ln soft"/>
    <text x="150" y="30" class="lbl">Trachea (midline)</text><line x1="205" y1="34" x2="230" y2="70" class="ll"/>
    <text x="20" y="120" class="lbl">Aortic knob</text><line x1="95" y1="124" x2="208" y2="126" class="ll"/>
    <text x="10" y="160" class="lbl">Main PA / AP window</text><line x1="140" y1="164" x2="206" y2="160" class="ll"/>
    <text x="10" y="255" class="lbl">Left heart border</text><line x1="112" y1="258" x2="206" y2="235" class="ll"/>
    <text x="352" y="130" class="lbl">SVC / ascending Ao</text><line x1="350" y1="134" x2="290" y2="140" class="ll"/>
    <text x="360" y="230" class="lbl">Right heart</text><text x="360" y="244" class="lbl">border (RA)</text><line x1="358" y1="234" x2="300" y2="215" class="ll"/>
    <text x="352" y="185" class="lbl">Minor fissure</text><line x1="350" y1="189" x2="300" y2="200" class="ll"/>
    <text x="30" y="352" class="lbl">Left hemidiaphragm + gastric bubble</text>
    <text x="255" y="368" class="lbl">Right hemidiaphragm (up to ~3 cm higher)</text>
    <text x="140" y="392" class="lbl soft">Costophrenic angles: sharp = normal</text>
  </svg>`,
  critoe: `<svg viewBox="0 0 460 300" role="img" aria-label="CRITOE elbow ossification order diagram" style="max-width:520px;width:100%">
    <style>.ln{stroke:currentColor;stroke-width:1.6;fill:none}.lbl{font:12px sans-serif;fill:currentColor}.big{font:13px sans-serif;font-weight:700;fill:currentColor}.c{fill:currentColor;opacity:.5}</style>
    <path d="M180 20 L180 120 q0 26 30 30 L290 152 q18 4 18 22 L308 280" class="ln"/>
    <path d="M150 20 L150 118 q-2 34 -30 40 L90 166" class="ln"/>
    <path d="M120 200 L120 280 M150 196 L152 280" class="ln"/>
    <circle cx="165" cy="168" r="16" class="c"/><text x="30" y="150" class="big">C</text><text x="46" y="150" class="lbl">apitellum ~1y</text><line x1="120" y1="146" x2="152" y2="162" class="ln" opacity=".4"/>
    <circle cx="136" cy="210" r="11" class="c"/><text x="30" y="215" class="big">R</text><text x="46" y="215" class="lbl">adial head ~3y</text>
    <circle cx="212" cy="176" r="9" class="c"/><text x="196" y="235" class="big">I</text><text x="204" y="235" class="lbl">nternal (medial) epicondyle ~5y</text><line x1="212" y1="226" x2="212" y2="188" class="ln" opacity=".4"/>
    <circle cx="188" cy="152" r="9" class="c"/><text x="330" y="60" class="big">T</text><text x="344" y="60" class="lbl">rochlea ~7y</text><line x1="328" y1="64" x2="198" y2="148" class="ln" opacity=".4"/>
    <circle cx="262" cy="120" r="10" class="c"/><text x="330" y="100" class="big">O</text><text x="346" y="100" class="lbl">lecranon ~9y</text><line x1="328" y1="104" x2="272" y2="122" class="ln" opacity=".4"/>
    <circle cx="146" cy="140" r="8" class="c"/><text x="30" y="90" class="big">E</text><text x="44" y="90" class="lbl">xternal (lateral)</text><text x="44" y="104" class="lbl">epicondyle ~11y</text><line x1="118" y1="98" x2="142" y2="132" class="ln" opacity=".4"/>
    <text x="120" y="296" class="lbl">Rule: trochlea ossified but no internal epicondyle → it is avulsed into the joint.</text>
  </svg>`
};

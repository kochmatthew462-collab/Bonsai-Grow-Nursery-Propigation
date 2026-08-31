/* Radiology Interpretation Academy — Modality curriculum.
   Educational reference content. Not a substitute for formal training or clinical judgment. */
window.RIA = window.RIA || {};
RIA.data = RIA.data || {};

RIA.data.modalities = [
  {
    id: 'radiography',
    name: 'Radiography (X-ray)',
    icon: '🦴',
    tagline: 'The foundation modality: projection imaging with ionizing radiation.',
    sections: [
      {
        h: 'How the image is made',
        body: `<p>An X-ray tube generates photons that pass through the patient to a digital detector. Tissues attenuate the beam in proportion to their density and atomic number, so the image is a <strong>2-D projection of summed attenuation</strong> along each ray path. Everything in the beam is superimposed — this is both the great limitation (overlap hides pathology) and the reason two orthogonal views are standard.</p>
        <p>Because the beam diverges, structures far from the detector are <strong>magnified</strong> and blurred. This is why the heart looks larger on an AP (anteroposterior) film than a PA (posteroanterior) film: on AP projections the heart sits farther from the detector.</p>`
      },
      {
        h: 'The five densities',
        body: `<p>Learn to name every shade on a radiograph using the five classic densities, from blackest to whitest:</p>
        <ol>
          <li><strong>Gas</strong> — black (lungs, bowel gas, free air)</li>
          <li><strong>Fat</strong> — dark grey (subcutaneous fat, fat pads, properitoneal fat stripes)</li>
          <li><strong>Soft tissue / fluid</strong> — mid grey (heart, muscle, solid organs, effusions — soft tissue and fluid are indistinguishable on plain film)</li>
          <li><strong>Bone / calcium</strong> — near white</li>
          <li><strong>Metal / contrast</strong> — bright white (hardware, barium, iodinated contrast)</li>
        </ol>
        <p>Interfaces are only visible where two <em>different</em> densities touch. This is the basis of the <strong>silhouette sign</strong>: when consolidation (fluid density) contacts the heart border (also fluid density), the border disappears — and the location of the lost border localizes the disease.</p>`
      },
      {
        h: 'Technique and adequacy — RIPE',
        body: `<p>Before interpreting any film, judge whether it is adequate. For a chest radiograph use <strong>RIPE</strong>:</p>
        <ul>
          <li><strong>Rotation</strong> — spinous process midway between the medial clavicular heads. Rotation distorts the mediastinum and hila and fakes pathology.</li>
          <li><strong>Inspiration</strong> — 5–6 anterior ribs (or 8–10 posterior ribs) above the diaphragm mid-clavicular line. Poor inspiration crowds basal vessels and mimics consolidation or cardiomegaly.</li>
          <li><strong>Projection / Position</strong> — PA erect is the standard; AP supine changes heart size, mediastinal width, and fluid/air distribution (effusions layer posteriorly, pneumothorax collects anteromedially → deep sulcus sign).</li>
          <li><strong>Exposure</strong> — vertebral bodies just visible through the cardiac shadow; disc spaces visible in the lower thorax. Modern digital systems auto-window, but gross under/over-exposure still degrades detail.</li>
        </ul>`
      },
      {
        h: 'Artifacts and pitfalls',
        body: `<ul>
          <li><strong>Superimposition</strong> — nipple shadows, skin folds (mimic pneumothorax — look for lung markings beyond the line and the line extending outside the thorax), hair braids, clothing, ECG leads.</li>
          <li><strong>Grid cut-off and motion blur</strong> — uniform loss of sharpness; repeat if diagnostic detail is lost.</li>
          <li><strong>Lordotic projection</strong> — clavicles project above the lung apices; anterior ribs point upward; can hide or mimic apical disease.</li>
          <li><strong>Mach bands</strong> — perceptual dark lines at convex bony margins that mimic fracture lucencies; trace the cortex, a true fracture disrupts it.</li>
        </ul>`
      },
      {
        h: 'Dose and safety',
        body: `<p>A PA chest radiograph is about <strong>0.02 mSv</strong> — roughly 2–3 days of natural background radiation. Extremity films are lower; lumbar spine (~1.5 mSv) and abdomen (~0.7 mSv) are higher. Apply <strong>ALARA</strong> (As Low As Reasonably Achievable): justify every exposure, collimate, shield when it does not compromise the study, and prefer non-ionizing modalities (ultrasound, MRI) in children and pregnancy when they can answer the question.</p>`
      },
      {
        h: 'When radiography is the right test',
        body: `<p>First-line for: suspected fracture or joint pathology, chest symptoms (dyspnea, cough, chest pain, line/tube placement), bowel obstruction or perforation screening, foreign bodies, and follow-up of known disease. Cheap, fast, low-dose, universally available — but insensitive: a normal radiograph does not exclude early pneumonia, occult fracture (scaphoid, hip), or most soft-tissue pathology. Know when to escalate to CT, US, or MRI.</p>`
      }
    ],
    keyPoints: [
      'A radiograph is summed attenuation — always think in terms of superimposition and get two views.',
      'Name findings using the five densities; interfaces disappear when like densities touch (silhouette sign).',
      'Check adequacy (RIPE) before interpretation; technique problems create fake pathology.',
      'AP magnifies the heart; supine position redistributes air and fluid.',
      'Normal film ≠ no disease. Know the sensitivity limits.'
    ],
    peds: `<p><strong>Pediatric points:</strong> The infant thymus is a normal anterior mediastinal structure ("sail sign" of the thymus, wave sign against the ribs) — do not call it a mass. Infant cardiothoracic ratio up to ~0.55–0.6 can be normal on AP films. Growth plates are normal lucencies — compare with the contralateral side or an atlas rather than calling fractures. Use inspiratory/expiratory (or decubitus) films for suspected airway foreign body: air trapping keeps the affected lung inflated on expiration. Minimize dose aggressively: children are more radiosensitive and have longer lifetimes to express risk.</p>`
  },

  {
    id: 'fluoroscopy',
    name: 'Fluoroscopy & Contrast Studies',
    icon: '📽️',
    tagline: 'Real-time X-ray: dynamic studies of swallowing, GI tract, joints, and vessels.',
    sections: [
      {
        h: 'How it works',
        body: `<p>Fluoroscopy is continuous or pulsed X-ray imaging displayed in real time, used to observe <strong>motion</strong> — swallowing, peristalsis, diaphragm movement, joint mechanics, catheter navigation. Modern units use flat-panel detectors with pulsed acquisition to lower dose. Spot images and cine loops document findings.</p>`
      },
      {
        h: 'Contrast agents for the GI tract',
        body: `<ul>
          <li><strong>Barium sulfate</strong> — excellent mucosal coating, the default for routine swallow and GI studies. Never use when perforation is suspected (barium peritonitis/mediastinitis) or when aspiration of large volume is likely.</li>
          <li><strong>Water-soluble iodinated contrast</strong> (e.g., diatrizoate) — used for suspected perforation or post-operative leaks. High-osmolar agents are dangerous if aspirated (pulmonary edema) — use low-osmolar non-ionic agents when aspiration risk exists.</li>
          <li><strong>Double contrast</strong> — barium plus gas distension for fine mucosal detail.</li>
        </ul>`
      },
      {
        h: 'Common studies and what they show',
        body: `<ul>
          <li><strong>Esophagram / barium swallow</strong> — dysphagia, strictures, rings, achalasia (bird-beak), motility.</li>
          <li><strong>Videofluoroscopic swallow study</strong> — aspiration assessment with speech pathology.</li>
          <li><strong>Upper GI series</strong> — in infants, the key study for <strong>malrotation/volvulus</strong>: normal duodenojejunal junction (ligament of Treitz) lies left of the left pedicle at the level of the duodenal bulb; a corkscrew duodenum indicates volvulus — a surgical emergency.</li>
          <li><strong>Contrast enema</strong> — neonatal distal obstruction (microcolon, meconium ileus, Hirschsprung transition zone); intussusception diagnosis and pneumatic/hydrostatic reduction in infants.</li>
          <li><strong>VCUG (voiding cystourethrogram)</strong> — vesicoureteral reflux grading, posterior urethral valves in boys.</li>
          <li><strong>Arthrography, myelography, HSG</strong> — joint, thecal sac, and uterine/tubal studies, often combined with CT/MR.</li>
        </ul>`
      },
      {
        h: 'Dose awareness',
        body: `<p>Fluoroscopy delivers dose for as long as the beam is on. Dose-saving discipline: pulsed fluoro at the lowest acceptable frame rate, last-image-hold instead of re-exposure, tight collimation, keep the detector close to the patient, and track fluoro time. Skin injury is the classic deterministic risk of long interventional cases.</p>`
      }
    ],
    keyPoints: [
      'Fluoroscopy answers questions about motion and luminal anatomy in real time.',
      'Suspected perforation → water-soluble contrast, never barium.',
      'Bilious vomiting in a neonate → emergent upper GI for malrotation/volvulus.',
      'Dose is proportional to beam-on time: pulse, collimate, use last-image-hold.'
    ],
    peds: `<p><strong>Pediatric points:</strong> The upper GI series for bilious vomiting and the contrast enema for intussusception reduction are two of the most consequential emergency fluoro studies in children. Air (pneumatic) reduction of ileocolic intussusception succeeds in the great majority of cases; perforation risk is small but the room must be prepared for it. In VCUG, cyclic voiding increases reflux detection in infants.</p>`
  },

  {
    id: 'ct',
    name: 'Computed Tomography (CT)',
    icon: '🌀',
    tagline: 'Cross-sectional X-ray imaging measured in Hounsfield units.',
    sections: [
      {
        h: 'How the image is made',
        body: `<p>A rotating X-ray tube and detector array acquire attenuation profiles from many angles; reconstruction produces cross-sectional images that eliminate superimposition. Modern helical multidetector CT scans a chest in seconds and reconstructs any plane (axial, coronal, sagittal, oblique) plus 3-D and maximum-intensity projections (MIP — great for vessels and nodules).</p>`
      },
      {
        h: 'Hounsfield units — learn these numbers',
        body: `<p>CT voxel values are calibrated attenuation: <strong>water = 0 HU, air = −1000 HU</strong>. Approximate values worth memorizing:</p>
        <ul>
          <li>Air −1000 · Lung −700 · Fat −100 to −50 · Water 0</li>
          <li>Simple fluid 0–20 · Soft tissue / muscle 30–60 · Unclotted blood ~35–45</li>
          <li><strong>Acute clotted blood 50–80</strong> · Contrast-enhanced blood 100–300</li>
          <li>Calcium/bone 150–1000+ · Metal ≫1000</li>
        </ul>
        <p>Measuring HU answers real questions: Is this renal lesion a simple cyst (&lt;20 HU, no enhancement) or solid? Is this adrenal nodule lipid-rich adenoma (≤10 HU unenhanced)? Is that fluid blood (hyperdense) or simple?</p>`
      },
      {
        h: 'Windowing',
        body: `<p>The display maps a chosen HU range (window width) around a center (window level) onto the grey scale. <strong>You must review every scan in the appropriate windows</strong> — pathology invisible in one window is obvious in another:</p>
        <ul>
          <li><strong>Brain</strong> W≈80 L≈40 · <strong>Subdural</strong> W≈200 L≈80 (thin subdurals hidden against skull) · <strong>Stroke</strong> W≈8–40 L≈32–40 (accentuates grey–white)</li>
          <li><strong>Lung</strong> W≈1500 L≈−600 · <strong>Mediastinum/soft tissue</strong> W≈350–400 L≈40–50</li>
          <li><strong>Bone</strong> W≈1500–2500 L≈300–500 · <strong>Liver</strong> narrow W≈150 L≈70 for subtle lesions</li>
        </ul>`
      },
      {
        h: 'Contrast phases',
        body: `<p>Iodinated IV contrast timing tailors the study to the question:</p>
        <ul>
          <li><strong>Non-contrast</strong> — hemorrhage, calcification/stones, baseline HU (adrenal, renal lesions).</li>
          <li><strong>CT angiographic/arterial phase (~25–35 s)</strong> — CTA (PE study is a dedicated pulmonary arterial phase), active arterial extravasation, hypervascular tumors (HCC arterial enhancement).</li>
          <li><strong>Portal venous phase (~60–70 s)</strong> — the workhorse abdominal phase: solid organ parenchyma, most masses, bowel, veins.</li>
          <li><strong>Delayed/excretory (3–10+ min)</strong> — urothelium (CT urogram), washout characterization (adrenal, HCC), slow bleeding.</li>
        </ul>`
      },
      {
        h: 'Contrast safety',
        body: `<ul>
          <li><strong>Allergic-like reactions</strong> — most are mild (hives). Prior moderate/severe reaction is the strongest risk factor; premedication protocols (corticosteroid + antihistamine) are used for those patients. Treat severe reactions as anaphylaxis: epinephrine, airway, fluids.</li>
          <li><strong>Contrast-associated acute kidney injury</strong> — risk concentrates in patients with severely reduced eGFR (&lt;30 mL/min/1.73 m²); modern evidence shows lower risk than historically feared. Hydration is the main mitigation; never withhold a life-saving contrast study for renal risk without weighing the alternative.</li>
          <li><strong>Metformin</strong> — hold after contrast in patients with reduced eGFR per local policy (lactic acidosis risk if AKI develops).</li>
          <li><strong>Extravasation</strong> — elevate limb, monitor for compartment symptoms.</li>
        </ul>`
      },
      {
        h: 'Artifacts',
        body: `<ul>
          <li><strong>Beam hardening / streak</strong> — dark bands between dense objects (posterior fossa between petrous bones; dental amalgam; metal hardware). Metal artifact reduction algorithms and dual-energy help.</li>
          <li><strong>Motion</strong> — respiratory or cardiac blur; can mimic dissection flaps at the aortic root on non-gated studies.</li>
          <li><strong>Partial volume</strong> — a voxel averaging two tissues fakes intermediate density; thin slices reduce it.</li>
          <li><strong>Noise in large patients / low-dose scans</strong> — grainy images; iterative reconstruction compensates.</li>
        </ul>`
      },
      {
        h: 'Dose and choosing CT',
        body: `<p>Typical effective doses: head CT ~2 mSv, chest ~5–7 mSv, abdomen/pelvis ~7–10 mSv (dose-reduction technology lowers these). CT is the emergency workhorse: trauma, stroke, PE, acute abdomen, complex fractures. Prefer US/MRI when equivalent and radiation matters (children, pregnancy, repeated follow-up). Use decision rules (e.g., PECARN for pediatric head injury) to avoid unnecessary scans.</p>`
      }
    ],
    keyPoints: [
      'Memorize the HU ladder — measuring density is a core interpretive act.',
      'Review every CT in all relevant windows: lung, soft tissue, bone, brain, subdural, stroke.',
      'Contrast phase = the question: arterial for vessels and bleeding, portal venous for organs, delayed for urothelium and washout.',
      'Acute blood is hyperdense (50–80 HU); fat is negative; simple fluid ~0–20.',
      'Know the big artifacts so you do not report them as disease.'
    ],
    peds: `<p><strong>Pediatric points:</strong> Child-size the dose: weight-based protocols, single-phase whenever possible, and ask whether US or MRI can answer first (appendicitis: US first; head injury: apply PECARN). Children have less visceral fat, making planes harder to read — oral contrast is used more liberally in some centers. In suspected non-accidental trauma, CT head plus skeletal survey follow defined protocols.</p>`
  },

  {
    id: 'mri',
    name: 'Magnetic Resonance Imaging (MRI)',
    icon: '🧲',
    tagline: 'Soft-tissue contrast king: signal from hydrogen protons, no ionizing radiation.',
    sections: [
      {
        h: 'How the image is made',
        body: `<p>The scanner magnetizes tissue protons in a strong static field (1.5 T or 3 T), perturbs them with radiofrequency pulses, and listens to the returning signal as they relax. Two relaxation constants — <strong>T1</strong> (longitudinal recovery) and <strong>T2</strong> (transverse decay) — differ by tissue, and pulse sequence parameters (TR, TE) weight the image toward one or the other. Gradients encode spatial position. No ionizing radiation is involved.</p>`
      },
      {
        h: 'Reading signal: the core sequences',
        body: `<ul>
          <li><strong>T1-weighted</strong> — fat bright, water/CSF dark, brain grey matter darker than white matter. Best for anatomy, fat, subacute blood (methemoglobin bright), and post-gadolinium enhancement.</li>
          <li><strong>T2-weighted</strong> — water/CSF bright, fat fairly bright (on fast spin echo). Pathology is usually water-rich → <em>most disease is T2-bright</em>.</li>
          <li><strong>FLAIR</strong> — T2 with CSF suppressed: periventricular and cortical/juxtacortical lesions (MS, edema, subarachnoid disease) stand out.</li>
          <li><strong>DWI + ADC</strong> — diffusion restriction (bright DWI, dark ADC) = acute infarct within minutes, also abscess pus, hypercellular tumor, epidermoid. Bright DWI with bright ADC is T2 shine-through, not restriction — always check the ADC map.</li>
          <li><strong>GRE / SWI</strong> — magnetic susceptibility: blood products, calcium, air "bloom" dark. Microhemorrhages, cavernomas, DAI.</li>
          <li><strong>Fat suppression (STIR, fat-sat)</strong> — reveals marrow edema and fluid signal that bright fat would hide; STIR is the MSK screening workhorse.</li>
          <li><strong>Post-gadolinium T1</strong> — enhancement marks blood–brain-barrier breakdown, inflammation, tumor vascularity, abscess rims.</li>
        </ul>
        <p>Quick identification habit: find fluid (CSF, bladder, joint fluid). Fluid dark → T1. Fluid bright → T2. Fluid bright but CSF dark → FLAIR. Then read the pathology's signal against that.</p>`
      },
      {
        h: 'Aging blood on MRI',
        body: `<p>Hemorrhage changes signal as hemoglobin degrades. A usable mnemonic (T1/T2): <strong>I B</strong>e, <strong>I</strong>ntensely <strong>D</strong>im, <strong>B</strong>right <strong>B</strong>right, <strong>D</strong>im <strong>D</strong>im — hyperacute (iso/bright), acute (iso/dark), early subacute (bright/dark), late subacute (bright/bright), chronic (dark/dark hemosiderin rim).</p>`
      },
      {
        h: 'Safety — the magnet is always on',
        body: `<ul>
          <li><strong>Projectile risk</strong> — ferromagnetic objects become missiles; the field never turns off. Zoned access and screening are absolute.</li>
          <li><strong>Implants</strong> — pacemakers/ICDs (many are now MR-conditional under protocol), aneurysm clips, cochlear implants, ferromagnetic foreign bodies (orbital metal!) must be verified before entry.</li>
          <li><strong>Heating and burns</strong> — looped cables, skin-to-skin contact, some tattoos.</li>
          <li><strong>Gadolinium</strong> — nephrogenic systemic fibrosis risk is essentially confined to older linear agents in severe renal failure; modern macrocyclic agents are low-risk. Trace gadolinium retention in brain is documented, of unclear significance — use contrast when it changes the answer.</li>
          <li><strong>Pregnancy</strong> — MRI without gadolinium is preferred over CT when feasible; gadolinium avoided unless essential.</li>
        </ul>`
      },
      {
        h: 'Artifacts',
        body: `<ul>
          <li><strong>Motion/ghosting</strong> — repeats along phase-encode direction.</li>
          <li><strong>Susceptibility</strong> — signal void and distortion near metal or air interfaces (worse at 3 T; sequences can compensate).</li>
          <li><strong>Chemical shift</strong> — fat/water boundary displacement; India-ink etching on opposed-phase imaging (used to prove microscopic fat in adrenal adenomas).</li>
          <li><strong>Aliasing/wrap</strong> — anatomy outside the field of view folds in.</li>
          <li><strong>T2 shine-through</strong> — see DWI above.</li>
        </ul>`
      },
      {
        h: 'When MRI is the right test',
        body: `<p>Brain and spine (stroke, tumor, MS, cord compression, infection), MSK internal derangement (menisci, ligaments, rotator cuff, marrow/occult fracture, osteomyelitis), liver/pancreas/biliary characterization (MRCP), pelvis (uterus, prostate, rectal cancer staging, fistula), cardiac function and tissue characterization. Slower and less available than CT; requires patient cooperation (or sedation in young children).</p>`
      }
    ],
    keyPoints: [
      'Identify the sequence first (find the fluid), then interpret signal.',
      'Most pathology is T2/FLAIR-bright; DWI restriction means acute infarct until proven otherwise — confirm on ADC.',
      'Fat suppression unmasks marrow and soft-tissue edema.',
      'Enhancement = leaky vessels/BBB breakdown, not "tumor" specifically.',
      'MRI safety is a screening discipline: the field is always on.'
    ],
    peds: `<p><strong>Pediatric points:</strong> MRI is preferred over CT in children whenever it can answer the question (no radiation) — but infants and toddlers often need feed-and-wrap technique, fast sequences, or sedation/anesthesia. Normal myelination changes brain signal dramatically over the first 2 years (white matter matures from T2-bright to T2-dark); use age-matched references. Rapid-sequence MRI protocols now screen shunted hydrocephalus without sedation or dose.</p>`
  },

  {
    id: 'ultrasound',
    name: 'Ultrasound',
    icon: '🔊',
    tagline: 'Real-time, radiation-free imaging with sound — operator skill is the resolution.',
    sections: [
      {
        h: 'How the image is made',
        body: `<p>A piezoelectric transducer sends high-frequency sound pulses (2–15+ MHz) and maps returning echoes by depth and direction. Echo strength depends on <strong>acoustic impedance mismatch</strong> at tissue interfaces. <strong>Higher frequency = better resolution, less penetration</strong>: linear high-frequency probes for superficial structures (thyroid, testes, MSK, pediatric appendix, vessels), curvilinear low-frequency probes for the abdomen, phased array for the heart and between ribs.</p>`
      },
      {
        h: 'Echogenicity vocabulary',
        body: `<p>Describe structures relative to neighbors: <strong>anechoic</strong> (black — simple fluid), <strong>hypoechoic</strong>, <strong>isoechoic</strong>, <strong>hyperechoic</strong> (bright — fat, gas interfaces, calcium). Normal ladder in the RUQ: renal sinus fat &gt; pancreas ≥ liver ≥ spleen &gt; renal cortex &gt; renal medulla. A liver brighter than the kidney suggests steatosis; a kidney brighter than liver suggests medical renal disease.</p>
        <p>A <strong>simple cyst</strong> requires all of: anechoic, imperceptible wall, sharp back wall, posterior acoustic enhancement. Anything else is "complex" and needs characterization.</p>`
      },
      {
        h: 'Artifacts you must use, not just avoid',
        body: `<ul>
          <li><strong>Posterior acoustic shadowing</strong> — sound blocked by stone/calcium/gas → dark shadow. Confirms gallstones and renal calculi. Gas gives "dirty" shadowing; stones give clean shadows.</li>
          <li><strong>Posterior enhancement</strong> — sound passes easily through fluid, tissues behind look brighter. Confirms cystic nature.</li>
          <li><strong>Reverberation / ring-down / comet tail</strong> — repeating echoes from strong parallel reflectors; A-lines in normal lung; comet-tail from cholesterol crystals in adenomyomatosis.</li>
          <li><strong>Mirror image</strong> — structures duplicated across a strong reflector (liver lesion "above" the diaphragm).</li>
          <li><strong>Anisotropy</strong> — tendons look falsely hypoechoic when not perpendicular to the beam; rock the probe before calling tendinosis.</li>
          <li><strong>Twinkle artifact</strong> — color Doppler sparkle behind rough calcific surfaces; helps find small renal stones.</li>
        </ul>`
      },
      {
        h: 'Doppler',
        body: `<p>Doppler shift encodes motion. <strong>Color Doppler</strong> maps direction/mean velocity (BART convention: blue away, red toward — check the scale, it is direction relative to the probe, not artery/vein). <strong>Spectral Doppler</strong> quantifies velocities and waveforms (carotid stenosis grading, portal vein flow, renal resistive index). <strong>Power Doppler</strong> is more sensitive for slow flow (testicular/ovarian torsion, synovitis) but directionless. Absence of flow in a torsed testis or ovary is a surgical emergency finding.</p>`
      },
      {
        h: 'Core applications',
        body: `<ul>
          <li><strong>RUQ</strong>: gallstones, cholecystitis (wall &gt;3 mm, pericholecystic fluid, sonographic Murphy), CBD dilation.</li>
          <li><strong>Renal</strong>: hydronephrosis, stones, bladder volume.</li>
          <li><strong>Pelvic/obstetric</strong>: first-line for pregnancy, ovaries, ectopic; endovaginal for early pregnancy.</li>
          <li><strong>Vascular</strong>: DVT compression US (non-compressible vein = thrombus), carotids, aorta screening.</li>
          <li><strong>FAST/eFAST</strong> in trauma: free fluid in Morison pouch, splenorenal recess, pelvis, pericardium; lung sliding for pneumothorax.</li>
          <li><strong>Lung US</strong>: B-lines (interstitial fluid), absent sliding + lung point (pneumothorax), consolidation with air bronchograms, effusion.</li>
          <li><strong>Small parts/MSK</strong>: thyroid, testes, soft-tissue lumps, tendons, foreign bodies.</li>
        </ul>`
      },
      {
        h: 'Strengths and limits',
        body: `<p>No radiation, portable, real-time, dynamic (compression, Valsalva, movement), cheap. Limits: gas and bone block sound; depth/penetration in large patients; and above all <strong>operator dependence</strong> — the images saved are only as good as the sweep performed. Documented negative study ≠ absent pathology if the target was not adequately seen.</p>`
      }
    ],
    keyPoints: [
      'Frequency trades penetration for resolution — choose the probe to fit the question.',
      'Artifacts are diagnostic tools: shadowing = stone/calcium, enhancement = fluid, absent flow = torsion/thrombosis.',
      'Learn the echogenicity ladder and the strict criteria for a simple cyst.',
      'Ultrasound is first-line in children and pregnancy.',
      'Anisotropy and poor technique create fake pathology — sweep and re-angle before calling.'
    ],
    peds: `<p><strong>Pediatric points:</strong> Ultrasound is the pediatric workhorse: pyloric stenosis (muscle ≥3 mm thick, channel ≥15 mm long), intussusception (target/doughnut sign, typically &gt;2.5 cm ileocolic), appendicitis (non-compressible, ≥6–7 mm), developmental dysplasia of the hip (Graf alpha angle ≥60° normal), infant spine (open acoustic windows before ossification), and cranial US through the open fontanelle for germinal-matrix hemorrhage grading in preemies.</p>`
  },

  {
    id: 'nucmed',
    name: 'Nuclear Medicine & PET',
    icon: '☢️',
    tagline: 'Physiology first: images of function made from injected radiotracers.',
    sections: [
      {
        h: 'How the image is made',
        body: `<p>A radiopharmaceutical — a molecule chosen for its biological behavior, labeled with a radioactive isotope — is administered, and its distribution is imaged. Gamma cameras capture single-photon emitters (planar and <strong>SPECT</strong>); <strong>PET</strong> detects the paired 511-keV photons from positron annihilation with much better resolution and quantification (SUV). Hybrid <strong>PET/CT and SPECT/CT</strong> fuse function with anatomy. The image shows <em>physiology</em>: uptake maps metabolism, perfusion, receptor binding, or excretion — anatomy is secondary.</p>`
      },
      {
        h: 'The tracers you should know',
        body: `<ul>
          <li><strong>FDG (¹⁸F-fluorodeoxyglucose, PET)</strong> — glucose analogue trapped in metabolically active cells. Oncology staging/response, infection/inflammation, viable myocardium, dementia patterns. Normal avid sites: brain, myocardium (variable), liver (reference), urinary tract (excretion), brown fat, active muscle. Patients fast; hyperglycemia degrades the study.</li>
          <li><strong>Tc-99m MDP (bone scan)</strong> — osteoblastic activity: metastases, stress fractures, osteomyelitis (three-phase). "Superscan" = diffuse skeletal uptake with faint kidneys.</li>
          <li><strong>Tc-99m MAA + xenon/Tc aerosol (V/Q)</strong> — ventilation/perfusion mismatch for PE when CTA is contraindicated (pregnancy, contrast allergy, renal failure).</li>
          <li><strong>Tc-99m HIDA (hepatobiliary)</strong> — non-visualized gallbladder at 4 h (or after morphine) = acute cholecystitis; also biliary leaks, biliary atresia in neonates.</li>
          <li><strong>Tc-99m MAG3/DTPA (renogram)</strong> — split renal function and drainage curves (obstruction vs. dilation, with furosemide).</li>
          <li><strong>Tc-99m pertechnetate</strong> — thyroid uptake; Meckel scan (ectopic gastric mucosa in a bleeding child).</li>
          <li><strong>Myocardial perfusion (Tc-99m sestamibi/tetrofosmin, rubidium PET)</strong> — stress/rest ischemia and infarct.</li>
          <li><strong>Iodine-123/131</strong> — thyroid imaging and therapy; <strong>PSMA and DOTATATE PET</strong> — prostate cancer and neuroendocrine tumors.</li>
        </ul>`
      },
      {
        h: 'Reading principles',
        body: `<p>Ask four questions: (1) What does <em>normal</em> biodistribution look like for this tracer? (2) Where is uptake increased or absent relative to that? (3) Does the CT correlate explain it (physiologic vs pathologic — ureter vs node)? (4) Does intensity matter (SUV trends for response, but SUV is semi-quantitative — compare like with like)? Beware FDG traps: brown fat, muscle activity, post-treatment inflammation, and tumors with low FDG avidity (some lobular breast, mucinous, low-grade tumors, small lesions below resolution).</p>`
      },
      {
        h: 'Safety',
        body: `<p>Doses are moderate (bone scan ~4 mSv; FDG PET/CT ~8–15 mSv including CT). Patients are briefly radioactive — breastfeeding interruption guidance and proximity precautions per tracer. Therapy doses (I-131) have formal radiation-protection protocols. Pregnancy: justify and minimize; V/Q perfusion-only with reduced dose is a common PE pathway in pregnancy.</p>`
      }
    ],
    keyPoints: [
      'Nuclear medicine images function; anatomy comes from the fused CT.',
      'Know each tracer\'s normal biodistribution before calling anything abnormal.',
      'HIDA non-filling = cholecystitis; V/Q mismatch = PE; three-phase bone scan for osteomyelitis.',
      'FDG is not cancer-specific: inflammation is avid, and some cancers are not.',
      'SUV is a tool, not a truth — compare consistent techniques.'
    ],
    peds: `<p><strong>Pediatric points:</strong> Weight-based dosing per consensus pediatric guidelines. MAG3 renography with furosemide is central to pediatric hydronephrosis workup; DMSA maps pyelonephritis scarring; Meckel scans are mostly a pediatric study; bone scans and increasingly whole-body MRI evaluate multifocal disease. Normal growth plates are hot on bone scan — symmetric physeal uptake is expected, not metastasis.</p>`
  },

  {
    id: 'mammo',
    name: 'Mammography & Breast Imaging',
    icon: '🎗️',
    tagline: 'High-resolution low-dose X-ray screening, with US and MRI as problem-solvers.',
    sections: [
      {
        h: 'The modality set',
        body: `<p><strong>Mammography</strong> (now typically digital breast tomosynthesis, "3-D mammo") uses low-energy X-rays and firm compression for microcalcification and mass detection; standard views are CC and MLO. <strong>Ultrasound</strong> characterizes masses (cystic vs solid) and guides biopsy; it is first-line under age 30 and in pregnancy. <strong>Breast MRI</strong> is the most sensitive test — used in high-risk screening, extent of disease, and implant evaluation.</p>`
      },
      {
        h: 'Core interpretive vocabulary',
        body: `<ul>
          <li><strong>Masses</strong> — described by shape (oval/round/irregular), margin (circumscribed → obscured → indistinct → microlobulated → spiculated), and density. Spiculated margins are the most suspicious feature.</li>
          <li><strong>Calcifications</strong> — typically benign patterns (vascular, coarse "popcorn", rim, milk-of-calcium) vs suspicious morphology (amorphous, fine pleomorphic, fine linear/branching) and distribution (diffuse → regional → grouped → linear → segmental; linear/segmental suggest ductal, i.e., DCIS).</li>
          <li><strong>Asymmetry, architectural distortion</strong> — spiculation without central mass; distortion demands explanation (cancer vs surgical scar).</li>
          <li><strong>Density</strong> — dense breast tissue lowers mammographic sensitivity (masking) and independently raises risk.</li>
        </ul>`
      },
      {
        h: 'BI-RADS: structured reporting done right',
        body: `<p>Breast imaging pioneered category-based reporting — a model for all structured reporting: <strong>0</strong> incomplete (recall), <strong>1</strong> negative, <strong>2</strong> benign, <strong>3</strong> probably benign (&le;2% malignancy, short-interval follow-up), <strong>4</strong> suspicious (biopsy; subdivided 4A/B/C), <strong>5</strong> highly suggestive (&ge;95%), <strong>6</strong> known cancer. Every finding gets a category, and every category maps to an action.</p>`
      },
      {
        h: 'Dose and screening logic',
        body: `<p>Two-view mammography is ~0.4 mSv. Screening trades small radiation and recall/overdiagnosis harms for mortality reduction; protocols differ by guideline (typically starting age 40–50, annual or biennial). Diagnostic workup (recall) adds spot compression, magnification views, and US.</p>`
      }
    ],
    keyPoints: [
      'Margins and calcification morphology/distribution drive suspicion.',
      'BI-RADS shows how structured categories link findings to actions.',
      'US first under 30 and in pregnancy/lactation; MRI for high-risk screening and extent.',
      'Dense breasts mask cancers and raise risk.'
    ],
    peds: `<p><strong>Pediatric/young-patient points:</strong> Mammography is essentially never the first test in children and adolescents; breast masses in this group (usually fibroadenomas) are evaluated with ultrasound. Radiation-sensitive breast tissue in the young is a core reason for age-based imaging pathways.</p>`
  },

  {
    id: 'interventional',
    name: 'Interventional Radiology (Overview)',
    icon: '🩻',
    tagline: 'Image-guided therapy: knowing what IR can do changes what you look for.',
    sections: [
      {
        h: 'Why interpreters need IR literacy',
        body: `<p>Diagnostic reads increasingly end with an IR referral. Recognizing an actively bleeding vessel (contrast extravasation on CTA), a drainable collection, a biopsy-accessible lesion, or a threatened dialysis fistula changes management within hours. Report findings with the intervention in mind: size, location, access window, and relationship to vessels.</p>`
      },
      {
        h: 'Core procedures to recognize on imaging',
        body: `<ul>
          <li><strong>Drainages</strong> — abscess/collection drains; describe collections with size, wall, gas, and safest route in mind.</li>
          <li><strong>Embolization</strong> — GI bleeding, trauma (spleen, pelvis), uterine fibroids, tumors; look for coils/plugs/onyx on follow-up scans and do not call them foreign bodies.</li>
          <li><strong>Vascular access & stents</strong> — recognize catheter tip positions (see the lines-and-tubes checklist), stents, IVC filters and their complications (migration, penetration, thrombosis).</li>
          <li><strong>Biopsies and ablations</strong> — post-ablation zones evolve on follow-up; know expected vs recurrent enhancement.</li>
          <li><strong>Biliary/GU interventions</strong> — nephrostomies, biliary drains, gastrostomies: verify tube course and side-holes within the target.</li>
        </ul>`
      },
      {
        h: 'Radiation protection in the suite',
        body: `<p>Interventional fluoroscopy is the highest-dose corner of radiology. Operator discipline — time, distance, shielding, collimation, low-dose pulsed modes — protects both patient and staff. Deterministic skin injury tracking is mandatory for long cases.</p>`
      }
    ],
    keyPoints: [
      'Read diagnostically with therapy in mind: is it bleeding, drainable, biopsiable, stentable?',
      'Recognize devices and post-treatment changes so you do not report them as pathology.',
      'Highest fluoro doses in radiology — protection discipline matters.'
    ],
    peds: `<p><strong>Pediatric points:</strong> Pediatric IR handles vascular anomalies (sclerotherapy of lymphatic/venous malformations), enteric access, and biopsies under sedation protocols with strict dose minimization.</p>`
  }
];

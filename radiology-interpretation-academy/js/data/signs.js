/* Radiology Interpretation Academy — Classic signs glossary. */
window.RIA = window.RIA || {};
RIA.data = RIA.data || {};

RIA.data.signs = [
  // ——— Chest ———
  { name: 'Air bronchogram', modality: 'XR/CT', region: 'Chest', desc: 'Lucent branching airways visible within opacified lung.', means: 'Airspace filling (pneumonia, edema, hemorrhage) — the airway is patent but alveoli are full. Confirms consolidation rather than pleural or mediastinal opacity.' },
  { name: 'Silhouette sign', modality: 'XR', region: 'Chest', desc: 'Loss of a normal soft-tissue border (heart, diaphragm) by adjacent same-density opacity.', means: 'Localizes disease: right heart border → RML; left heart border → lingula; hemidiaphragm → lower lobe.' },
  { name: 'Deep sulcus sign', modality: 'XR', region: 'Chest', desc: 'Abnormally deep, lucent lateral costophrenic sulcus on a supine film.', means: 'Supine pneumothorax — air collects anteriorly and inferiorly rather than apically.' },
  { name: 'Continuous diaphragm sign', modality: 'XR', region: 'Chest', desc: 'The central diaphragm is visible in continuity beneath the heart.', means: 'Pneumomediastinum outlining the central diaphragm.' },
  { name: 'Golden S sign', modality: 'XR/CT', region: 'Chest', desc: 'RUL collapse with a reverse-S contour of the minor fissure: concave laterally, convex medially.', means: 'Central obstructing mass causing lobar collapse — think bronchogenic carcinoma in adults.' },
  { name: 'Luftsichel sign', modality: 'XR', region: 'Chest', desc: 'Para-aortic crescent of lucency in LUL collapse.', means: 'Hyperexpanded superior segment of the left lower lobe interposed against the arch — LUL collapse (check for central mass).' },
  { name: 'Kerley B lines', modality: 'XR', region: 'Chest', desc: 'Short horizontal peripheral lines reaching the pleura at the bases.', means: 'Thickened interlobular septa — interstitial edema (also lymphangitic carcinomatosis).' },
  { name: 'Bat-wing opacities', modality: 'XR', region: 'Chest', desc: 'Bilateral perihilar airspace opacity sparing the periphery.', means: 'Alveolar pulmonary edema (also hemorrhage, PJP in the right setting).' },
  { name: 'Westermark sign', modality: 'XR', region: 'Chest', desc: 'Regional oligemia (hyperlucency) distal to an occluded pulmonary artery.', means: 'Pulmonary embolism (insensitive but specific).' },
  { name: 'Hampton hump', modality: 'XR/CT', region: 'Chest', desc: 'Peripheral wedge-shaped pleural-based opacity.', means: 'Pulmonary infarct from PE.' },
  { name: 'Split pleura sign', modality: 'CT', region: 'Chest', desc: 'Thickened, enhancing visceral and parietal pleura separated by fluid.', means: 'Empyema (vs simple parapneumonic effusion).' },
  { name: 'Halo sign', modality: 'CT', region: 'Chest', desc: 'Ground-glass rim surrounding a pulmonary nodule.', means: 'Hemorrhagic nodule — classic for angioinvasive aspergillosis in neutropenia.' },
  { name: 'Reversed halo (atoll) sign', modality: 'CT', region: 'Chest', desc: 'Central ground-glass with a ring of consolidation.', means: 'Organizing pneumonia classically; also infarct, fungal disease.' },
  { name: 'Tree-in-bud', modality: 'CT', region: 'Chest', desc: 'Branching centrilobular nodularity like a budding tree.', means: 'Small-airway filling — endobronchial infection spread (TB, atypicals), aspiration.' },
  { name: 'Signet ring sign', modality: 'CT', region: 'Chest', desc: 'Bronchus wider than its accompanying artery.', means: 'Bronchiectasis.' },
  { name: 'Finger-in-glove', modality: 'XR/CT', region: 'Chest', desc: 'Branching tubular opacities from mucoid-impacted bronchi.', means: 'Mucus plugging — ABPA classically, also obstruction.' },

  // ——— Neuro ———
  { name: 'Hyperdense MCA sign', modality: 'CT', region: 'Neuro', desc: 'Attenuated (bright) MCA compared with the other side.', means: 'Acute intraluminal thrombus — large-vessel-occlusion stroke; correlate with CTA.' },
  { name: 'Insular ribbon sign', modality: 'CT', region: 'Neuro', desc: 'Loss of the normal grey–white definition of the insular cortex.', means: 'Early MCA-territory infarction.' },
  { name: 'Dense vessel / cord sign', modality: 'CT', region: 'Neuro', desc: 'Hyperdense dural venous sinus or cortical vein.', means: 'Cerebral venous thrombosis — confirm with venography; empty delta sign on contrast.' },
  { name: 'Empty delta sign', modality: 'CT+C', region: 'Neuro', desc: 'Enhancing dural walls around a non-enhancing clot in the superior sagittal sinus.', means: 'Dural venous sinus thrombosis.' },
  { name: 'Swirl sign (intracranial)', modality: 'CT', region: 'Neuro', desc: 'Low-density unclotted blood swirling within a hyperdense hematoma.', means: 'Active bleeding — hematoma likely to expand.' },
  { name: 'Restricted diffusion', modality: 'MRI', region: 'Neuro', desc: 'Bright DWI with correspondingly dark ADC.', means: 'Acute infarct (minutes–days); also abscess pus, hypercellular tumor, epidermoid.' },
  { name: 'Dural tail sign', modality: 'MRI+C', region: 'Neuro', desc: 'Tapering enhancement of dura adjacent to an extra-axial mass.', means: 'Suggests meningioma (not entirely specific).' },
  { name: 'Dawson fingers', modality: 'MRI', region: 'Neuro', desc: 'Ovoid periventricular FLAIR lesions oriented perpendicular to the ventricles.', means: 'Demyelination — multiple sclerosis.' },

  // ——— Abdomen ———
  { name: 'Rigler sign', modality: 'XR', region: 'Abdomen', desc: 'Both sides of the bowel wall visible (gas inside and outside).', means: 'Pneumoperitoneum on a supine film.' },
  { name: 'Football sign', modality: 'XR', region: 'Abdomen', desc: 'Large oval central lucency over the abdomen, falciform ligament as the "lacing".', means: 'Massive pneumoperitoneum — classically perforation in neonates.' },
  { name: 'Coffee bean sign', modality: 'XR', region: 'Abdomen', desc: 'Dilated ahaustral loop folded on itself, arising from the pelvis.', means: 'Sigmoid volvulus.' },
  { name: 'Whirl sign', modality: 'CT', region: 'Abdomen', desc: 'Swirled mesenteric vessels and fat.', means: 'Volvulus/internal hernia with mesenteric twisting — surgical urgency; in infants suggests midgut volvulus.' },
  { name: 'Small-bowel feces sign', modality: 'CT', region: 'Abdomen', desc: 'Particulate "feces-like" content in dilated small bowel.', means: 'Marks the segment just proximal to a small-bowel obstruction transition point.' },
  { name: 'Target sign (bowel)', modality: 'CT/US', region: 'Abdomen', desc: 'Mural stratification — alternating enhancing/edematous wall layers.', means: 'Bowel wall edema/inflammation (IBD, infection, ischemia-reperfusion); on US in a child = intussusception (doughnut).' },
  { name: 'Comb sign', modality: 'CT', region: 'Abdomen', desc: 'Engorged vasa recta lined up like comb teeth along a bowel segment.', means: 'Active inflammation — classically Crohn disease.' },
  { name: 'Sentinel clot sign', modality: 'CT', region: 'Abdomen', desc: 'Highest-density clotted blood collects next to the bleeding source.', means: 'Localizes the injured organ in hemoperitoneum.' },
  { name: 'Portal venous gas', modality: 'CT/US/XR', region: 'Abdomen', desc: 'Branching gas reaching within 2 cm of the liver capsule (vs central pneumobilia).', means: 'Ominous — bowel ischemia/necrosis (in neonates: NEC); pneumobilia is the more benign central pattern.' },
  { name: 'WES sign', modality: 'US', region: 'Abdomen', desc: 'Wall–Echo–Shadow: gallbladder wall, stone echo, dense shadow with no visible lumen.', means: 'Gallbladder contracted around packed stones — easy to mistake for bowel gas.' },
  { name: 'Sonographic Murphy sign', modality: 'US', region: 'Abdomen', desc: 'Maximal tenderness directly over the visualized gallbladder.', means: 'Supports acute cholecystitis (with stones, wall thickening, pericholecystic fluid).' },
  { name: 'Double duct sign', modality: 'CT/MRCP', region: 'Abdomen', desc: 'Dilation of both CBD and pancreatic duct.', means: 'Obstructing pancreatic head/ampullary mass until proven otherwise.' },
  { name: 'Claw sign', modality: 'CT/US', region: 'Abdomen', desc: 'Normal parenchyma splays around a mass like a claw.', means: 'Confirms organ of origin (classic: Wilms tumor arising from kidney).' },
  { name: 'Drooping lily sign', modality: 'Urography/CT', region: 'Abdomen', desc: 'Lower-pole collecting system displaced down and out.', means: 'Obstructed upper pole moiety of a duplex kidney (with ureterocele).' },
  { name: 'Bear claw ulcers', modality: 'CT', region: 'Abdomen', desc: 'Deep transmural colonic ulcerations.', means: 'Severe colitis pattern description (e.g., in IBD).' },

  // ——— Pediatric ———
  { name: 'Double bubble sign', modality: 'XR/US', region: 'Pediatric', desc: 'Two gas bubbles: stomach and dilated duodenal bulb, little/no distal gas.', means: 'Duodenal atresia (trisomy 21 association); if distal gas present, exclude midgut volvulus urgently.' },
  { name: 'Corkscrew sign', modality: 'Fluoro', region: 'Pediatric', desc: 'Spiral course of the duodenum/jejunum on upper GI.', means: 'Midgut volvulus — surgical emergency.' },
  { name: 'Target/doughnut sign (intussusception)', modality: 'US', region: 'Pediatric', desc: 'Concentric rings >2.5 cm in the right abdomen of a 3 mo–3 y child.', means: 'Ileocolic intussusception — proceed to air/hydrostatic enema reduction.' },
  { name: 'Pyloric measurements', modality: 'US', region: 'Pediatric', desc: 'Pyloric muscle ≥3 mm thick, channel ≥15 mm long, failure to open.', means: 'Hypertrophic pyloric stenosis (2–8 week old, projectile nonbilious vomiting).' },
  { name: 'Steeple sign', modality: 'XR', region: 'Pediatric', desc: 'Symmetric subglottic tracheal narrowing on the frontal neck film.', means: 'Croup.' },
  { name: 'Thumb sign', modality: 'XR', region: 'Pediatric', desc: 'Swollen epiglottis on the lateral neck film.', means: 'Epiglottitis — airway emergency; image only if safe.' },
  { name: 'Sail sign (thymic)', modality: 'XR', region: 'Pediatric', desc: 'Triangular right thymic lobe resembling a sail.', means: 'Normal thymus — not consolidation or mass.' },
  { name: 'Spinnaker sail sign', modality: 'XR', region: 'Pediatric', desc: 'Thymic lobes lifted up and out from the mediastinum.', means: 'Pneumomediastinum in a neonate (this one IS pathologic).' },
  { name: 'Classic metaphyseal lesion', modality: 'XR', region: 'Pediatric', desc: 'Corner or bucket-handle metaphyseal fracture fragment in an infant.', means: 'High specificity for non-accidental injury — triggers skeletal survey and protection workflow.' },
  { name: 'Klein line failure', modality: 'XR', region: 'Pediatric', desc: 'Line along the superior femoral neck fails to intersect the epiphysis.', means: 'Slipped capital femoral epiphysis (10–16 y, limp/knee pain) — frog-leg lateral confirms.' },
  { name: 'Halo/double-rim sign (esophageal)', modality: 'XR', region: 'Pediatric', desc: 'Double ring on an ingested disc-shaped foreign body.', means: 'Button battery, not a coin — emergent removal (necrosis within hours).' },

  // ——— MSK ———
  { name: 'Posterior fat pad sign', modality: 'XR', region: 'MSK', desc: 'Any visible posterior fat lucency at the elbow.', means: 'Joint effusion → occult fracture in trauma (child: supracondylar; adult: radial head).' },
  { name: 'Sail sign (elbow)', modality: 'XR', region: 'MSK', desc: 'Elevated triangular anterior fat pad.', means: 'Elbow effusion — same implication as the posterior fat pad.' },
  { name: 'Terry Thomas sign', modality: 'XR', region: 'MSK', desc: 'Scapholunate interval >3 mm (gap-toothed).', means: 'Scapholunate dissociation.' },
  { name: 'Segond fracture', modality: 'XR', region: 'MSK', desc: 'Small avulsion off the lateral tibial rim.', means: 'Marker of ACL tear (and lateral capsular injury) — MRI next.' },
  { name: 'Lipohemarthrosis (FBI sign)', modality: 'XR/CT', region: 'MSK', desc: 'Fat–blood interface level in a joint on horizontal-beam view.', means: 'Intra-articular fracture (marrow fat has entered the joint) — hunt the fracture, often tibial plateau.' },
  { name: 'Light bulb sign', modality: 'XR', region: 'MSK', desc: 'Humeral head fixed in internal rotation looks symmetric and round.', means: 'Posterior shoulder dislocation (seizure/electrocution) — get an axillary or Y view.' },
  { name: 'Codman triangle', modality: 'XR', region: 'MSK', desc: 'Elevated periosteum ossified only at the margin of a lesion.', means: 'Aggressive periosteal reaction — osteosarcoma and other fast processes.' },
  { name: 'Crescent sign (AVN)', modality: 'XR/MRI', region: 'MSK', desc: 'Subchondral lucent crescent in the femoral head.', means: 'Osteonecrosis with subchondral fracture — precedes collapse.' },

  // ——— Ultrasound / vascular ———
  { name: 'Twinkle artifact', modality: 'US', region: 'GU', desc: 'Rapidly alternating color Doppler behind a rough reflector.', means: 'Supports a calculus (renal/ureteric) when the grey-scale stone is subtle.' },
  { name: 'Ring of fire', modality: 'US', region: 'Pelvis', desc: 'Circumferential Doppler flow around an adnexal ring.', means: 'Seen with ectopic pregnancy AND corpus luteum — location (in vs out of ovary) and hCG context decide.' },
  { name: 'Whirlpool sign (torsion)', modality: 'US', region: 'GU', desc: 'Twisted vascular pedicle swirls on Doppler.', means: 'Ovarian or testicular torsion — surgical emergency.' },
  { name: 'B-lines', modality: 'US', region: 'Chest', desc: 'Laser-like vertical reverberation artifacts from the pleural line, erasing A-lines.', means: 'Interstitial syndrome — edema when diffuse and bilateral; a few are normal at the bases.' },
  { name: 'Barcode/stratosphere sign', modality: 'US', region: 'Chest', desc: 'M-mode shows static parallel lines instead of the sandy "seashore".', means: 'Absent lung sliding — pneumothorax (find the lung point to confirm).' },
  { name: 'Yin-yang sign', modality: 'US/CT', region: 'Vascular', desc: 'Swirling bidirectional Doppler flow within a sac.', means: 'Pseudoaneurysm.' }
];

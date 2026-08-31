# 🩻 Radiology Interpretation Academy

A self-contained web application for teaching yourself the interpretation of radiologic imaging across the **entire pediatric and adult body** — modality by modality, system by system.

No build step, no server, no account. Open `index.html` in a modern browser and start studying. All of your data (studies, images, notes, progress, flashcards) stays in your own browser.

## What's inside

| Section | What it teaches |
|---|---|
| **📚 Modalities** | How each modality makes its image and how to read its language: Radiography (5 densities, RIPE technique), CT (Hounsfield units, windowing, contrast phases), MRI (sequences, DWI/ADC, safety), Ultrasound (echogenicity, artifacts-as-tools, Doppler), Fluoroscopy & contrast studies, Nuclear Medicine & PET (tracers, biodistribution), Mammography (BI-RADS), and an Interventional Radiology overview. Every module ends with pediatric considerations and key points. |
| **🧭 Systematic Approaches** | Interactive step-by-step checklists that build professional search patterns: adult & pediatric CXR, abdominal radiograph, neonatal abdomen/NEC, non-contrast head CT ("Blood Can Be Very Bad"), cervical spine CT, chest CT, CT abdomen/pelvis, brain MRI, MSK radiograph & fracture description, ultrasound approach, structured reporting & critical-results communication, and search patterns & cognitive error (satisfaction of search, anchoring). Each has pearls and classic misses. |
| **🗺️ Radiologic Anatomy** | Region-by-region imaging anatomy with adult norms **and pediatric deltas side-by-side**: brain (CT levels, vascular territories), head & neck spaces, spine, chest & mediastinum (with labeled CXR diagram), cardiac & great vessels, abdomen (Couinaud, SAD PUCKER), pelvis/GU, upper limb (CRITOE diagram), lower limb (pediatric hip timeline), pediatric skeletal development (Salter-Harris, NAI, variants), and pediatric chest/abdomen differences. |
| **📁 My Study Library** | Your personal teaching file. Create studies, upload image series (PNG/JPEG and uncompressed DICOM), and read them in a PACS-style viewer: stack scroll, zoom/pan, true window/level for DICOM, invert, rotate, numbered annotations. Practice writing structured reports (history → findings → impression → diagnosis → teaching points) with autosave. |
| **🃏 Flashcards** | ~60 seeded cards across Physics & Safety, Chest, Neuro, Abdomen, MSK, Pediatrics, Signs and Measurements, scheduled by SM-2 spaced repetition. Add unlimited cards of your own. |
| **❓ Quizzes** | 6 quizzes (~48 questions) with full explanations: physics & safety, CXR, head CT/neuro, abdominal, MSK & trauma, and pediatric imaging. Best scores tracked. |
| **💡 Classic Signs** | Searchable glossary of ~60 named signs (air bronchogram → whirlpool sign) with appearance and meaning. A "sign of the day" appears on the dashboard. |
| **📏 Measurements** | Adult and pediatric normal values and thresholds (3-6-9 rule, CBD, pyloric measurements, ADI, Graf angle, line positions…) plus typical radiation doses for justification thinking. |

## Running it

- **Simplest:** double-click `index.html` (works from `file://`).
- **Nicer:** serve it — `python3 -m http.server` in this folder, then open http://localhost:8000.
- **Hosted:** enable GitHub Pages for this repo/folder; the app is fully static.

DICOM support loads the `dicom-parser` library from a CDN; without a network connection the app still works fully for PNG/JPEG images.

## Suggested workflow

1. **Foundation** — work through the Modalities modules.
2. **Ritual** — pick one Systematic Approach at a time and run its checklist against real teaching cases until it's automatic.
3. **Anatomy in parallel** — one region per week, always noting the pediatric deltas.
4. **Bank cases** — collect anonymized, openly licensed teaching images (e.g., from Radiopaedia — check each case's license) into the Study Library. Write your findings and impression *before* revealing the diagnosis.
5. **Retain** — clear due flashcards daily; retake quizzes to stable ≥85%.
6. **Speed comes last** — accuracy through repetition of one search pattern; speed follows on its own.

## Privacy & scope

- Everything is stored locally (IndexedDB + localStorage). Clearing site data erases your library — export/back up anything precious.
- **Never store images containing patient-identifiable information.** Anonymize first.
- This is a personal education tool: not medical advice, not a diagnostic device, and no substitute for accredited training, supervision, or current local protocols.

## Tech

Plain HTML/CSS/JavaScript (no framework, no build). IndexedDB for image blobs, localStorage for progress/SRS state, `dicom-parser` (CDN) for uncompressed DICOM rendering with real window/level, canvas-based viewer, hash-based router.

# Pipeline Learnings & Lessons (`learning.md`)

This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.

## database-search
- Avoid PubChem for protein targets and biologics; the PUG REST API relies on Compound Identifiers (CIDs) and consistently returns 404 errors.
- Search openFDA by brand (e.g., “Vyloy”) or generic name (e.g., “zolbetuximab”) as target names are not indexed in safety and label data.
- On ClinicalTrials.gov, use English symbols (CLDN18.2), spaced synonyms (Claudin 18.2), and hyphenated variants (Claudin-18.2) to capture maximum multinational sponsor records.
- In NMPA CDE, use English gene symbols first; formal Chinese descriptions (紧密连接蛋白) capture specific domestic programs (e.g., Innovent), while phonetic translations often fail.
- Identify Chinese biologics/ADCs in NMPA CDE/ChiCTR using the “注射用” (Injectable) prefix and alphanumeric asset codes (e.g., “CT041”, “JS107”, “IBI343”).
- Chinese WHO registries (ChiCTR/ICTRP) favor English official gene symbols (CLDN18.2); Mandarin phonetic or formal translations typically yield zero results.
- Use EU CTIS and ANZCTR to track "Biology before Stage" protocols and multiplex testing (CLDN18.2, HER2, PD-L1, MSI, EBV) for patient stratification.
- Conference databases track resistance mechanisms such as secondary loss of expression and intrapatient heterogeneity between primary and metastatic sites.
- Monitor conference abstracts for target expansion into emerging or rare indications (Biliary Tract, Pancreatic, Urachal, or Mucinous Ovarian Cancer).
- Patent databases (Lens.org) are sensitive to decimals; search by parent protein name (e.g., “Claudin 18”) and avoid generic drug names (e.g., “Zolbetuximab”).
- In IP searches, focus on Extracellular Loop 1 (ECL1) and isoform specificity to avoid cross-reactivity with off-target tissue (e.g., CLDN18.1 in lung).
- ClinicalTrials.gov distinguishes inclusion thresholds by modality: high (e.g., ≥75% for mAbs) vs. moderate (e.g., ≥50% for ADCs/CAR-Ts) using 2+/3+ IHC intensity.
- Access NMPA CDE to monitor the “immuno-cytotoxic convergence” trend, specifically Phase III registrations of ADCs combined with PD-1 inhibitors in first-line settings.
- Use openFDA to identify labeled toxicity patterns for approved targets, such as severe nausea, vomiting, and hematologic abnormalities (e.g., neutropenia).
- Mark a search as complete only after attempting gene symbols, spaced synonyms, parent protein names, and specific diagnostic clones (e.g., “43-14A”).
- For combination regimens (e.g. `IBI343,sintilimab...`) and Chinese CDE records containing trial descriptions/suffixes in parentheses (e.g., `IMC002注射液 (...)`), use the LLM agent to cleanly consolidate them under their base canonical molecule names, mapping the messy combination/trial strings to aliases. Penalize combo-regimen indicators and trial title patterns in the canonical sorting keys to prevent messy names from becoming the canonical table rows.

## web-search
- **Query Formatting & Length Constraints**: Keep queries concise, focus on a few key terms, and avoid complex syntax to prevent search engine errors. Strip special characters or shorten queries if no results are found.
- **Entity Combination**: Search using the drug code/name combined with the lead sponsor/developer's name, mechanism of action, or target class to filter out noise.
- **Identifier-based Searching**: Prioritize searching with clinical trial identifiers (NCT numbers) or synonyms (brand name, generic name, asset code) for precise candidate tracking.
- **Source & Indication Keywords**: Incorporate trial keywords (e.g., "safety", "efficacy", "Phase 1"), indication keywords, conference names (e.g., "ASCO", "ESMO"), or status terms ("discontinued", "terminated") to retrieve targeted clinical/preclinical readouts.
- **Chinese Registry Mapping**: For CTR entries or Chinese registry assets, search via English equivalents, descriptions, or linked NCT numbers to obtain higher-quality indexing.

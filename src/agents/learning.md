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
- API Error (HTTP 400): {"error":{"code":400,"message":"API key not valid. Please pass a valid API key.","status":"INVALID_ARGUMENT"}}
- Search for clinical trial identifiers (NCT numbers) directly—they uniquely identify studies and yield the most precise results for drug candidates.
- Combine the drug code with the developing company’s name (e.g., “AZD5863 AstraZeneca”) to filter out irrelevant hits from other fields.
- Add the mechanism of action or target (e.g., “CLDN18.2”, “ADC”, “Bispecific T-cell engager”) to focus results on the therapeutic context.
- When a drug code is ambiguous or returns spam, try its alternative name (brand name, generic name) or a synonym (e.g., “tecotabart vedotin” for LM-302).
- Search for conference abstracts (ASCO, ESMO, AACR) by combining drug name with “ASCO 2024” or “ESMO 2025” to locate public safety and efficacy data.
- For Chinese trial registry entries (CTRxxx), use an English description of the trial or the corresponding NCT number; direct CTR searches often return irrelevant content.
- Include keywords like “safety”, “efficacy”, “phase 1”, or “clinical trial” in the query to improve relevance to due diligence.
- Enclose exact compound names in double quotes when they share common words (e.g., “2-Targeted” or “5Fluorouracil”).
- Append “discontinued” or “terminated” to the search for candidates that were halted to quickly identify termination details.
- Company press releases and investor materials are reliable sources for milestones (regulatory designations, trial initiations) and should be searched directly on the company site.
- For selectivity or preclinical data, add terms like “selectivity”, “binding affinity”, or “expression” to the query.
- Limit search queries to a few key terms; overly complex syntax can trigger API errors (e.g., “query is mandatory” on DuckDuckGo).
- When a search returns no results, reduce the query length or remove special characters before retrying.
- For drugs developed by multiple institutions, pick the lead sponsor or one major hospital as the developer in the search.
- Include the drug’s target class (e.g., “ADC targeting CLDN18.2”) to distinguish it from unrelated compounds with similar codes.

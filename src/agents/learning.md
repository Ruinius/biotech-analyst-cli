# Pipeline Learnings & Lessons (`learning.md`)

This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.

## database-search
- Avoid PubChem for protein targets and biologics; the PUG REST API relies on Compound Identifiers (CIDs) and consistently returns 404 errors.
- Search openFDA by brand (e.g., “Vyloy”) or generic name (e.g., “zolbetuximab”) as target names are not indexed in safety and label data.
- On ClinicalTrials.gov, use spaced synonyms (e.g., “Claudin 18.2”) for max coverage and hyphenated variants (e.g., “Claudin-18.2”) for multinational sponsor records.
- In NMPA CDE, use English gene symbols first, then attempt the formal Chinese description (e.g., “紧密连接蛋白”) to capture specific domestic registrations.
- Identify Chinese biologics and ADCs in NMPA CDE/ChiCTR using the “注射用” (Injectable) prefix and alphanumeric asset codes (e.g., “CT041”, “JS107”).
- Chinese WHO registries (ChiCTR/ICTRP) favor English official gene symbols; Mandarin phonetic or formal translations often yield zero results.
- Use EU CTIS and ANZCTR to identify "Biology before Stage" protocols and multiplex testing trends (e.g., SAPHIR) for targets alongside HER2 or PD-L1.
- Conference databases are the primary source for tracking resistance mechanisms like secondary loss of expression or intrapatient heterogeneity.
- Monitor conference abstracts for target expansion into emerging indications (e.g., Biliary Tract or Pancreatic Cancer) before they reach registries.
- Patent databases (Lens.org) are sensitive to decimals; avoid isoform suffixes (e.g., “.2”) in favor of parent protein names (e.g., “Claudin 18”).
- Search Lens.org by technical target name rather than generic drug names (e.g., “Zolbetuximab”), which often return zero results in IP databases.
- Use ClinicalTrials.gov to identify Phase II/III diagnostic inclusion thresholds, such as specific IHC membrane staining intensity requirements (e.g., 2+ or 3+).
- Access Chinese registries via direct web portals (NMPA CDE) to find the most current trial recruitment statuses and Phase III expansion data.
- Do not retry searches for terms that trigger API errors (HTTP 400/404); these indicate fundamental tool or entity type limitations.
- Mark a search as complete only after attempting official gene symbols, spaced English synonyms, and parent protein names in patent tools.

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

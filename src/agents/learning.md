# Pipeline Learnings & Lessons (`learning.md`)

This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.

## database-search
- Avoid PubChem for protein targets and biologics (e.g., antibodies); they lack Compound Identifiers (CIDs) and consistently return 404 errors.
- On ClinicalTrials.gov, use spaced synonyms (e.g., “Claudin 18.2”) as they often capture more descriptive clinical records than official gene symbols.
- In NMPA CDE, use English gene symbols first, but attempt the formal Chinese description (e.g., “紧密连接蛋白”) to capture specific domestic registrations.
- Chinese WHO registries (ChiCTR/ICTRP) favor English official gene symbols; Mandarin phonetic or formal translations often yield zero results.
- Search openFDA by brand (e.g., “Vyloy”) or generic name (e.g., “zolbetuximab”) as target names are not indexed in safety and label data.
- Identify Chinese biologics and ADCs in NMPA CDE using the “注射用” (Injectable) prefix followed by alphanumeric asset codes (e.g., “注射用JS107”).
- Conference databases are the primary source for tracking resistance mechanisms, such as secondary loss of expression or intrapatient heterogeneity.
- Patent databases (e.g., Lens.org) are extremely sensitive to punctuation and decimals; avoid isoform suffixes (e.g., “.2”) in favor of parent protein names.
- Broaden patent searches from specific isoforms to the parent name (e.g., “Claudin 18”) to overcome low sensitivity and technical indexing limitations.
- Clinical registries (EU CTIS, ANZCTR) may return literature citations or registry testing protocols (e.g., SAPHIR) rather than raw trial records.
- Use EU CTIS and ANZCTR to identify regional diagnostic profiles and multiplex testing trends (e.g., “Biology before Stage”) for targets alongside HER2 or PD-L1.
- Access Chinese registries via direct web portals (NMPA CDE) to find the most current trial recruitment statuses and Phase III expansion data.
- Do not retry searches for terms that trigger API errors (HTTP 400/404); these indicate fundamental tool or entity type limitations.
- Search conference abstracts for clinicopathologic correlates to identify emerging indications (e.g., Biliary Tract or Pancreatic Cancer) before they reach registries.
- Mark a database search as complete only after attempting official gene symbols, spaced English synonyms, and parent protein names in patent tools.

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

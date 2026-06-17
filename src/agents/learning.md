# Pipeline Learnings & Lessons (`learning.md`)

This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.

## database-search
- Avoid PubChem for protein targets; they lack Compound Identifiers (CIDs) and consistently return 404 errors.
- Use English official gene symbols (e.g., “CLDN18.2”) over descriptive synonyms to maximize coverage in NMPA CDE and technical databases.
- Clinical registries (EU CTIS, ANZCTR) may return literature citations instead of raw trial records, indicating tool-specific indexing behavior.
- Search openFDA by brand name (e.g., “Vyloy”) or generic name (e.g., “zolbetuximab”) as target names are rarely indexed in safety and label data.
- Identify Chinese biologic and ADC trials in NMPA CDE using the “注射用” (Injectable) prefix followed by alphanumeric asset codes (e.g., “注射用JS107”).
- Conference databases are the primary source for tracking resistance mechanisms, such as secondary loss of expression or intrapatient heterogeneity.
- ClinicalTrials.gov synonyms often yield identical result counts; a single search with a common synonym is usually sufficient to capture relevant trials.
- Patent databases (e.g., Lens.org) are extremely sensitive to punctuation; test hyphenated, spaced, and concatenated strings (e.g., “Claudin-18.2” vs. “Claudin 18.2”).
- To overcome low sensitivity in patent registries, broaden searches from specific isoforms to the parent protein name (e.g., “Claudin 18”).
- Do not retry searches for terms that trigger API errors (HTTP 400/404); these indicate fundamental tool or entity type limitations.
- Use EU CTIS and ANZCTR to identify regional registries (e.g., SAPHIR) and diagnostic profiles where targets are tested alongside HER2 or PD-L1.
- Access Chinese registries via direct web portals as they provide the most current trial recruitment statuses and Phase III expansion data.
- If high-profile targets yield zero patent hits, verify if records are filed under broader classifications or specific preparation methods (e.g., “recombinant vaccine”).
- Search conference abstracts for clinicopathologic correlates to identify emerging indications (e.g., Biliary Tract Cancer) before they appear in standard registries.
- Mark a database search as complete only after attempting both official gene symbols and common English synonym variations.

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

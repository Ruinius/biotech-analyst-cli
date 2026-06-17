# Pipeline Learnings & Lessons (`learning.md`)

This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.

## database-search
- Avoid PubChem for protein targets; it indexes small molecules and will return 404 errors or irrelevant records.
- Use English official gene symbols (e.g., “CLDN18.2”) over descriptive synonyms or direct Chinese translations to maximize coverage in technical databases.
- If clinical registries (EU CTIS, ANZCTR) return literature citations instead of raw trial records, it indicates a tool-specific indexing behavior rather than a synonym error.
- For FDA regulatory data (openFDA), search by specific drug product names (e.g., “zolbetuximab”) rather than protein target synonyms to find relevant records.
- NMPA CDE (China) effectively returns IND records using official gene symbols (e.g., “CLDN18.2”), while descriptive English and Chinese synonyms often fail.
- Conference databases are the primary source for tracking emerging modality shifts (e.g., CAR-T, bispecifics) and pathological insights like expression heterogeneity.
- ClinicalTrials.gov synonyms often yield highly overlapping results; a single search with the most common synonym is usually sufficient to capture relevant trials.
- Patent databases (e.g., Lens.org) are extremely sensitive to string formatting; removing spaces (e.g., "Claudin18.2") may yield results where spaced terms fail entirely.
- To overcome low sensitivity in patent registries, broaden searches from specific isoforms (e.g., "CLDN18.2") to the parent protein name (e.g., "Claudin 18").
- Do not retry searches for terms that trigger API errors (HTTP 400/404); these indicate fundamental tool or entity type limitations.
- Use EU CTIS and ANZCTR to identify regional combinations and registry-based diagnostic profiles (e.g., SAPHIR) not always listed on ClinicalTrials.gov.
- Access Chinese registries like ChiCTR via direct web portals as they may not index trial records reliably via generic aggregate search tools.
- If high-profile clinical targets yield zero patent hits, verify if records are filed under broader classification terms or specific preparation methods (e.g., "recombinant vaccine").
- Subtle synonym variations in patent databases can lead to zero-result failures, necessitating the testing of both spaced and concatenated alphanumeric strings.
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

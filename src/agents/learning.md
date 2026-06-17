# Pipeline Learnings & Lessons (`learning.md`)

This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.

## database-search
- For protein targets (e.g., Claudin 18.2), avoid PubChem compound search; it returns 404 because the tool indexes small molecules, not proteins.
- Use both English synonyms (with/without space) and official gene symbols (e.g., “CLDN18.2”) to maximize coverage; direct Chinese translations (e.g., “克劳丁18.2”) may consistently fail or return no results in some Chinese databases.
- When a search tool for clinical trial registries (e.g., EU CTIS, ANZCTR, Chinese WHO) consistently returns literature (PubMed/Medline) instead of trial records, verify the data source; this indicates a tool integration issue, and further synonym searches are unlikely to fix it.
- For FDA regulatory data (openFDA), protein targets yield no records; search by drug product names (e.g., “zolbetuximab”) instead of target synonyms.
- NMPA CDE (Chinese regulator) successfully returns IND records using English synonyms, especially official gene symbols (e.g., “CLDN18.2” yields more results than “Claudin 18.2”); the Chinese synonym consistently fails.
- Conference databases (e.g., ASCO, AACR) effectively return relevant abstracts, and using multiple English synonyms (e.g., 'Claudin 18.2', 'CLDN18.2', 'Claudin18.2') can provide comprehensive coverage, even if full abstract text is not always accessible via the tool.
- ClinicalTrials.gov consistently returns a high number of trials (e.g., up to 50) per synonym; common English synonym variations often yield highly overlapping results, suggesting a single comprehensive search may be sufficient.
- API errors (HTTP 400/404) may indicate tool limitations (e.g., invalid API key, unsupported entity type); document the error and do not retry the same term.
- For Chinese registries (ChiCTR), a direct web portal search is often recommended over generic synonyms via tools, as they may not index trial records reliably.
- After exhausting all relevant synonyms, if a database still yields incorrect data types or explicit 'no results' errors, mark the search as complete for that database via the current tool/method.
- For patent databases (e.g., Lens.org), subtle synonym variations (e.g., 'Claudin18.2' vs 'Claudin 18.2') can significantly impact results, even leading to zero results for common terms.
- Patent databases may require more specific keyword combinations or have limited coverage for certain targets or jurisdictions compared to clinical/literature databases.

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

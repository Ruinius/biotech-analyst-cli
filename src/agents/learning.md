# Pipeline Learnings & Lessons (`learning.md`)

This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.

## database-search
- Use English gene symbols (CLDN18.2), spaced synonyms (Claudin 18.2), and hyphenated variants across all registries; use alphanumeric codes (e.g., IBI343, JS107) as primary identifiers for Chinese ADC and CAR-T programs.
- In NMPA CDE, use formal Chinese descriptions (紧密连接蛋白) to capture domestic programs from Innovent or CSPC; alphanumeric codes (e.g., JS107, SYSA1801) are the most effective identifiers for high-potency ADCs.
- Distinguish IHC inclusion thresholds by modality: high expression (≥75%, 2+/3+ intensity) for monoclonal antibodies versus moderate expression (≥40-50%) for potent ADCs and CAR-T therapies.
- Track CLDN18.2 as part of the standard "Big 5" biomarker panel (alongside HER2, PD-L1, MSI, and EBV) in EU CTIS and SAPHIR registries for patient stratification in gastric cancer.
- Focus Lens.org searches on parent protein names (Claudin 18) and foundational inventors (Sahin, Türeci); commercial diagnostic clone names like "43-14A" typically yield zero results in IP titles and abstracts.
- Monitor conference abstracts for resistance mechanisms such as secondary loss of target expression and intrapatient heterogeneity between primary gastric tumors and metastatic sites (e.g., peritoneal or lung).
- Track target expansion beyond Gastric/GEJ cancer into Pancreatic (PDAC), Biliary Tract (BTC), Colorectal (CRC), Urachal, and Small Bowel Adenocarcinomas.
- Search openFDA by brand (Vyloy) or generic name (zolbetuximab) to identify labeled toxicities, primarily severe nausea, vomiting, neutropenia, and infusion-related reactions.
- Monitor NMPA CDE for "immuno-cytotoxic convergence" trends, specifically Phase III registrations of CLDN18.2 ADCs combined with PD-1 inhibitors (e.g., sintilimab, toripalimab) in first-line settings.
- Use an LLM agent to map combination regimens and trial-specific suffixes (e.g., "IMC002注射液 (...)") to base canonical molecule names to prevent messy trial titles from becoming table rows.

## web-search
- **Query Formatting & Length Constraints**: Keep queries concise, focus on a few key terms, and avoid complex syntax to prevent search engine errors. Strip special characters or shorten queries if no results are found.
- **Entity Combination**: Search using the drug code/name combined with the lead sponsor/developer's name, mechanism of action, or target class to filter out noise.
- **Identifier-based Searching**: Prioritize searching with clinical trial identifiers (NCT numbers) or synonyms (brand name, generic name, asset code) for precise candidate tracking.
- **Source & Indication Keywords**: Incorporate trial keywords (e.g., "safety", "efficacy", "Phase 1"), indication keywords, conference names (e.g., "ASCO", "ESMO"), or status terms ("discontinued", "terminated") to retrieve targeted clinical/preclinical readouts.
- **Chinese Registry Mapping**: For CTR entries or Chinese registry assets, search via English equivalents, descriptions, or linked NCT numbers to obtain higher-quality indexing.

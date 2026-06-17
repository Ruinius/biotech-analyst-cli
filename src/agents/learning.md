# Pipeline Learnings & Lessons (`learning.md`)

This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.

## database-search
- Use English gene symbols (CLDN18.2), spaced synonyms (Claudin 18.2), and alphanumeric codes (IBI343, JS107) as primary identifiers; in openFDA, search by brand (Vyloy) or generic (zolbetuximab) only, as gene symbols often yield zero hits in drug label registries.
- In PubChem, the name-to-CID resolution path fails for biologics; pivot to Protein Accession numbers or Assay IDs (AID) to retrieve bioactivity data for monoclonal antibodies and specific isoforms.
- Monitor NMPA CDE for "immuno-cytotoxic convergence" trends, specifically Phase III registrations of CLDN18.2 ADCs combined with PD-1 inhibitors (e.g., sintilimab, toripalimab, tislelizumab) in first-line settings.
- Track CLDN18.2 as part of the standard "Big 5" biomarker panel (alongside HER2, PD-L1, MSI, and EBV) in EU CTIS and SAPHIR registries; note its 2026 inclusion in formal ASCO treatment guidelines.
- Focus Lens.org searches on parent protein names (Claudin 18) and foundational inventors (Sahin, Türeci); recent filings indicate a 2024 peak in patents for high-potency ADCs and multi-agent combination regimens.
- Distinguish IHC inclusion thresholds by modality: high expression (≥75%, 2+/3+ intensity) for monoclonal antibodies versus moderate expression (≥40-50%) for potent ADCs and CAR-T therapies leveraging the bystander effect.
- Monitor conference abstracts for resistance mechanisms such as intrapatient heterogeneity (discrepancy between primary tumors and metastatic sites) and secondary loss of target expression, which necessitates re-biopsy upon progression.
- Track target expansion beyond Gastric/GEJ into "cold" tumors like Pancreatic (PDAC) and Biliary Tract (BTC), as well as rare indications like Urachal and Small Bowel Adenocarcinoma (e.g., ENVELOPE trial).
- Use alphanumeric codes (e.g., SYSA1801, SHR-A1904, CT041) to track high-potency programs in Chinese registries, where the market is reaching recruitment saturation for gastric indications.
- Use an LLM agent to map combination regimens and trial suffixes (e.g., "IMC002注射液") to canonical names and identify emerging "CAR-armored-cell" or bispecific (CLDN18.2 x CD3) modalities.

## web-search
- **Query Formatting & Length Constraints**: Keep queries concise, focus on a few key terms, and avoid complex syntax to prevent search engine errors. Strip special characters or shorten queries if no results are found.
- **Entity Combination**: Search using the drug code/name combined with the lead sponsor/developer's name, mechanism of action, or target class to filter out noise.
- **Identifier-based Searching**: Prioritize searching with clinical trial identifiers (NCT numbers) or synonyms (brand name, generic name, asset code) for precise candidate tracking.
- **Source & Indication Keywords**: Incorporate trial keywords (e.g., "safety", "efficacy", "Phase 1"), indication keywords, conference names (e.g., "ASCO", "ESMO"), or status terms ("discontinued", "terminated") to retrieve targeted clinical/preclinical readouts.
- **Chinese Registry Mapping**: For CTR entries or Chinese registry assets, search via English equivalents, descriptions, or linked NCT numbers to obtain higher-quality indexing.

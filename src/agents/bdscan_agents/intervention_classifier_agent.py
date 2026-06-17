"""
LLM-based intervention classifier agent.

Handles all LLM-based intervention classification and alias resolution logic.
Moved from src/tools/classify_interventions.py to become a dedicated BD Scan agent.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.services.llm_client import LLMClient


class AssetList(list):
    def __contains__(self, item):
        if isinstance(item, str):
            item_lower = item.lower()
            for entry in self:
                if isinstance(entry, dict):
                    canon = entry.get("canonical_name", "")
                    aliases = entry.get("aliases", [])
                    if canon.lower() == item_lower or any(
                        a.lower() == item_lower for a in aliases
                    ):
                        return True
                elif isinstance(entry, str):
                    if entry.lower() == item_lower:
                        return True
            return False
        return super().__contains__(item)


def classify_interventions(
    names: list,
    target_name: str,
    target_synonyms: list | None = None,
    batch_size: int = 15,
) -> AssetList:
    """
    Use the configured LLM to classify raw intervention names from clinical
    trial registries as pipeline assets or background/comparator agents.

    Returns an AssetList of dicts representing the pipeline assets:
      {"canonical_name": "...", "aliases": [...], "modality": "...", "targets": [...], "filtered_terms": [...]}

    Raises RuntimeError on any LLM failure — no silent fallback.
    """
    synonyms = target_synonyms or []
    synonyms_str = ", ".join(synonyms) if synonyms else target_name

    # Deduplicate: case-insensitive key → preserve first-seen casing
    seen_lower: dict = {}
    for n in names:
        stripped = n.strip()
        key = stripped.lower()
        if stripped and key not in seen_lower:
            seen_lower[key] = stripped
    unique_names = list(seen_lower.values())

    if not unique_names:
        return AssetList()

    client = LLMClient()
    all_assets = AssetList()

    total_batches = (len(unique_names) + batch_size - 1) // batch_size
    print(
        f"\nClassifying {len(unique_names)} unique intervention name(s) via LLM "
        f"({total_batches} batch(es) of ≤{batch_size})..."
    )

    def process_single_batch(batch_idx: int, batch: list) -> tuple[list, list]:
        batch_json = json.dumps(batch, ensure_ascii=False)

        prompt = (
            f"You are classifying pharmaceutical intervention names from clinical trial registries.\n\n"
            f"Research target: {target_name}\n"
            f"Target synonyms: {synonyms_str}\n\n"
            f"Identify which of the names in the input list are pipeline assets targeting {target_name} (primary target).\n"
            f"An asset name MUST be a specific molecule name, brand name, or codename/laboratory code.\n"
            f"Group synonym names/codes from the input list together under the same asset, select a canonical name, and annotate modality/targets.\n\n"
            f"Input names:\n{batch_json}\n\n"
            f"Respond ONLY with a valid JSON object with exactly two keys:\n"
            f'  "assets": a list of objects, one per asset, with the keys:\n'
            f'     "canonical_name": string (most standard/common name)\n'
            f'     "aliases": list of strings (other names/codes for this asset from the input list)\n'
            f'     "modality": string (e.g., "Monoclonal Antibody", "ADC", "Small Molecule")\n'
            f'     "targets": list of strings (e.g., ["{target_name}"])\n'
            f'     "filtered_terms": list of strings (any generic/background terms related to this asset)\n'
            f'  "background": a list of strings containing all other input names that are not pipeline assets (e.g., placebos, generic modalities like chemotherapy, other targets, etc.)\n\n'
            f"Every input name must be accounted for either in 'assets' or in 'background'. No explanation, no other text."
        )

        system_instruction = (
            "You are a biotech drug classification expert with deep knowledge of "
            "pharmaceutical naming conventions, clinical trial nomenclature, and "
            "approved global drugs. Output only valid JSON with no markdown fencing. "
            "When uncertain, classify as 'background'.\n"
            "CRITICAL: An asset name MUST be a specific molecule name, brand name, or codename. "
            "Never classify general terms (like 'immunotherapy', 'chemotherapy', 'placebo'), "
            "other targets (like 'HER2', 'EGFR'), or target descriptions as an 'asset'. "
            "Novel investigational assets typically have alphanumeric codes "
            "(e.g. AMG910, SHR-A1904, AZD6422) or USAN/INN stems "
            "(-mab, -tib, -cept, -mig, -can, -bart) with a sponsor-specific prefix "
            "that does not match any approved drug name."
        )

        # Call with stream=False to prevent interleaved console logs
        try:
            response = client.query(prompt, system_instruction, stream=False)
        except TypeError as e:
            if "unexpected keyword argument" in str(e) and "stream" in str(e):
                response = client.query(prompt, system_instruction)
            else:
                raise

        if (
            not response
            or response.startswith("Error:")
            or response.startswith("Failed to call")
        ):
            raise RuntimeError(
                f"LLM intervention classification failed for batch "
                f"{batch_idx + 1}/{total_batches}: {response}"
            )

        # Strip markdown code fences if the LLM wrapped the output
        clean_response = response.strip()
        if clean_response.startswith("```"):
            clean_response = re.sub(r"^```[a-z]*\n?", "", clean_response)
            clean_response = re.sub(r"\n?```$", "", clean_response.strip())

        try:
            result = json.loads(clean_response)
            raw_assets = []
            if "assets" in result and isinstance(result["assets"], list):
                raw_assets = result["assets"]
            elif "asset" in result and isinstance(result["asset"], list):
                # Legacy compatibility support
                for name in result["asset"]:
                    raw_assets.append(
                        {
                            "canonical_name": name,
                            "aliases": [],
                            "modality": "N/A",
                            "targets": [target_name],
                            "filtered_terms": [],
                        }
                    )
            classified_background: list = result.get("background", [])
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"LLM returned unparseable JSON for batch "
                f"{batch_idx + 1}/{total_batches}: {exc}\n"
                f"Raw response (first 400 chars): {response[:400]}"
            ) from exc

        # 1. Hallucination Validator (Provenance check)
        input_names_lower = {n.lower() for n in batch}
        valid_assets_in_batch = []
        for entry in raw_assets:
            if not isinstance(entry, dict):
                continue
            canon = entry.get("canonical_name", "").strip()
            aliases = [a.strip() for a in entry.get("aliases", []) if a.strip()]

            # Verbatim containment check (case-insensitive)
            valid_aliases = [a for a in aliases if a.lower() in input_names_lower]
            if canon.lower() in input_names_lower:
                entry["aliases"] = valid_aliases
                valid_assets_in_batch.append(entry)
            elif valid_aliases:
                entry["canonical_name"] = valid_aliases[0]
                entry["aliases"] = valid_aliases[1:]
                valid_assets_in_batch.append(entry)

        # 2. Secondary Modality/Target Filter Call
        if valid_assets_in_batch:
            candidate_names = [e["canonical_name"] for e in valid_assets_in_batch]
            audit_prompt = (
                f"You are auditing a list of potential biotechnology drug/asset names.\n"
                f"For each name in the JSON array below, determine if it is a specific drug, biologic, or asset name (e.g., Zolbetuximab, Vyloy, TST001, AMG 910).\n"
                f"It is NOT a valid asset if it is:\n"
                f"  - A generic modality term (e.g., chemotherapy, immunotherapy, placebo, surgery, radiotherapy, standard of care)\n"
                f"  - A target protein or gene name (e.g., CLDN18.2, HER2, EGFR, Claudin-18.2)\n"
                f"  - A general combination description (e.g., chemotherapy combination, triplet therapy)\n\n"
                f"Candidate names: {json.dumps(candidate_names)}\n\n"
                f"Respond ONLY with a valid JSON object with exactly two keys:\n"
                f'  "valid_assets": [ ...names that are genuine specific asset names... ]\n'
                f'  "generic_or_modality": [ ...names that are generic terms/targets... ]\n'
                f"No explanation, no other text."
            )
            audit_system = (
                "You are an expert biotech asset auditor. Output only valid JSON. "
                "Classify any target proteins (like HER2, CLDN18.2, EGFR) or generic classes "
                "(like chemotherapy, immunotherapy) as 'generic_or_modality'."
            )
            try:
                try:
                    audit_response = client.query(
                        audit_prompt, audit_system, stream=False
                    )
                except TypeError as e:
                    if "unexpected keyword argument" in str(e) and "stream" in str(e):
                        audit_response = client.query(audit_prompt, audit_system)
                    else:
                        raise
                clean_audit = audit_response.strip()
                if clean_audit.startswith("```"):
                    clean_audit = re.sub(r"^```[a-z]*\n?", "", clean_audit)
                    clean_audit = re.sub(r"\n?```$", "", clean_audit.strip())
                audit_result = json.loads(clean_audit)
                if (
                    "valid_assets" in audit_result
                    or "generic_or_modality" in audit_result
                ):
                    valid_set = {
                        n.lower() for n in audit_result.get("valid_assets", [])
                    }
                else:
                    print(
                        "Warning: Secondary LLM modality audit response did not match expected schema. Keeping all candidates."
                    )
                    valid_set = {n.lower() for n in candidate_names}
            except Exception as e:
                print(
                    f"Warning: Secondary LLM modality audit failed ({e}). Keeping all candidates."
                )
                valid_set = {n.lower() for n in candidate_names}

            # Keep only audited valid assets
            filtered_assets = []
            for entry in valid_assets_in_batch:
                if entry["canonical_name"].lower() in valid_set:
                    filtered_assets.append(entry)
                else:
                    print(
                        f"    ✗ Audited and removed generic term/target: {entry['canonical_name']}"
                    )
            valid_assets_in_batch = filtered_assets

        return valid_assets_in_batch, classified_background

    # We will submit batches to a ThreadPoolExecutor
    futures_map = {}
    batch_results = [None] * total_batches

    with ThreadPoolExecutor(max_workers=min(total_batches, 4)) as executor:
        for batch_idx in range(total_batches):
            batch = unique_names[batch_idx * batch_size : (batch_idx + 1) * batch_size]
            f = executor.submit(process_single_batch, batch_idx, batch)
            futures_map[f] = batch_idx

        for f in as_completed(futures_map):
            idx = futures_map[f]
            try:
                batch_results[idx] = f.result()
            except Exception:
                # Re-raise to crash loudly as per rules
                raise

    # Print logs sequentially by batch index to keep standard output clear and un-interleaved
    for batch_idx, result in enumerate(batch_results):
        if result is None:
            continue
        valid_assets_in_batch, classified_background = result
        print(
            f"  [Classifier] Batch {batch_idx + 1}/{total_batches}: "
            f"{len(valid_assets_in_batch)} asset(s), "
            f"{len(classified_background)} background agent(s)"
        )
        for entry in valid_assets_in_batch:
            print(
                f"    ✓ ASSET      : {entry['canonical_name']} (Aliases: {entry['aliases']})"
            )
        for name in classified_background:
            print(f"    ✗ background : {name}")

        all_assets.extend(valid_assets_in_batch)

    return all_assets

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

    with ThreadPoolExecutor(max_workers=min(total_batches, 8)) as executor:
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

    # Perform global synonym resolution if we have more than one asset
    if len(all_assets) > 1:
        all_assets = consolidate_synonyms_globally(
            assets=all_assets,
            target_name=target_name,
            target_synonyms=target_synonyms,
        )

    return all_assets


def consolidate_synonyms_globally(
    assets: list[dict],
    target_name: str,
    target_synonyms: list | None = None,
) -> AssetList:
    """
    Consolidate duplicate/synonym assets globally using the LLM.
    Guarantees no data loss of identified assets and applies a provenance check/hallucination filter.
    """
    if not assets or len(assets) <= 1:
        return AssetList(assets)

    synonyms = target_synonyms or []
    synonyms_str = ", ".join(synonyms) if synonyms else target_name

    # Prepare input list for LLM to keep the prompt clean and concise
    input_assets_json = json.dumps(
        [
            {
                "canonical_name": a["canonical_name"],
                "aliases": a.get("aliases", []),
                "modality": a.get("modality", "N/A"),
                "targets": a.get("targets", [target_name]),
            }
            for a in assets
        ],
        ensure_ascii=False,
    )

    prompt = (
        f"You are a biotech drug synonym consolidation expert.\n\n"
        f"Research target: {target_name}\n"
        f"Target synonyms: {synonyms_str}\n\n"
        f"Below is a list of pipeline assets that were identified. Some of these assets are synonyms, alternative names, or laboratory codes for the same drug/molecule "
        f"(for example, 'IMC002' and 'LM-302' are the same molecule; 'Zolbetuximab' and 'Vyloy' are the same molecule).\n\n"
        f"Your task is to merge any duplicate/synonym assets together under a single canonical name.\n"
        f"Keep the most standard/common name as the 'canonical_name', and list all other synonym names/codes in 'aliases'.\n"
        f"Make sure to preserve/aggregate the correct modality and targets.\n\n"
        f"Input assets:\n{input_assets_json}\n\n"
        f"Respond ONLY with a valid JSON object with the key:\n"
        f'  "consolidated_assets": a list of objects, one per consolidated asset, with the keys:\n'
        f'     "canonical_name": string (most standard/common name)\n'
        f'     "aliases": list of strings (all other synonym names/codes for this asset)\n'
        f'     "modality": string (e.g. "Monoclonal Antibody", "ADC", "Small Molecule")\n'
        f'     "targets": list of strings\n\n'
        f"Every canonical name and alias in the input assets MUST be accounted for. Do not drop any valid asset. No explanations, no markdown fencing."
    )

    system_instruction = (
        "You are an expert biotech asset consolidator. Output only valid JSON. "
        "Consolidate multiple names/codes of the same drug/molecule into a single asset. "
        "Do not invent any new names not present in the input. Keep all valid assets."
    )

    client = LLMClient()
    try:
        try:
            response = client.query(prompt, system_instruction, stream=False)
        except TypeError as e:
            if "unexpected keyword argument" in str(e) and "stream" in str(e):
                response = client.query(prompt, system_instruction)
            else:
                raise
    except Exception as e:
        print(
            f"Warning: Global synonym consolidation LLM call failed ({e}). Returning unconsolidated list."
        )
        return AssetList(assets)

    if (
        not response
        or response.startswith("Error:")
        or response.startswith("Failed to call")
    ):
        print(
            f"Warning: Global synonym consolidation LLM call failed. Response: {response}. Returning unconsolidated list."
        )
        return AssetList(assets)

    # Strip markdown code fences if the LLM wrapped the output
    clean_response = response.strip()
    if clean_response.startswith("```"):
        clean_response = re.sub(r"^```[a-z]*\n?", "", clean_response)
        clean_response = re.sub(r"\n?```$", "", clean_response.strip())

    try:
        result = json.loads(clean_response)
        raw_consolidated = result.get("consolidated_assets", [])
    except Exception as exc:
        print(
            f"Warning: Failed to parse global consolidation JSON ({exc}). Returning unconsolidated list."
        )
        return AssetList(assets)

    # 1. Track all valid input names to build a safe set for provenance check
    input_names_lower = set()
    for entry in assets:
        input_names_lower.add(entry["canonical_name"].lower())
        for a in entry.get("aliases", []):
            input_names_lower.add(a.lower())

    # Build a lookup map of original input assets to recover any fields if needed
    name_to_original_asset = {}
    for entry in assets:
        name_to_original_asset[entry["canonical_name"].lower()] = entry
        for a in entry.get("aliases", []):
            name_to_original_asset[a.lower()] = entry

    # 2. Hallucination Validator (Provenance check)
    validated_assets = []
    covered_names_lower = set()

    for entry in raw_consolidated:
        if not isinstance(entry, dict):
            continue
        canon = entry.get("canonical_name", "").strip()
        aliases = [a.strip() for a in entry.get("aliases", []) if a.strip()]

        # Filter aliases to only those in the original inputs
        valid_aliases = [a for a in aliases if a.lower() in input_names_lower]

        if canon.lower() in input_names_lower:
            entry["aliases"] = valid_aliases
            validated_assets.append(entry)
            covered_names_lower.add(canon.lower())
            for a in valid_aliases:
                covered_names_lower.add(a.lower())
        elif valid_aliases:
            entry["canonical_name"] = valid_aliases[0]
            entry["aliases"] = valid_aliases[1:]
            validated_assets.append(entry)
            covered_names_lower.add(valid_aliases[0].lower())
            for a in valid_aliases[1:]:
                covered_names_lower.add(a.lower())

    # 3. Prevent Data Loss: Add back any input assets that were not covered by the LLM
    for entry in assets:
        canon_lower = entry["canonical_name"].lower()
        if canon_lower not in covered_names_lower:
            # Check if any of its aliases are covered. If not, add the whole asset entry back.
            aliases_lower = {a.lower() for a in entry.get("aliases", [])}
            if not aliases_lower.intersection(covered_names_lower):
                validated_assets.append(entry)
                covered_names_lower.add(canon_lower)
                for a in entry.get("aliases", []):
                    covered_names_lower.add(a.lower())

    # Re-wrap in AssetList
    final_list = AssetList()
    for entry in validated_assets:
        canon_lower = entry["canonical_name"].lower()
        orig = name_to_original_asset.get(canon_lower, {})

        final_entry = {
            "canonical_name": entry["canonical_name"],
            "aliases": entry.get("aliases", []),
            "modality": entry.get("modality") or orig.get("modality", "N/A"),
            "targets": entry.get("targets") or orig.get("targets", [target_name]),
            "filtered_terms": orig.get("filtered_terms", []),
        }
        final_list.append(final_entry)

    print(
        f"  [Classifier] Globally consolidated from {len(assets)} down to {len(final_list)} unique asset(s)."
    )
    return final_list

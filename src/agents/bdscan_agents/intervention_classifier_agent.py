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
            "CRITICAL: An asset name MUST be a specific molecule name, brand name, or codename.\n"
            "Never classify general terms (like 'immunotherapy', 'chemotherapy', 'placebo'), "
            "other targets (like 'HER2', 'EGFR'), or target descriptions as an 'asset'.\n"
            "Novel investigational assets typically have alphanumeric codes "
            "(e.g. AMG910, SHR-A1904, AZD6422) or USAN/INN stems "
            "(-mab, -tib, -cept, -mig, -can, -bart) with a sponsor-specific prefix.\n"
            "CRITICAL CLEANING & COMBINATION RULES:\n"
            "1. Registry names may contain complex combination descriptions, Chinese pharmaceutical suffixes (like '注射液', '注射用'), or trailing clinical trial descriptions in parentheses. For such records, isolate and use the clean, target-specific base molecule name/codename (e.g. 'IBI343' or 'IMC002') as the 'canonical_name' of the asset, and list the original messy input string in 'aliases'. Do NOT include suffixes, trial descriptions, or combination partner therapies in the canonical name.\n"
            "2. If an input name lists combination therapies (e.g., 'IBI343,sintilimab,oxaliplatin,S-1', 'Zolbetuximab combined with mFOLFOX6'), identify the target-specific asset (e.g., 'IBI343' or 'Zolbetuximab') as the canonical name. Put the entire combination string in the asset's 'aliases'. This maps the combination trial records to the core investigational drug."
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
        "Do not invent any new names not present in the input. Keep all valid assets.\n"
        "CRITICAL CONSOLIDATION RULES:\n"
        "1. If some assets are combination regimens (e.g., 'IBI343,sintilimab...'), suffix-modified names (e.g. 'IMC002注射液'), or names with long parenthetical trial descriptions, consolidate them under the clean canonical drug name (e.g., 'IBI343' or 'IMC002').\n"
        "2. Put all combination regimens, suffix-modified names, and trial description strings in the consolidated asset's 'aliases'. Make sure all variants are merged so there is only one entry per molecule in the output list."
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

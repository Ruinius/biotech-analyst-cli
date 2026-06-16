import json
import re

from src.services.llm_client import LLMClient


def fallback_parse(query: str) -> dict:
    """Robust regex-based fallback to extract target, synonyms, and modality from query."""
    modalities = [
        "ADC",
        "Bispecific",
        "mAb",
        "CAR-T",
        "CAR T",
        "Small Molecule",
        "BsAb",
        "BiTE",
    ]
    found_modality = ""
    target = query.strip()

    # Try to find and extract modality
    for mod in modalities:
        pattern = re.compile(rf"\b{re.escape(mod)}\b", re.IGNORECASE)
        if pattern.search(target):
            found_modality = mod
            target = pattern.sub("", target).strip()
            break

    # Clean common indication / disease area suffixes
    indications = [
        "pancreatic cancer",
        "solid tumor",
        "solid tumors",
        "breast cancer",
        "lung cancer",
        "gastric cancer",
        "ovarian cancer",
        "colorectal cancer",
        "prostate cancer",
        "cancer",
        "tumor",
        "tumors",
    ]
    for ind in indications:
        pattern = re.compile(rf"\b{re.escape(ind)}\b", re.IGNORECASE)
        if pattern.search(target):
            target = pattern.sub("", target).strip()

    # Clean up multiple whitespace and outer punctuation
    target = re.sub(r"\s+", " ", target)
    target = target.strip(" .,-_")

    if not target:
        target = query.strip()

    # Generate English synonyms
    en_synonyms = [target]
    clean_no_dot_no_space = target.replace(".", "").replace(" ", "")
    if clean_no_dot_no_space and clean_no_dot_no_space not in en_synonyms:
        en_synonyms.append(clean_no_dot_no_space)

    clean_no_space = target.replace(" ", "")
    if clean_no_space and clean_no_space not in en_synonyms:
        en_synonyms.append(clean_no_space)

    # Add a version with hyphen if applicable
    if " " in target:
        hyphenated = target.replace(" ", "-")
        if hyphenated not in en_synonyms:
            en_synonyms.append(hyphenated)

    return {
        "target_name": target,
        "en_list": en_synonyms,
        "zh_list": [target],
        "modality": found_modality,
    }


def parse_query_via_llm(query: str) -> dict:
    """Use configured LLM to parse a query string, falling back to local parsing on failure."""
    client = LLMClient()

    system_instruction = (
        "You are an expert molecular biologist and biotech diligence analyst assistant. "
        "Your task is to parse a raw user biotech research query string and extract the target name, "
        "English synonyms, Mandarin synonyms, and modality constraint. Return ONLY a valid JSON object."
    )

    prompt = (
        f"Parse the following biotech research query into a structured JSON object:\n"
        f"Query: '{query}'\n\n"
        f"The JSON object must have exactly these keys (and no others):\n"
        f"1. 'target_name': The core biological target/pathway name (e.g. 'Claudin 18.2' or 'CLDN18.2' if the query is 'Claudin 18.2 pancreatic cancer'). It must be the clean target name and not include the modality or the disease/indication.\n"
        f"2. 'en_list': A list of English search synonyms/variants for global database queries (e.g. ['CLDN18.2', 'Claudin18.2', 'Claudin 18.2']). Do NOT include modality or disease details in synonyms unless they are synonymous names of the target. Limit to 2-4 key synonyms.\n"
        f"3. 'zh_list': A list of Mandarin/Chinese search synonyms/variants for Chinese databases (e.g. ['CLDN18.2', '克劳丁18.2', 'Claudin 18.2']). Limit to 2-4 key synonyms.\n"
        f"4. 'modality': The therapeutic modality if specified in the query (e.g. 'ADC', 'mAb', 'Bispecific', 'CAR-T', 'Small Molecule'). If none is specified, set to empty string.\n\n"
        f"Ensure you return ONLY valid JSON. No markdown backticks, no outer text, no conversational elements, just raw JSON."
    )

    response = client.query(prompt, system_instruction)

    if (
        not response
        or response.startswith("Error:")
        or response.startswith("Failed to call")
    ):
        return fallback_parse(query)

    cleaned = response.strip()
    # Clean markdown block if LLM returned it
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        # Verify required keys
        required_keys = {"target_name", "en_list", "zh_list", "modality"}
        if required_keys.issubset(data.keys()):
            # Ensure synonyms are list of strings
            data["en_list"] = [str(x) for x in data["en_list"]]
            data["zh_list"] = [str(x) for x in data["zh_list"]]
            data["modality"] = str(data["modality"])
            return data
    except Exception:
        pass

    return fallback_parse(query)

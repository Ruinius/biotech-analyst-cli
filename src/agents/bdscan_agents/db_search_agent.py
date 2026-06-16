import datetime
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from src.core.config import Settings
from src.services.llm_client import LLMClient
from src.utils import formatting


def run_cmd(cmd_args: list[str]) -> tuple[bool, str, str]:
    """Execute a python subprocess with absolute Windows compatibility."""
    my_env = os.environ.copy()
    my_env["PYTHONIOENCODING"] = "utf-8"
    try:
        res = subprocess.run(
            [sys.executable] + cmd_args,
            env=my_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return res.returncode == 0, res.stdout, res.stderr
    except Exception as e:
        return False, "", str(e)


# Tool Functions
def search_clinicaltrials(folder_safe_name: str, term: str, limit: int = 50) -> str:
    term_clean = term.replace(" ", "_").replace(".", "")
    out_file = f"tmp/{folder_safe_name}_ct_{term_clean}.json"
    sum_file = out_file.replace(".json", "_sum.txt")

    success, out, err = run_cmd(
        [
            "src/utils/fetch_clinicaltrials.py",
            "--terms",
            term,
            "--output",
            out_file,
            "--limit",
            str(limit),
        ]
    )
    if not success or not os.path.exists(out_file):
        return f"Error executing ClinicalTrials.gov fetch for '{term}': {err or out}"

    # Summarize
    success_sum, out_sum, err_sum = run_cmd(
        [
            "src/utils/summarize_clinicaltrials.py",
            "--input",
            out_file,
            "--output",
            sum_file,
        ]
    )
    if not success_sum or not os.path.exists(sum_file):
        return (
            f"Error summarizing ClinicalTrials.gov for '{term}': {err_sum or out_sum}"
        )

    with open(sum_file, encoding="utf-8") as f:
        summary_text = f.read()

    return f"Success. Saved raw data to {out_file}.\nSummary Preview:\n{summary_text[:3000]}"


def search_anzctr_ctis(folder_safe_name: str, term: str, limit: int = 50) -> str:
    term_clean = term.replace(" ", "_").replace(".", "")
    out_file = f"tmp/{folder_safe_name}_anzctr_{term_clean}.json"
    sum_file = out_file.replace(".json", "_sum.txt")

    success, out, err = run_cmd(
        [
            "src/utils/fetch_anzctr_ctis.py",
            "--term",
            term,
            "--output",
            out_file,
            "--limit",
            str(limit),
        ]
    )
    if not success or not os.path.exists(out_file):
        return f"Error executing ANZCTR/CTIS fetch for '{term}': {err or out}"

    # Summarize
    success_sum, out_sum, err_sum = run_cmd(
        [
            "src/utils/summarize_anzctr_ctis.py",
            "--input",
            out_file,
            "--output",
            sum_file,
        ]
    )
    if not success_sum or not os.path.exists(sum_file):
        return f"Error summarizing ANZCTR/CTIS for '{term}': {err_sum or out_sum}"

    with open(sum_file, encoding="utf-8") as f:
        summary_text = f.read()

    return f"Success. Saved raw data to {out_file}.\nSummary Preview:\n{summary_text[:3000]}"


def search_conferences(folder_safe_name: str, term: str, limit: int = 50) -> str:
    term_clean = term.replace(" ", "_").replace(".", "")
    out_file = f"tmp/{folder_safe_name}_conf_{term_clean}.json"
    sum_file = out_file.replace(".json", "_sum.txt")

    success, out, err = run_cmd(
        [
            "src/utils/fetch_conferences.py",
            "--term",
            term,
            "--output",
            out_file,
            "--limit",
            str(limit),
        ]
    )
    if not success or not os.path.exists(out_file):
        return f"Error executing Conference abstract fetch for '{term}': {err or out}"

    # Summarize
    success_sum, out_sum, err_sum = run_cmd(
        [
            "src/utils/summarize_conferences.py",
            "--input",
            out_file,
            "--output",
            sum_file,
        ]
    )
    if not success_sum or not os.path.exists(sum_file):
        return (
            f"Error summarizing Conference abstracts for '{term}': {err_sum or out_sum}"
        )

    with open(sum_file, encoding="utf-8") as f:
        summary_text = f.read()

    return f"Success. Saved raw data to {out_file}.\nSummary Preview:\n{summary_text[:3000]}"


def search_chinese_registries(folder_safe_name: str, term: str, limit: int = 50) -> str:
    term_clean = term.replace(" ", "_").replace(".", "")
    out_file = f"tmp/{folder_safe_name}_chreg_{term_clean}.json"
    sum_file = out_file.replace(".json", "_sum.txt")

    success, out, err = run_cmd(
        [
            "src/utils/fetch_chinese_registries.py",
            "--term",
            term,
            "--output",
            out_file,
            "--limit",
            str(limit),
        ]
    )
    if not success or not os.path.exists(out_file):
        return f"Error executing Chinese Registries fetch for '{term}': {err or out}"

    # Summarize
    success_sum, out_sum, err_sum = run_cmd(
        [
            "src/utils/summarize_chinese_registries.py",
            "--input",
            out_file,
            "--output",
            sum_file,
        ]
    )
    if not success_sum or not os.path.exists(sum_file):
        return (
            f"Error summarizing Chinese Registries for '{term}': {err_sum or out_sum}"
        )

    with open(sum_file, encoding="utf-8") as f:
        summary_text = f.read()

    return f"Success. Saved raw data to {out_file}.\nSummary Preview:\n{summary_text[:3000]}"


def search_china_direct(folder_safe_name: str, term: str) -> str:
    term_clean = term.replace(" ", "_").replace(".", "")
    out_file = f"tmp/{folder_safe_name}_cdirect_{term_clean}.json"
    sum_file = out_file.replace(".json", "_sum.txt")

    # Direct search on NMPA CDE (requires chromium playwrigth installed)
    success, out, err = run_cmd(
        ["src/utils/fetch_china_direct.py", "--term", term, "--output", out_file]
    )
    if not success or not os.path.exists(out_file):
        return f"Error executing CDE Playwright scrape for '{term}': {err or out}"

    # Summarize
    success_sum, out_sum, err_sum = run_cmd(
        [
            "src/utils/summarize_china_direct.py",
            "--input",
            out_file,
            "--output",
            sum_file,
        ]
    )
    if not success_sum or not os.path.exists(sum_file):
        return f"Error summarizing CDE for '{term}': {err_sum or out_sum}"

    with open(sum_file, encoding="utf-8") as f:
        summary_text = f.read()

    return f"Success. Saved raw data to {out_file}.\nSummary Preview:\n{summary_text[:3000]}"


def search_ip_lens(folder_safe_name: str, term: str, limit: int = 50) -> str:
    term_clean = term.replace(" ", "_").replace(".", "")
    out_file = f"tmp/{folder_safe_name}_lens_{term_clean}.json"
    sum_file = out_file.replace(".json", "_sum.txt")

    success, out, err = run_cmd(
        [
            "src/utils/fetch_ip_lens.py",
            "--term",
            term,
            "--output",
            out_file,
            "--limit",
            str(limit),
        ]
    )
    if not success or not os.path.exists(out_file):
        return f"Error executing Lens.org IP fetch for '{term}': {err or out}"

    # Summarize
    success_sum, out_sum, err_sum = run_cmd(
        ["src/utils/summarize_ip_lens.py", "--input", out_file, "--output", sum_file]
    )
    if not success_sum or not os.path.exists(sum_file):
        return f"Error summarizing Lens.org IP for '{term}': {err_sum or out_sum}"

    with open(sum_file, encoding="utf-8") as f:
        summary_text = f.read()

    return f"Success. Saved raw data to {out_file}.\nSummary Preview:\n{summary_text[:3000]}"


def search_pubchem(folder_safe_name: str, term: str) -> str:
    term_clean = term.replace(" ", "_").replace(".", "")
    out_file = f"tmp/{folder_safe_name}_pubchem_{term_clean}.json"
    sum_file = out_file.replace(".json", "_sum.txt")

    success, out, err = run_cmd(
        ["src/utils/fetch_pubchem.py", "--compound", term, "--output", out_file]
    )
    if not success or not os.path.exists(out_file):
        return f"Error executing PubChem fetch for '{term}': {err or out}"

    # Summarize
    success_sum, out_sum, err_sum = run_cmd(
        ["src/utils/summarize_pubchem.py", "--input", out_file, "--output", sum_file]
    )
    if not success_sum or not os.path.exists(sum_file):
        return f"Error summarizing PubChem for '{term}': {err_sum or out_sum}"

    with open(sum_file, encoding="utf-8") as f:
        summary_text = f.read()

    return f"Success. Saved raw data to {out_file}.\nSummary Preview:\n{summary_text[:3000]}"


def search_openfda(folder_safe_name: str, term: str) -> str:
    term_clean = term.replace(" ", "_").replace(".", "")
    out_file = f"tmp/{folder_safe_name}_openfda_{term_clean}.json"
    sum_file = out_file.replace(".json", "_sum.txt")

    success, out, err = run_cmd(
        ["src/utils/fetch_openfda.py", "--drug", term, "--output", out_file]
    )
    if not success or not os.path.exists(out_file):
        return f"Error executing openFDA fetch for '{term}': {err or out}"

    # Summarize
    success_sum, out_sum, err_sum = run_cmd(
        ["src/utils/summarize_openfda.py", "--input", out_file, "--output", sum_file]
    )
    if not success_sum or not os.path.exists(sum_file):
        return f"Error summarizing openFDA for '{term}': {err_sum or out_sum}"

    with open(sum_file, encoding="utf-8") as f:
        summary_text = f.read()

    return f"Success. Saved raw data to {out_file}.\nSummary Preview:\n{summary_text[:3000]}"


class DatabaseSearchAgent:
    """Agent executing 4-turn state search loop sequentially for each of the eight databases."""

    def __init__(self, settings: Settings, folder_safe_name: str, target_dir: Path):
        self.settings = settings
        self.folder_safe_name = folder_safe_name
        self.target_dir = target_dir
        self.client = LLMClient()
        self.logs = []

    def execute_search_pipeline(
        self,
        target_name: str,
        en_list: list[str],
        zh_list: list[str],
        modality: str = "",
    ):
        sources = [
            ("ClinicalTrials.gov", "search_clinicaltrials", en_list),
            ("EU CTIS & Australian ANZCTR", "search_anzctr_ctis", en_list),
            ("Major Conferences", "search_conferences", en_list),
            ("Chinese WHO Registries", "search_chinese_registries", zh_list),
            ("NMPA CDE Direct Search", "search_china_direct", zh_list),
            ("Global Patents & IP (Lens.org)", "search_ip_lens", en_list),
            ("PubChem BioAssays", "search_pubchem", en_list),
            ("openFDA Briefings", "search_openfda", en_list),
        ]

        os.makedirs("tmp", exist_ok=True)
        research_dir = self.target_dir / "research"
        research_dir.mkdir(parents=True, exist_ok=True)

        for idx, (source_name, tool_name, synonyms) in enumerate(sources, 1):
            formatting.print_info(
                f"[{idx}/8] Commencing search sweep for source: {source_name}..."
            )
            self.run_loop_for_source(
                idx, source_name, tool_name, synonyms, target_name, modality
            )

        # Run deterministic merging after completing all sweeps
        self.deterministic_merge()

    def run_loop_for_source(
        self,
        idx: int,
        source_name: str,
        tool_name: str,
        synonyms: list[str],
        target_name: str,
        modality: str,
    ):
        history = []
        turn_budget = 4
        source_log_lines = []

        system_instruction = (
            f"You are Dr. Hops' Database Search Agent specialized in '{source_name}'.\n"
            "Your objective is to find trials, products, and preclinical/clinical info "
            f"for the pathway '{target_name}'.\n"
            "You have a budget of up to 4 turns.\n"
            "In each turn, you can call the tool once using this exact syntax:\n"
            f'[TOOL_CALL: {tool_name}(term="synonym_here")]\n'
            "Or with limit if supported (e.g. limit=50).\n"
            "Once you have sufficient results, or on Turn 4, write a comprehensive Markdown summary "
            "reviewing the findings and end your response with the [FINALIZE] tag.\n"
            "Do NOT hallucinate study IDs or names."
        )

        current_term_index = 0

        for turn in range(1, turn_budget + 1):
            formatting.print_info(f"  Turn {turn}/{turn_budget} for {source_name}...")

            # Compile prompt
            prompt = (
                f"We are researching target: '{target_name}' using '{source_name}'.\n"
                f"Available synonyms: {', '.join(synonyms)}\n"
                f"Target Modality constraints: {modality if modality else 'None'}\n\n"
                f"Turn {turn} details:\n"
            )
            if turn == 1:
                prompt += f"Please invoke the tool '{tool_name}' using one of the primary synonyms to fetch initial data."
            else:
                prompt += (
                    "Review the search results below. If there are gaps or spelling variations, run another search. "
                    "Otherwise, compile a structured research log and output [FINALIZE]."
                )

            # Invoke LLM
            full_prompt = prompt + "\n\nHistory:\n" + "\n".join(history)
            response = self.client.query(full_prompt, system_instruction)

            # Track history
            history.append(f"User: {prompt}")
            history.append(f"Agent: {response}")
            source_log_lines.append(f"Turn {turn} Response:\n{response}")

            # Parse tool call
            tool_match = re.search(
                r"\[TOOL_CALL:\s*([a-zA-Z_0-9]+)\((.*?)\)\]", response
            )
            if tool_match:
                called_tool = tool_match.group(1)
                args_str = tool_match.group(2)
                # Parse arguments
                args = {}
                for kv in re.findall(r"([a-zA-Z_0-9]+)\s*=\s*\"(.*?)\"", args_str):
                    args[kv[0]] = kv[1]
                for kv in re.findall(r"([a-zA-Z_0-9]+)\s*=\s*([0-9]+)", args_str):
                    args[kv[0]] = int(kv[1])

                term_to_search = args.get("term") or (
                    synonyms[current_term_index]
                    if current_term_index < len(synonyms)
                    else target_name
                )
                limit = args.get("limit") or 50

                formatting.print_info(
                    f"    Executing tool {called_tool} for '{term_to_search}'..."
                )

                # Run tool
                if called_tool == "search_clinicaltrials":
                    result = search_clinicaltrials(
                        self.folder_safe_name, term_to_search, limit
                    )
                elif called_tool == "search_anzctr_ctis":
                    result = search_anzctr_ctis(
                        self.folder_safe_name, term_to_search, limit
                    )
                elif called_tool == "search_conferences":
                    result = search_conferences(
                        self.folder_safe_name, term_to_search, limit
                    )
                elif called_tool == "search_chinese_registries":
                    result = search_chinese_registries(
                        self.folder_safe_name, term_to_search, limit
                    )
                elif called_tool == "search_china_direct":
                    result = search_china_direct(self.folder_safe_name, term_to_search)
                elif called_tool == "search_ip_lens":
                    result = search_ip_lens(
                        self.folder_safe_name, term_to_search, limit
                    )
                elif called_tool == "search_pubchem":
                    result = search_pubchem(self.folder_safe_name, term_to_search)
                elif called_tool == "search_openfda":
                    result = search_openfda(self.folder_safe_name, term_to_search)
                else:
                    result = f"Error: Tool '{called_tool}' is not recognized."

                history.append(f"System Tool Result: {result}")
                current_term_index += 1
            else:
                # No tool call, did the agent finalize?
                if "[FINALIZE]" in response or turn == turn_budget:
                    # Compile final log
                    log_file = (
                        self.target_dir
                        / "research"
                        / f"research_log_0{idx}_{tool_name.replace('search_', '')}.md"
                    )
                    clean_md = response.replace("[FINALIZE]", "").strip()
                    log_header = (
                        f"# Research Log {idx}: {source_name} Sourcing\n"
                        f"**Date Accessed**: {datetime.date.today().strftime('%Y-%m-%d')}\n"
                        f"**Analyst**: Senior Biotech BD Analyst\n"
                        f"**Source**: {source_name}\n"
                        f"**Target Pathway**: {target_name}\n\n"
                        "---\n\n"
                    )
                    log_file.write_text(log_header + clean_md, encoding="utf-8")
                    formatting.print_success(f"    Saved research log to {log_file}")
                    self.logs.append(
                        {
                            "source": source_name,
                            "log_file": str(log_file),
                            "summary": clean_md[:200],
                        }
                    )
                    break

    def deterministic_merge(self):
        """Deterministic de-duplication and merging of Clinical Trials and CDE Scrapes."""
        formatting.speak(
            "Ribosomes active! Commencing deterministic append/de-duplicate merging schedules..."
        )

        merged_ct_file = f"tmp/{self.folder_safe_name}_clinicaltrials.json"
        merged_china_file = f"tmp/{self.folder_safe_name}_china_direct.json"

        # 1. Merge Clinical Trials (ClinicalTrials.gov + ANZCTR/CTIS)
        merged_trials = {}
        # ClinicalTrials
        for f_path in glob.glob(f"tmp/{self.folder_safe_name}_ct_*.json"):
            try:
                with open(f_path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for nct, study in data.items():
                        merged_trials[nct] = study
            except Exception:
                pass

        # ANZCTR / CTIS
        for f_path in glob.glob(f"tmp/{self.folder_safe_name}_anzctr_*.json"):
            try:
                with open(f_path, encoding="utf-8") as f:
                    data = json.load(f)
                # ANZCTR holds results in results list
                trials_list = data.get("results", [])
                for study in trials_list:
                    # Get NCT ID or registration ID
                    nct_id = None
                    # Search cross references or try to extract from title
                    title = study.get("title", "")
                    nct_match = re.search(r"\bNCT\d{8}\b", title)
                    if nct_match:
                        nct_id = nct_match.group(0)
                    else:
                        # Fallback to e.g. EudraCT or registration number
                        cross_refs = study.get("dbCrossReferenceList", {}).get(
                            "dbName", []
                        )
                        for word in title.split() + cross_refs:
                            if "NCT" in word:
                                nct_id = word.strip(".,()[]")
                                break
                    if not nct_id:
                        nct_id = study.get("id") or study.get("pmid")

                    if nct_id:
                        # Standardize into a protocolSection structure similar to clinicaltrials.gov
                        # if it's missing, so landscape table generator doesn't crash
                        merged_trials[nct_id] = {
                            "protocolSection": {
                                "identificationModule": {
                                    "briefTitle": study.get("title", "N/A"),
                                    "officialTitle": study.get("title", "N/A"),
                                    "nctId": nct_id,
                                },
                                "statusModule": {
                                    "overallStatus": "Completed"
                                    if study.get("pubYear")
                                    else "Recruiting"
                                },
                                "sponsorCollaboratorsModule": {
                                    "leadSponsor": {
                                        "name": study.get("authorString", "N/A")
                                    }
                                },
                                "designModule": {
                                    "phases": ["Phase 2"]  # Default phase fallback
                                },
                                "armsInterventionsModule": {
                                    "interventions": [
                                        {
                                            "name": study.get(
                                                "meshHeadingList", {}
                                            ).get("descriptorName", ["N/A"])[0]
                                            if study.get("meshHeadingList")
                                            else "N/A"
                                        }
                                    ]
                                },
                            }
                        }
            except Exception:
                pass

        with open(merged_ct_file, "w", encoding="utf-8") as f:
            json.dump(merged_trials, f, indent=2, ensure_ascii=False)
        formatting.print_success(
            f"Merged {len(merged_trials)} clinical trial records to {merged_ct_file}"
        )

        # 2. Merge China Direct CDE Scrapes
        merged_china = []
        for f_path in glob.glob(f"tmp/{self.folder_safe_name}_cdirect_*.json"):
            try:
                with open(f_path, encoding="utf-8") as f:
                    data = json.load(f)
                merged_china.extend(data.get("records", []))
            except Exception:
                pass

        # Deduplicate by acceptance_number
        unique_china = {}
        for rec in merged_china:
            acc_num = rec.get("acceptance_number")
            if acc_num:
                unique_china[acc_num] = rec

        with open(merged_china_file, "w", encoding="utf-8") as f:
            json.dump(
                {"records": list(unique_china.values())},
                f,
                indent=2,
                ensure_ascii=False,
            )
        formatting.print_success(
            f"Merged {len(unique_china)} direct CDE records to {merged_china_file}"
        )

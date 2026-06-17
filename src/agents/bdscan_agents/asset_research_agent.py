import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ddgs import DDGS

from src.core.config import Settings
from src.services.llm_client import LLMClient
from src.utils import formatting
from src.utils.landscape.table_formatters import (
    normalize_drug_name,
    parse_asset_and_aliases,
)


def clean_cell_to_name(cell: str, config: dict | None = None) -> str:
    primary, aliases = parse_asset_and_aliases(cell)
    if not config:
        return primary

    candidates = [primary] + aliases
    for canon, details in config.items():
        all_names = [canon] + details.get("aliases", [])
        all_names_lower = {n.lower() for n in all_names}
        if any(c.lower() in all_names_lower for c in candidates):
            return canon
    return primary


def extract_names_from_cell(cell: str, config: dict | None = None) -> list[str]:
    primary, aliases = parse_asset_and_aliases(cell)
    if not config:
        return [primary] + aliases

    candidates = [primary] + aliases
    for canon, details in config.items():
        all_names = [canon] + details.get("aliases", [])
        all_names_lower = {n.lower() for n in all_names}
        if any(c.lower() in all_names_lower for c in candidates):
            return [canon] + details.get("aliases", [])
    return [primary] + aliases


def update_table_row(
    table_path: Path,
    asset_name: str,
    safety: str,
    efficacy: str,
    licensing: str,
    milestones: str,
    citations: str,
    config: dict | None = None,
):
    """Write back the researched details directly to the landscape table in research/."""
    if not table_path.exists():
        return

    content = table_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    col_indices = {}
    header_idx = -1
    for idx, line in enumerate(lines):
        if "|" in line and "Asset Name" in line:
            header_idx = idx
            cols = [c.strip() for c in line.split("|")]
            for col_num, col_name in enumerate(cols):
                if col_name:
                    col_indices[col_name] = col_num
            break

    if header_idx == -1:
        asset_idx = 1
        safety_idx = 12
        efficacy_idx = 13
        licensing_idx = 14
        milestones_idx = 15
        citations_idx = 16
    else:
        asset_idx = col_indices.get("Asset Name", 1)
        safety_idx = col_indices.get("Web Selectivity & Safety Profile", 12)
        efficacy_idx = col_indices.get("Web Key Efficacy Data", 13)
        licensing_idx = col_indices.get("Web Licensing Status & Partners", 14)
        milestones_idx = col_indices.get("Web Upcoming Milestones", 15)
        citations_idx = col_indices.get("Web Citations / Sources", 16)

    for idx, line in enumerate(lines):
        if not line.strip() or idx <= header_idx + 1:
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) <= max(
            asset_idx,
            safety_idx,
            efficacy_idx,
            licensing_idx,
            milestones_idx,
            citations_idx,
        ):
            continue

        name_cell = cols[asset_idx]
        cleaned_name = clean_cell_to_name(name_cell, config)
        if cleaned_name.lower() == asset_name.lower():
            cols[safety_idx] = safety.replace("\n", " ").replace("|", "\\|")
            cols[efficacy_idx] = efficacy.replace("\n", " ").replace("|", "\\|")
            cols[licensing_idx] = licensing.replace("\n", " ").replace("|", "\\|")
            cols[milestones_idx] = milestones.replace("\n", " ").replace("|", "\\|")
            cols[citations_idx] = citations.replace("\n", " ").replace("|", "\\|")
            lines[idx] = "| " + " | ".join(cols[1:-1]) + " |"
            break

    table_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sanitize_search_query(query: str, max_length: int = 200) -> str:
    """Sanitize and cap search query string to prevent errors or runaway loops."""
    # Replace newlines, tabs, carriage returns with spaces
    query = re.sub(r"[\r\n\t]+", " ", query)

    # Replace multiple spaces with a single space
    query = re.sub(r"\s+", " ", query)

    # Strip quotes (both single and double) that might be wrapping or cluttering the query
    query = query.strip().strip("\"'").strip()

    # Clean up consecutive duplicate words (case-insensitive)
    query = re.sub(r"\b(\w+)(?:\s+\1\b)+", r"\1", query, flags=re.IGNORECASE)

    # Cap the query length
    if len(query) > max_length:
        truncated = query[:max_length]
        # Try to truncate at a word boundary
        split_query = truncated.rsplit(" ", 1)
        if len(split_query) > 1 and split_query[0]:
            query = split_query[0]
        else:
            query = truncated

    return query.strip()


def web_search(query: str) -> str:
    """Query DuckDuckGo for clinical news and pipeline updates."""
    try:
        results = []
        with DDGS() as ddgs:
            ddgs_generator = ddgs.text(query, max_results=5)
            if ddgs_generator:
                for r in ddgs_generator:
                    results.append(
                        f"Title: {r.get('title')}\nURL: {r.get('href')}\nSnippet: {r.get('body')}\n---"
                    )
        if not results:
            return "No web search results found."
        return "\n".join(results)
    except Exception as e:
        return f"Error executing DuckDuckGo search: {str(e)}"


class AssetResearchAgent:
    """Agent executing 4-turn web research loop concurrently for each asset in the master table."""

    def __init__(self, settings: Settings, target_dir: Path):
        self.settings = settings
        self.target_dir = target_dir
        self.client = LLMClient()
        self.aliases_map = {}
        self.asset_config = {}
        self._registry_lock = threading.RLock()
        self._claimed_assets = {}  # normalized_alias -> canonical_name
        self._merge_queue = []  # list of (canonical_name, other_canonical_name)
        self._pre_detected_duplicates = []  # list of (raw_name, duplicate_parent)
        self.learning_filepath = Path(__file__).parent.parent / "learning.md"
        config_path = self.target_dir / "database_json" / "asset_config.json"
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    self.asset_config = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load asset_config.json: {e}")

    def research_all_assets(self) -> Path:
        table_path = self.target_dir / "research" / "landscape_table.md"
        if not table_path.exists():
            raise FileNotFoundError(f"Master landscape table not found at {table_path}")

        formatting.print_info(
            "Starting concurrent web diligence research loops for all assets..."
        )

        # Parse table rows to get assets
        content = table_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        rows_to_process = []
        for idx, line in enumerate(lines):
            if not line.strip() or idx < 2:
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) < 3:
                continue
            rows_to_process.append((idx, cols))

        processed_count = 0
        web_search_dir = self.target_dir / "web_search"
        web_search_dir.mkdir(parents=True, exist_ok=True)

        def research_single_row(idx, cols):
            name_cell = cols[2]
            primary_name = clean_cell_to_name(name_cell, self.asset_config)
            all_synonyms = extract_names_from_cell(name_cell, self.asset_config)

            with self._registry_lock:
                # Check if any of this asset's aliases are already claimed
                duplicate_parent = None
                for syn in all_synonyms:
                    key = normalize_drug_name(syn)
                    if key in self._claimed_assets:
                        duplicate_parent = self._claimed_assets[key]
                        break

                if duplicate_parent:
                    formatting.print_warning(
                        f"Duplicate asset detected: '{primary_name}' maps to already-researched parent '{duplicate_parent}'."
                    )
                    # Skip search, queue for post-research duplicate link mapping
                    raw_name = clean_cell_to_name(name_cell, config=None)
                    self._pre_detected_duplicates.append((raw_name, duplicate_parent))
                    return False

                # Record aliases to prevent duplicate searches later
                for syn in all_synonyms:
                    self._claimed_assets[normalize_drug_name(syn)] = primary_name

            # Run 4-turn loop for this new asset
            formatting.print_info(
                f"Researching asset: {primary_name} ({cols[3] if len(cols) > 3 else 'N/A'})..."
            )
            self.run_loop_for_asset(table_path, primary_name, cols)
            return True

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(research_single_row, idx, cols)
                for idx, cols in rows_to_process
            ]
            for future in as_completed(futures):
                try:
                    was_researched = future.result()
                    if was_researched:
                        processed_count += 1
                except Exception as e:
                    formatting.print_warning(f"Error researching asset: {e}")

        # Post-research merge
        with self._registry_lock:
            for raw_name, duplicate_parent in self._pre_detected_duplicates:
                formatting.print_info(
                    f"Linking duplicate asset: {raw_name} -> {duplicate_parent}"
                )
                self.link_duplicate_asset(table_path, raw_name, duplicate_parent)

            for canonical_name, other in self._merge_queue:
                formatting.print_info(
                    f"Merging mid-research duplicates: {canonical_name} and {other}"
                )
                self.link_duplicate_asset(table_path, canonical_name, other)

        formatting.print_success(
            f"Completed web research for {processed_count} unique assets."
        )
        return table_path

    def link_duplicate_asset(
        self, table_path: Path, duplicate_name: str, parent_name: str
    ):
        """Find parent values and copy them to duplicate asset row."""
        with self._registry_lock:
            content = table_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            col_indices = {}
            header_idx = -1
            for idx, line in enumerate(lines):
                if "|" in line and "Asset Name" in line:
                    header_idx = idx
                    cols = [c.strip() for c in line.split("|")]
                    for col_num, col_name in enumerate(cols):
                        if col_name:
                            col_indices[col_name] = col_num
                    break

            if header_idx == -1:
                asset_idx = 1
                safety_idx = 12
                efficacy_idx = 13
                licensing_idx = 14
                milestones_idx = 15
                citations_idx = 16
            else:
                asset_idx = col_indices.get("Asset Name", 1)
                safety_idx = col_indices.get("Web Selectivity & Safety Profile", 12)
                efficacy_idx = col_indices.get("Web Key Efficacy Data", 13)
                licensing_idx = col_indices.get("Web Licensing Status & Partners", 14)
                milestones_idx = col_indices.get("Web Upcoming Milestones", 15)
                citations_idx = col_indices.get("Web Citations / Sources", 16)

            parent_safety = "Duplicate. Refer to parent."
            parent_efficacy = "Duplicate. Refer to parent."
            parent_licensing = "Duplicate. Refer to parent."
            parent_milestones = "Duplicate. Refer to parent."
            parent_citations = "N/A"

            for idx, line in enumerate(lines):
                if not line.strip() or idx <= header_idx + 1:
                    continue
                cols = [c.strip() for c in line.split("|")]
                if len(cols) <= max(
                    asset_idx,
                    safety_idx,
                    efficacy_idx,
                    licensing_idx,
                    milestones_idx,
                    citations_idx,
                ):
                    continue
                if (
                    clean_cell_to_name(cols[asset_idx], self.asset_config).lower()
                    == parent_name.lower()
                ):
                    parent_safety = cols[safety_idx]
                    parent_efficacy = cols[efficacy_idx]
                    parent_licensing = cols[licensing_idx]
                    parent_milestones = cols[milestones_idx]
                    parent_citations = cols[citations_idx]
                    break

            update_table_row(
                table_path=table_path,
                asset_name=duplicate_name,
                safety=parent_safety,
                efficacy=parent_efficacy,
                licensing=parent_licensing,
                milestones=parent_milestones,
                citations=parent_citations,
                config=None,
            )

    def register_alias_mid_research(self, canonical_name: str, new_alias: str):
        with self._registry_lock:
            key = normalize_drug_name(new_alias)
            if key in self._claimed_assets:
                other = self._claimed_assets[key]
                if other.lower() != canonical_name.lower():
                    # Collision: another worker is researching the same drug
                    # Current worker continues (already invested turns)
                    # but marks for post-research merge
                    self._merge_queue.append((canonical_name, other))
            else:
                self._claimed_assets[key] = canonical_name

    def _load_learnings(self, section: str) -> str:
        """Load specific section learnings from learning.md if it exists."""
        if not self.learning_filepath.exists():
            return ""
        try:
            content = self.learning_filepath.read_text(encoding="utf-8")
            lines = content.splitlines()
            section_header = f"## {section}"
            section_idx = -1
            for idx, line in enumerate(lines):
                if line.strip() == section_header:
                    section_idx = idx
                    break
            if section_idx == -1:
                return ""
            next_section_idx = len(lines)
            for idx in range(section_idx + 1, len(lines)):
                if lines[idx].strip().startswith("## "):
                    next_section_idx = idx
                    break
            sec_lines = lines[section_idx + 1 : next_section_idx]
            return "\n".join(sec_lines).strip()
        except Exception:
            return ""

    def run_loop_for_asset(self, table_path: Path, asset_name: str, cols: list[str]):
        history_turns = []
        turn_budget = 4
        table_updated = False

        sponsor = cols[3] if len(cols) > 3 else "N/A"
        modality = cols[4] if len(cols) > 4 else "N/A"
        phase = cols[7] if len(cols) > 7 else "N/A"
        trials = cols[8] if len(cols) > 8 else "N/A"

        # Load historical web-search learnings
        learnings = self._load_learnings("web-search")
        learnings_block = (
            f"\nApply these historical learnings and guidelines during your web search execution:\n{learnings}\n"
            if learnings
            else ""
        )

        system_instruction = (
            f"You are Dr. Hops' Asset Research Agent dilution scout for the candidate '{asset_name}'.\n"
            f"Developer: {sponsor}, Modality: {modality}, Phase: {phase}, Trial IDs: {trials}.\n"
            "Your objective is to find recent clinical data, selectivity profile details, licensing availability/partnerships, and upcoming milestones.\n"
            "For licensing availability, investigate if the asset is available for in-licensing: it is likely NOT available if the developer/sponsor is a big pharma company, or if they already have an existing US/EU regional licensing or partnership deal. Focus on identifying existing partners or in-licensing feasibility.\n"
            "You have a budget of up to 4 turns.\n"
            "Supported tools:\n"
            '- [TOOL_CALL: web_search(query="query_string")]\n'
            '- [TOOL_CALL: edit_landscape_table(safety="...", efficacy="...", licensing="...", milestones="...", citations="...")]\n'
            f"{learnings_block}"
            "When done or on Turn 4, write your final response ending with the [FINALIZE] tag.\n"
            "Always cite PMIDs, NCT links, press releases, or conference abstracts."
        )

        for turn in range(1, turn_budget + 1):
            if turn == turn_budget:
                current_instructions = (
                    "CRITICAL: This is your LAST turn (Turn Budget Exhausted). You MUST call the edit_landscape_table tool "
                    "now with all qualitative safety, efficacy, licensing, and milestone information you have found so far, and output [FINALIZE] "
                    "in your response to save your work. If you do not call edit_landscape_table now, your research will be lost."
                )
            elif turn == 1:
                current_instructions = f"Please run an initial web_search to find selectivity, safety, licensing/partnership status, and clinical milestones for {asset_name}."
            else:
                current_instructions = (
                    "Review the search results. If you have sufficient qualitative safety, efficacy, licensing, and milestone information, "
                    "call the edit_landscape_table tool to update the table, and output [FINALIZE]. Otherwise, run another search."
                )

            # Construct prompt using XML tags to avoid LLM transcript-completion loops
            prompt_parts = [
                f"We are conducting due diligence on '{asset_name}' developed by '{sponsor}'."
            ]
            if history_turns:
                prompt_parts.append("<conversation_history>")
                for h_turn in history_turns:
                    prompt_parts.append(f'  <turn number="{h_turn["number"]}">')
                    prompt_parts.append(
                        f"    <instructions>{h_turn['instructions']}</instructions>"
                    )
                    prompt_parts.append(
                        f"    <response>{h_turn['response']}</response>"
                    )
                    if "tool_result" in h_turn:
                        prompt_parts.append(
                            f"    <tool_result>{h_turn['tool_result']}</tool_result>"
                        )
                    prompt_parts.append("  </turn>")
                prompt_parts.append("</conversation_history>\n")

            prompt_parts.append(f'<current_turn number="{turn}">')
            prompt_parts.append(
                f"  <instructions>{current_instructions}</instructions>"
            )
            prompt_parts.append("</current_turn>\n")
            prompt_parts.append(
                "Provide your response for the current turn. Output ONLY the response/tool call for the current turn. "
                "Do NOT include any tags, conversational fillers, or future turns."
            )

            full_prompt = "\n".join(prompt_parts)

            response = self.client.query(
                full_prompt,
                system_instruction,
                temperature=0.2,
            )

            turn_record = {
                "number": turn,
                "instructions": current_instructions,
                "response": response,
            }

            # Parse tool calls
            tool_match = re.search(
                r"\[TOOL_CALL:\s*([a-zA-Z_0-9]+)\((.*?)\)\]", response
            )
            if tool_match:
                called_tool = tool_match.group(1)
                args_str = tool_match.group(2)

                if called_tool == "web_search":
                    if turn == turn_budget:
                        result = "Error: Cannot execute web search on final turn. Turn budget exhausted."
                    else:
                        # Extract query
                        query_match = re.search(r"query\s*=\s*\"(.*?)\"", args_str)
                        query = (
                            query_match.group(1)
                            if query_match
                            else f"{asset_name} {sponsor} clinical data"
                        )
                        sanitized_query = sanitize_search_query(query)
                        result = web_search(sanitized_query)
                    turn_record["tool_result"] = result
                elif called_tool == "edit_landscape_table":
                    # Parse safety, efficacy, licensing, milestones, citations
                    args = {}
                    for kv in re.findall(r"([a-zA-Z_0-9]+)\s*=\s*\"(.*?)\"", args_str):
                        args[kv[0]] = kv[1]

                    safety = args.get("safety") or "Safety profile evaluated."
                    efficacy = args.get("efficacy") or "Efficacy data reviewed."
                    licensing = (
                        args.get("licensing") or "Licensing status pending/unknown."
                    )
                    milestones = (
                        args.get("milestones") or "Next clinical readout pending."
                    )
                    citations = args.get("citations") or "N/A"

                    with self._registry_lock:
                        update_table_row(
                            table_path,
                            asset_name,
                            safety,
                            efficacy,
                            licensing,
                            milestones,
                            citations,
                            self.asset_config,
                        )
                    turn_record["tool_result"] = "Table updated successfully."
                    table_updated = True
                else:
                    turn_record["tool_result"] = f"Unknown tool '{called_tool}'."

            history_turns.append(turn_record)

            if "[FINALIZE]" in response or turn == turn_budget:
                break

        # Fallback automated extraction if table was not updated
        if not table_updated:
            formatting.print_warning(
                f"Web research agent did not update the table for {asset_name}. Running fallback extraction..."
            )
            history_text_list = []
            for h_turn in history_turns:
                history_text_list.append(
                    f"Turn {h_turn['number']} Instructions: {h_turn['instructions']}"
                )
                history_text_list.append(
                    f"Turn {h_turn['number']} Response: {h_turn['response']}"
                )
                if "tool_result" in h_turn:
                    history_text_list.append(
                        f"Turn {h_turn['number']} Tool Result: {h_turn['tool_result']}"
                    )
            history_text = "\n".join(history_text_list)

            fallback_prompt = (
                f"Based on the research history below for candidate '{asset_name}', please extract or summarize the following fields:\n"
                f"1. Selectivity & Safety Profile (concise description)\n"
                f"2. Key Efficacy Data (concise description)\n"
                f"3. Licensing Status & Partners (concise description of licensing availability, sponsor class (e.g. big pharma), and/or existing deals)\n"
                f"4. Upcoming Milestones (concise description)\n"
                f"5. Citations / Sources (PMIDs, trial registry IDs, or links)\n\n"
                f"Research History:\n" + history_text + "\n\n"
                "Respond ONLY with a valid JSON object with the keys:\n"
                '  "safety": string\n'
                '  "efficacy": string\n'
                '  "licensing": string\n'
                '  "milestones": string\n'
                '  "citations": string\n'
                "Respond with valid JSON only. No explanation, no other text."
            )
            fallback_system = (
                "You are a data extraction assistant. Output only valid JSON."
            )
            try:
                fallback_response = self.client.query(fallback_prompt, fallback_system)
                clean_res = fallback_response.strip()
                if clean_res.startswith("```"):
                    clean_res = re.sub(r"^```[a-z]*\n?", "", clean_res)
                    clean_res = re.sub(r"\n?```$", "", clean_res.strip())
                res_dict = json.loads(clean_res)
                safety = (
                    res_dict.get("safety")
                    or "Selectivity/safety profile details not found in search results."
                )
                efficacy = (
                    res_dict.get("efficacy")
                    or "Key efficacy data not found in search results."
                )
                licensing = (
                    res_dict.get("licensing") or "Licensing status pending/unknown."
                )
                milestones = (
                    res_dict.get("milestones")
                    or "Next clinical readouts/milestones pending."
                )
                citations = res_dict.get("citations") or "N/A"
                with self._registry_lock:
                    update_table_row(
                        table_path,
                        asset_name,
                        safety,
                        efficacy,
                        licensing,
                        milestones,
                        citations,
                        self.asset_config,
                    )
            except Exception as e:
                formatting.print_error(
                    f"Fallback extraction failed for {asset_name}: {e}"
                )
                with self._registry_lock:
                    update_table_row(
                        table_path,
                        asset_name,
                        "Safety profile query completed; details pending synthesis.",
                        "Efficacy query completed; details pending synthesis.",
                        "Licensing status query completed; details pending synthesis.",
                        "Milestones query completed; details pending synthesis.",
                        "N/A",
                        self.asset_config,
                    )

        # Save execution log to a markdown file
        clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", asset_name)
        log_file = (
            self.target_dir / "web_search" / f"web_research_log_{clean_name.lower()}.md"
        )

        log_content = [
            f"# Web Research Log: {asset_name}",
            f"**Developer**: {sponsor}",
            f"**Modality**: {modality}",
            f"**Phase**: {phase}",
            f"**Trial IDs**: {trials}",
            "",
            "## Execution History",
            "",
        ]
        for h_turn in history_turns:
            log_content.append(f"### Turn {h_turn['number']}")
            log_content.append(f"**Instructions**: {h_turn['instructions']}")
            log_content.append(f"**Agent Response**:\n{h_turn['response']}")
            if "tool_result" in h_turn:
                log_content.append(f"**Tool Result**:\n{h_turn['tool_result']}")
            log_content.append("\n---\n")

        log_file.write_text("\n".join(log_content), encoding="utf-8")

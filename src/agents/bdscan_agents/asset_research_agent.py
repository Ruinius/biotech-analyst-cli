import re
from pathlib import Path

from duckduckgo_search import DDGS

from src.core.config import Settings
from src.services.llm_client import LLMClient
from src.utils import formatting


def clean_cell_to_name(cell: str) -> str:
    cell = re.sub(r"<[^>]+>", " ", cell)
    cell = cell.replace("**", "").replace("*", "").replace("__", "").replace("_", "")
    cell = re.split(r"[\(（]", cell)[0]
    return cell.strip()


def extract_names_from_cell(cell: str) -> list[str]:
    cleaned = re.sub(r"<[^>]+>", " ", cell)
    cleaned = (
        cleaned.replace("**", "").replace("*", "").replace("__", "").replace("_", "")
    )
    names = re.findall(r"[a-zA-Z0-9\-]{3,25}", cleaned)
    return [n.strip() for n in names if n.strip()]


def update_table_row(
    table_path: Path,
    asset_name: str,
    safety: str,
    efficacy: str,
    milestones: str,
    citations: str,
):
    """Write back the researched details directly to the landscape table in research/."""
    if not table_path.exists():
        return

    content = table_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    for idx, line in enumerate(lines):
        if not line.strip() or idx < 2:
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 3:
            continue

        name_cell = cols[1]
        cleaned_name = clean_cell_to_name(name_cell)
        if cleaned_name.lower() == asset_name.lower():
            # Update columns 12, 13, 14, 15 (which correspond to Web columns)
            cols[12] = safety.replace("\n", " ").replace("|", "\\|")
            cols[13] = efficacy.replace("\n", " ").replace("|", "\\|")
            cols[14] = milestones.replace("\n", " ").replace("|", "\\|")
            cols[15] = citations.replace("\n", " ").replace("|", "\\|")
            lines[idx] = "| " + " | ".join(cols[1:-1]) + " |"
            break

    table_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_learnings(section: str, new_learning: str):
    path = Path("src/agents/learning.md")
    if not path.exists():
        return
    try:
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        section_header = f"## {section}"

        section_idx = -1
        for idx, line in enumerate(lines):
            if line.strip() == section_header:
                section_idx = idx
                break

        if section_idx == -1:
            return

        # Find next section or end of file
        next_section_idx = len(lines)
        for idx in range(section_idx + 1, len(lines)):
            if lines[idx].startswith("## "):
                next_section_idx = idx
                break

        # Get current section lines
        sec_lines = lines[section_idx + 1 : next_section_idx]
        sec_lines = [l for l in sec_lines if l.strip() and "Initializing" not in l]

        # Avoid adding exact duplicate learning lines
        new_line = f"- {new_learning.strip()}"
        if new_line not in sec_lines:
            sec_lines.append(new_line)

        # Limit to 20 lines max
        sec_lines = sec_lines[-20:]

        new_content = lines[: section_idx + 1] + sec_lines + lines[next_section_idx:]
        path.write_text("\n".join(new_content) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"Warning: Failed to update learnings: {e}")


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
    """Agent executing 4-turn web research loop sequentially for each asset in the master table."""

    def __init__(self, settings: Settings, target_dir: Path):
        self.settings = settings
        self.target_dir = target_dir
        self.client = LLMClient()
        self.aliases_map = {}

    def research_all_assets(self) -> Path:
        table_path = self.target_dir / "research" / "landscape_table.md"
        if not table_path.exists():
            raise FileNotFoundError(f"Master landscape table not found at {table_path}")

        formatting.print_info(
            "Starting sequential web diligence research loops for all assets..."
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

        for _idx, cols in rows_to_process:
            name_cell = cols[1]
            primary_name = clean_cell_to_name(name_cell)
            all_synonyms = extract_names_from_cell(name_cell)

            # Check if this asset has already been researched under an alias
            duplicate_parent = None
            for syn in all_synonyms:
                if syn.lower() in self.aliases_map:
                    duplicate_parent = self.aliases_map[syn.lower()]
                    break

            if duplicate_parent:
                formatting.print_warning(
                    f"Duplicate asset detected: '{primary_name}' maps to already-researched parent '{duplicate_parent}'."
                )
                # Skip search, link qualitative columns to parent asset
                self.link_duplicate_asset(table_path, primary_name, duplicate_parent)
                continue

            # Record aliases to prevent duplicate searches later
            for syn in all_synonyms:
                self.aliases_map[syn.lower()] = primary_name

            # Run 4-turn loop for this new asset
            formatting.print_info(
                f"Researching asset: {primary_name} ({cols[2] if len(cols) > 2 else 'N/A'})..."
            )
            self.run_loop_for_asset(table_path, primary_name, cols)
            processed_count += 1

        formatting.print_success(
            f"Completed web research for {processed_count} unique assets."
        )
        return table_path

    def link_duplicate_asset(
        self, table_path: Path, duplicate_name: str, parent_name: str
    ):
        """Find parent values and copy them to duplicate asset row."""
        content = table_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        parent_safety = "Duplicate. Refer to parent."
        parent_efficacy = "Duplicate. Refer to parent."
        parent_milestones = "Duplicate. Refer to parent."
        parent_citations = "N/A"

        for idx, line in enumerate(lines):
            if not line.strip() or idx < 2:
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) < 3:
                continue
            if clean_cell_to_name(cols[1]).lower() == parent_name.lower():
                parent_safety = cols[12]
                parent_efficacy = cols[13]
                parent_milestones = cols[14]
                parent_citations = cols[15]
                break

        update_table_row(
            table_path=table_path,
            asset_name=duplicate_name,
            safety=parent_safety,
            efficacy=parent_efficacy,
            milestones=parent_milestones,
            citations=parent_citations,
        )

    def run_loop_for_asset(self, table_path: Path, asset_name: str, cols: list[str]):
        history = []
        turn_budget = 4

        sponsor = cols[2] if len(cols) > 2 else "N/A"
        modality = cols[3] if len(cols) > 3 else "N/A"
        phase = cols[6] if len(cols) > 6 else "N/A"
        trials = cols[7] if len(cols) > 7 else "N/A"

        system_instruction = (
            f"You are Dr. Hops' Asset Research Agent dilution scout for the candidate '{asset_name}'.\n"
            f"Developer: {sponsor}, Modality: {modality}, Phase: {phase}, Trial IDs: {trials}.\n"
            "Your objective is to find recent clinical data, selectivity profile details, and upcoming milestones.\n"
            "You have a budget of up to 4 turns.\n"
            "Supported tools:\n"
            '- [TOOL_CALL: web_search(query="query_string")]\n'
            '- [TOOL_CALL: edit_landscape_table(safety="...", efficacy="...", milestones="...", citations="...")]\n'
            "When done or on Turn 4, write your final response ending with the [FINALIZE] tag.\n"
            "Always cite PMIDs, NCT links, press releases, or conference abstracts."
        )

        for turn in range(1, turn_budget + 1):
            prompt = (
                f"We are conducting due diligence on '{asset_name}' developed by '{sponsor}'.\n"
                f"Turn {turn} details:\n"
            )
            if turn == 1:
                prompt += f"Please run an initial web_search to find selectivity, safety, and clinical milestones for {asset_name}."
            else:
                prompt += (
                    "Review the search results. If you have sufficient qualitative safety, efficacy, and milestone information, "
                    "call the edit_landscape_table tool to update the table, and output [FINALIZE]. Otherwise, run another search."
                )

            # Invoke LLM
            full_prompt = prompt + "\n\nHistory:\n" + "\n".join(history)
            response = self.client.query(full_prompt, system_instruction)

            history.append(f"User: {prompt}")
            history.append(f"Agent: {response}")

            # Parse tool calls
            tool_match = re.search(
                r"\[TOOL_CALL:\s*([a-zA-Z_0-9]+)\((.*?)\)\]", response
            )
            if tool_match:
                called_tool = tool_match.group(1)
                args_str = tool_match.group(2)

                if called_tool == "web_search":
                    # Extract query
                    query_match = re.search(r"query\s*=\s*\"(.*?)\"", args_str)
                    query = (
                        query_match.group(1)
                        if query_match
                        else f"{asset_name} {sponsor} clinical data"
                    )
                    result = web_search(query)
                    history.append(f"System Tool Result: {result}")
                elif called_tool == "edit_landscape_table":
                    # Parse safety, efficacy, milestones, citations
                    args = {}
                    for kv in re.findall(r"([a-zA-Z_0-9]+)\s*=\s*\"(.*?)\"", args_str):
                        args[kv[0]] = kv[1]

                    safety = args.get("safety") or "Safety profile evaluated."
                    efficacy = args.get("efficacy") or "Efficacy data reviewed."
                    milestones = (
                        args.get("milestones") or "Next clinical readout pending."
                    )
                    citations = args.get("citations") or "N/A"

                    update_table_row(
                        table_path, asset_name, safety, efficacy, milestones, citations
                    )
                    history.append("System Tool Result: Table updated successfully.")
                else:
                    history.append(f"System Tool Result: Unknown tool '{called_tool}'.")
            else:
                if "[FINALIZE]" in response or turn == turn_budget:
                    break

        # Save execution log to a markdown file
        clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", asset_name)
        log_file = (
            self.target_dir
            / "research"
            / f"web_research_log_{clean_name.lower()}.md"
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
        for hist_item in history:
            log_content.append(hist_item)
            log_content.append("\n---\n")

        log_file.write_text("\n".join(log_content), encoding="utf-8")

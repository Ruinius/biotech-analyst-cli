import datetime
import re
from pathlib import Path

from ddgs import DDGS

from src.core.config import Settings
from src.services.llm_client import LLMClient
from src.utils import formatting
from src.utils.generate_landscape_table import md_table_to_csv, md_table_to_text_table


def web_search(query: str) -> str:
    """Query DuckDuckGo for strategic and market details."""
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
            return "No search results found."
        return "\n".join(results)
    except Exception as e:
        return f"Error executing DuckDuckGo search: {str(e)}"


class SynthesisAgent:
    """Strategic synthesis agent executing up to 10-turn reasoning loop to compile reports."""

    def __init__(self, settings: Settings, folder_safe_name: str, target_dir: Path):
        self.settings = settings
        self.folder_safe_name = folder_safe_name
        self.target_dir = target_dir
        self.client = LLMClient()

    def generate_synthesis(
        self, target_name: str, modality: str = ""
    ) -> tuple[Path, Path]:
        formatting.print_info("Starting strategic synthesis agent loop...")

        table_path = self.target_dir / "research" / "landscape_table.md"
        context_path = self.target_dir / "context.md"

        # Read input materials to feed into agent context
        table_content = (
            table_path.read_text(encoding="utf-8") if table_path.exists() else ""
        )
        context_content = (
            context_path.read_text(encoding="utf-8") if context_path.exists() else ""
        )

        # Find any research logs in research/
        research_logs = []
        research_dir = self.target_dir / "research"
        if research_dir.exists():
            for log_file in research_dir.glob("research_log_*.md"):
                log_content = log_file.read_text(encoding="utf-8")
                research_logs.append(
                    f"File: {log_file.name}\n{log_content[:2000]}\n---"
                )

        logs_summary = "\n".join(research_logs)

        history_turns = []
        turn_budget = 10

        system_instruction = (
            f"You are Dr. Hops' Senior Biotech BD Synthesis Agent. Your task is to draft the final strategic diligence report "
            f"for the pathway/target '{target_name}'.\n"
            "You have access to the landscape table and research logs.\n"
            "Supported tools:\n"
            '- [TOOL_CALL: web_search(query="query_string")]\n'
            "You have up to 10 turns. When finished, write your response containing the strategic diligence report "
            "and output the [FINALIZE] tag at the very end.\n"
            "Constraints:\n"
            "- Do NOT embed the big competitive landscape table inside the strategic report to avoid PDF page-splitting/formatting issues.\n"
            "- The strategic report should detail the scientific rationale, differentiation vectors (by modality/formulation), "
            "commercial viability, regulatory class-wide risks, swot analysis, and upcoming clinical milestones.\n"
            "Draft the report with high density and rigorous, quantitative findings."
        )

        for turn in range(1, turn_budget + 1):
            formatting.print_info(f"  Synthesis Turn {turn}/{turn_budget}...")

            if turn == turn_budget:
                current_instructions = (
                    "CRITICAL: This is your LAST turn (Turn Budget Exhausted). You MUST compile and write the complete, "
                    "detailed final strategic diligence report now, and end your response with the [FINALIZE] tag. Do NOT make any tool calls."
                )
            elif turn == 1:
                current_instructions = (
                    "Please analyze the pathway data and run a web_search query to verify recent market size, "
                    "regulatory policies, or competitor status for this class."
                )
            else:
                current_instructions = (
                    "Review the gathered details. If you have enough insights, write the final strategic diligence report "
                    "and output [FINALIZE]. Otherwise, execute another search query."
                )

            # Construct prompt using XML tags to avoid LLM transcript-completion loops
            prompt_parts = [
                f"We are compiling the final broad scan report for '{target_name}'.",
                f"Target Modality: {modality if modality else 'All'}\n",
                f"Context Overview:\n{context_content}\n",
                f"Research Logs Summary:\n{logs_summary}\n",
            ]
            if history_turns:
                prompt_parts.append("<conversation_history>")
                for h_turn in history_turns:
                    prompt_parts.append(f'  <turn number="{h_turn["number"]}">')
                    prompt_parts.append(
                        f'    <instructions>{h_turn["instructions"]}</instructions>'
                    )
                    prompt_parts.append(
                        f'    <response>{h_turn["response"]}</response>'
                    )
                    if "tool_result" in h_turn:
                        prompt_parts.append(
                            f'    <tool_result>{h_turn["tool_result"]}</tool_result>'
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
            response = self.client.query(full_prompt, system_instruction)

            turn_record = {
                "number": turn,
                "instructions": current_instructions,
                "response": response,
            }

            if turn == turn_budget:
                history_turns.append(turn_record)
                break

            # Parse tool calls
            tool_match = re.search(
                r"\[TOOL_CALL:\s*([a-zA-Z_0-9]+)\((.*?)\)\]", response
            )
            if tool_match:
                called_tool = tool_match.group(1)
                args_str = tool_match.group(2)

                if called_tool == "web_search":
                    query_match = re.search(r"query\s*=\s*\"(.*?)\"", args_str)
                    query = (
                        query_match.group(1)
                        if query_match
                        else f"{target_name} market size pricing oncology"
                    )
                    result = web_search(query)
                    turn_record["tool_result"] = result
                else:
                    turn_record["tool_result"] = f"Unknown tool '{called_tool}'."
            else:
                if "[FINALIZE]" in response:
                    history_turns.append(turn_record)
                    break

            history_turns.append(turn_record)

        # Generate report and table files in final_output/
        date_str = datetime.date.today().strftime("%Y%m%d")
        final_output_dir = self.target_dir / "final_output"
        final_output_dir.mkdir(parents=True, exist_ok=True)

        report_file = (
            final_output_dir
            / f"meta_analysis_{self.folder_safe_name}_report_{date_str}.md"
        )
        table_file = (
            final_output_dir
            / f"meta_analysis_{self.folder_safe_name}_table_{date_str}.md"
        )

        # Robustly extract the agent's response containing the report
        report_text = ""
        if history_turns:
            report_text = history_turns[-1]["response"].strip()

        # Clean up tags and tool call strings if present
        report_text = report_text.replace("[FINALIZE]", "").strip()
        report_text = re.sub(r"\[TOOL_CALL:.*?\]", "", report_text).strip()

        # Write strategic report
        report_header = (
            f"# Pathway Landscape Meta-Analysis: {target_name}\n\n"
            f"**Date of Report**: {datetime.date.today().strftime('%B %d, %Y')}\n"
            f"**Analyst**: Senior Biotech BD Analyst\n"
            f"**Target Pathway**: {target_name}\n\n"
            f"**Note**: The corresponding competitive landscape table is compiled in [meta_analysis_{self.folder_safe_name}_table_{date_str}.md](meta_analysis_{self.folder_safe_name}_table_{date_str}.md).\n\n"
            "---\n\n"
        )
        report_file.write_text(report_header + report_text, encoding="utf-8")
        formatting.print_success(f"Saved strategic report to {report_file}")

        # Write table markdown separately, with column-aligned formatting
        table_header = (
            f"# Reconciled Competitive Matrix: {target_name}\n\n"
            f"**Date of Table**: {datetime.date.today().strftime('%B %d, %Y')}\n"
            f"**Target Pathway**: {target_name}\n\n"
            "---\n\n"
        )
        table_md = table_header + table_content
        table_file.write_text(md_table_to_text_table(table_md), encoding="utf-8")
        formatting.print_success(
            f"Saved column-aligned competitive matrix table to {table_file}"
        )

        # Write CSV version alongside the .md
        csv_file = table_file.with_suffix(".csv")
        csv_file.write_text(md_table_to_csv(table_md), encoding="utf-8-sig")
        formatting.print_success(f"Saved CSV competitive matrix at {csv_file}")

        return report_file, table_file

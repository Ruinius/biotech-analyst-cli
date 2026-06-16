from pathlib import Path

from src.core.config import Settings
from src.services.llm_client import LLMClient
from src.utils import formatting


class CuratorAgent:
    """Stage-end curation agent that aggregates logs from sweeps to update rules and search lessons."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = LLMClient()
        self.learning_filepath = Path(__file__).parent.parent / "learning.md"

    def curate_database_search(self, target_dir: Path):
        """Ingest database search logs and update global learnings under ## database-search."""
        formatting.speak("Dr. Hops' Curator Agent is analyzing database search execution logs...")

        research_dir = target_dir / "research"
        if not research_dir.exists():
            formatting.print_warning(f"Research directory not found at {research_dir}")
            return

        log_files = list(research_dir.glob("research_log_*.md"))
        if not log_files:
            formatting.print_warning("No database search research logs found to curate.")
            return

        logs_content = ""
        for lf in log_files:
            logs_content += f"\nFile: {lf.name}\n"
            try:
                logs_content += lf.read_text(encoding="utf-8")
            except Exception as e:
                formatting.print_error(f"Failed to read {lf.name}: {e}")
            logs_content += "\n---\n"

        existing = self.get_existing_learnings("database-search")
        new_bullets = self.query_llm_for_learnings("database-search", existing, logs_content)
        self.update_section("database-search", new_bullets)
        formatting.print_success("Database search learnings updated successfully.")

    def curate_web_search(self, target_dir: Path):
        """Ingest web research logs and update global learnings under ## web-search."""
        formatting.speak("Dr. Hops' Curator Agent is analyzing web research execution logs...")

        research_dir = target_dir / "research"
        if not research_dir.exists():
            formatting.print_warning(f"Research directory not found at {research_dir}")
            return

        log_files = list(research_dir.glob("web_research_log_*.md"))
        if not log_files:
            formatting.print_warning("No web research logs found to curate.")
            return

        logs_content = ""
        for lf in log_files:
            logs_content += f"\nFile: {lf.name}\n"
            try:
                logs_content += lf.read_text(encoding="utf-8")
            except Exception as e:
                formatting.print_error(f"Failed to read {lf.name}: {e}")
            logs_content += "\n---\n"

        existing = self.get_existing_learnings("web-search")
        new_bullets = self.query_llm_for_learnings("web-search", existing, logs_content)
        self.update_section("web-search", new_bullets)
        formatting.print_success("Web search learnings updated successfully.")

    def get_existing_learnings(self, section: str) -> str:
        """Read and return existing bullet points for a section in learning.md."""
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
        except Exception as e:
            formatting.print_error(f"Failed to read existing learnings: {e}")
            return ""

    def query_llm_for_learnings(self, section: str, existing: str, logs: str) -> list[str]:
        """Call the LLM Client to extract and synthesize learnings from logs."""
        system_instruction = (
            "You are Dr. Hops' Senior Curation Agent. Your objective is to extract valuable, "
            "actionable lessons, database search tips, nomenclature rules, translation mappings, "
            "or web search heuristics from the provided logs, and merge them with existing learnings.\n"
            "Return only the final updated list of learnings as bullet points, each on a single line starting with '- '.\n"
            "Limit the response to a maximum of 15 bullet points.\n"
            "Do NOT include any introduction, formatting wrappers, extra commentary, or conversational output."
        )

        prompt = (
            f"We are curating and updating the pipeline learnings for '{section}'.\n\n"
            f"Existing Learnings:\n{existing if existing else '(None)'}\n\n"
            f"New Execution/Search Logs:\n{logs}\n\n"
            "Analyze the logs and identify any patterns, failures, successes, or search tricks (e.g. spelling variants, translation rules, API limits).\n"
            "Consolidate these into a clean bulleted list (max 15 bullets, each on a single line).\n"
            "Ensure they merge with and refine the existing learnings without duplicate entries."
        )

        response = self.client.query(prompt, system_instruction)

        bullets = []
        for line in response.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if line_stripped.startswith("- ") or line_stripped.startswith("* "):
                bullets.append(line_stripped[2:].strip())
            elif line_stripped.startswith("-") or line_stripped.startswith("*"):
                bullets.append(line_stripped[1:].strip())
            else:
                bullets.append(line_stripped)

        return bullets

    def update_section(self, section: str, bullet_points: list[str]):
        """Write the updated bullet points to the correct section in learning.md, limiting to 20 lines max."""
        if not self.learning_filepath.exists():
            # Create a basic file template if missing
            self.learning_filepath.write_text(
                "# Pipeline Learnings & Lessons (`learning.md`)\n\n"
                "This file contains accumulated learnings, heuristics, and constraints gathered by the Biotech Analyst CLI agents during execution.\n\n"
                "## database-search\n- Initializing search strategy template.\n\n"
                "## web-search\n- Initializing web search template.\n",
                encoding="utf-8"
            )

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
                # If section not found, append it
                lines.append("")
                lines.append(section_header)
                section_idx = len(lines) - 1

            next_section_idx = len(lines)
            for idx in range(section_idx + 1, len(lines)):
                if lines[idx].strip().startswith("## "):
                    next_section_idx = idx
                    break

            # Filter and format bullet points
            cleaned_bullets = [bp.strip() for bp in bullet_points if bp.strip()]
            formatted_points = [f"- {bp}" if not bp.startswith("- ") else bp for bp in cleaned_bullets]

            # Enforce max 20 lines constraint programmatically
            formatted_points = formatted_points[:20]

            # Reconstruct the file content
            new_content = lines[:section_idx + 1] + formatted_points + [""] + lines[next_section_idx:]

            # Clean double empty lines
            cleaned_lines = []
            prev_empty = False
            for line in new_content:
                is_empty = not line.strip()
                if is_empty and prev_empty:
                    continue
                cleaned_lines.append(line)
                prev_empty = is_empty

            self.learning_filepath.write_text("\n".join(cleaned_lines) + "\n", encoding="utf-8")
        except Exception as e:
            formatting.print_error(f"Failed to write updated section to learnings file: {e}")

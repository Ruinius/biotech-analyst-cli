import datetime
from pathlib import Path

from src.core.config import Settings
from src.core.exceptions import PipelineError
from src.services.llm_client import LLMClient
from src.utils import formatting


def generate_context(
    settings: Settings,
    target_name: str,
    en_list: list[str],
    zh_list: list[str],
    modality: str,
    target_dir: Path,
) -> Path:
    """Generate a concise, science-focused biological grounding context.md file."""
    formatting.print_info(f"Generating scientific context for target: {target_name}...")

    # Build prompt
    en_synonyms = ", ".join(en_list) if en_list else target_name
    zh_synonyms = ", ".join(zh_list) if zh_list else target_name
    modality_str = (
        modality if modality else "All (mAbs, ADCs, Bispecifics, CAR-T, etc.)"
    )

    prompt = (
        f"Generate a concise, science-focused, biological grounding overview for the target: '{target_name}'.\n\n"
        f"**English Synonyms**: {en_synonyms}\n"
        f"**Mandarin Synonyms**: {zh_synonyms}\n"
        f"**Target Modality**: {modality_str}\n\n"
        f"Please write a short markdown overview structured as follows:\n"
        f"## 1. Biology and Scientific Rationale\n"
        f"Key biological roles, cellular mechanisms, and functional roles of the target.\n\n"
        f"## 2. Clinical Settings and Disease Areas\n"
        f"Primary disease indications, patient populations, and why this pathway is clinically targeted.\n\n"
        f"## 3. Modality Considerations\n"
        f"Brief notes on modal approaches (e.g. ADCs vs mAbs vs bispecifics) for this target.\n\n"
        f"Constraints:\n"
        f"- Keep the entire output under 300 words. Be extremely concise to prevent downstream context window bloating.\n"
        f"- Output raw markdown starting directly with '## 1. Biology and Scientific Rationale'. No greetings, conversational text, or outer code blocks."
    )

    system_instruction = (
        "You are an expert molecular biologist and biotech diligence analyst. "
        "Your task is to provide extremely concise, accurate, and high-density scientific context."
    )

    client = LLMClient()
    response_text = client.query(prompt, system_instruction)

    # Raise error if query failed or returned empty/error
    if (
        not response_text
        or response_text.startswith("Error:")
        or response_text.startswith("Failed to call")
    ):
        raise PipelineError(
            f"LLM context generation failed or returned error: {response_text}"
        )

    # Format the context file
    context_content = (
        f"# Context Overview: {target_name} Sourcing\n\n"
        f"**Target Pathway**: {target_name}\n"
        f"**Modality Filters**: {modality_str}\n"
        f"**Date**: {datetime.date.today().strftime('%Y-%m-%d')}\n\n"
        f"{response_text.strip()}\n"
    )

    context_path = target_dir / "context.md"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(context_content, encoding="utf-8")

    formatting.print_success(f"Successfully compiled context.md at {context_path}")
    return context_path

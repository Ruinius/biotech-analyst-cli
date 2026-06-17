#!/usr/bin/env python3
"""
Competitive Landscape Table Generator — backward-compatible re-export shim.

The implementation has been decomposed into src/utils/landscape/ submodules (§3).
This file re-exports all public symbols so that any existing imports continue
to work unchanged during the transition period.

Deprecation: this shim will be removed after §2 (LLM Alias Resolution) passes
all tests and downstream consumers are updated to import from the submodules.
"""

# Re-export everything from the new submodule locations
from src.agents.bdscan_agents.intervention_classifier_agent import (
    classify_interventions,  # noqa: F401
)
from src.utils.landscape.config_builder import (  # noqa: F401
    discover_config,
    merge_config_duplicates,
    parse_existing_report,
)
from src.utils.landscape.exporters import (  # noqa: F401
    _strip_md,
    md_table_to_csv,
    md_table_to_text_table,
)
from src.utils.landscape.table_builder import (  # noqa: F401
    build_landscape_table,
    load_and_build_from_files,
)
from src.utils.landscape.table_formatters import (  # noqa: F401
    CDE_ACTIVE,
    CDE_COMPLETED,
    CDE_DISCONTINUED,
    CT_ACTIVE,
    CT_COMPLETED,
    CT_DISCONTINUED,
    _name_priority,
    clean_cell_to_name,
    clean_sponsor,
    detect_formulation,
    matches_drug,
    normalize_drug_name,
    parse_asset_and_aliases,
    parse_ct_phase,
    parse_text_phase,
)


# ---------------------------------------------------------------------------
# CLI entry point (preserved for backward-compatibility)
# ---------------------------------------------------------------------------
def main():
    """Delegate to the modular CLI shim."""
    from src.utils.landscape.__main__ import main as _main  # noqa: PLC0415

    _main()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lint Unraid template to verify environment variables are a strict subset of
recognized app env vars. Fails with exit code 1 if unknown variables found.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Recognized environment variables that the app expects
RECOGNIZED_VARS = {
    "JELLYFIN_URL",
    "JELLYFIN_API_KEY",
    "TMDB_ACCESS_TOKEN",
    "SESSION_SECRET",
    "DB_PATH",
    "JELLYFIN_DEVICE_ID",
    "PUID",
    "PGID",
}


def extract_variables(template_path: Path) -> set[str]:
    """Extract all variable names from <Variable> and <Config> sections."""
    tree = ET.parse(template_path)
    root = tree.getroot()

    variables = set()

    # Extract from <Variable> sections (legacy format)
    for variable in root.findall(".//Variable"):
        name_elem = variable.find("Name")
        if name_elem is not None and name_elem.text:
            variables.add(name_elem.text.strip())

    # Extract from <Config> sections (modern format) - only Type="Variable" are env vars
    for config in root.findall(".//Config"):
        config_type = config.get("Type")
        if config_type == "Variable":
            name_attr = config.get("Name")
            if name_attr:
                variables.add(name_attr)

    return variables


def main():
    if len(sys.argv) != 2:
        print("Usage: lint-unraid-template.py <template-file>")
        sys.exit(1)

    template_path = Path(sys.argv[1])
    if not template_path.exists():
        print(f"Error: Template file not found: {template_path}")
        sys.exit(1)

    template_vars = extract_variables(template_path)
    unknown_vars = template_vars - RECOGNIZED_VARS

    if unknown_vars:
        print("❌ Unraid template validation failed")
        print(f"Unknown environment variables found: {sorted(unknown_vars)}")
        print(f"Recognized variables: {sorted(RECOGNIZED_VARS)}")
        sys.exit(1)

    print("✓ Unraid template validation passed")
    print(f"All {len(template_vars)} variables are recognized")
    sys.exit(0)


if __name__ == "__main__":
    main()

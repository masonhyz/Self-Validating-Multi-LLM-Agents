#!/usr/bin/env python3
"""
convert_cases_md_to_json_flexible.py

Converts a markdown file of "Case" blocks into JSON.

Header formats supported:
  A) Case 12: <genre>
  B) <genre>: Case 12:

(Genre is optional in both; if missing, genre=null.)

Extracted fields per case:
- case_number (int)
- genre (str | null)
- prompt (str | null)         # free-text description lines in the block
- constraints (list[str])     # markdown bullets beginning with * or -
- objective (str | null)      # line starting with "Objective:"
- output_format (str | null)  # line starting with "Output format:"
- full_content (str)          # raw markdown content of the entire case block (header + body)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Format B (genre before Case) must be checked first so it doesn't get swallowed by format A.
HEADER_B_RE = re.compile(
    r"^\s*(?P<genre>[^:\n]+?)\s*:\s*Case\s+(?P<num>\d+)\s*:\s*(?P<suffix>.*)\s*$",
    re.IGNORECASE,
)

# Format A (Case first): "Case 2: Binary string / coding theory"
HEADER_A_RE = re.compile(
    r"^\s*Case\s+(?P<num>\d+)\s*:\s*(?P<after>.*)\s*$",
    re.IGNORECASE,
)

BULLET_RE = re.compile(r"^\s*[*-]\s+(.*)\s*$")
OBJECTIVE_RE = re.compile(r"^\s*Objective\s*:\s*(.*)\s*$", re.IGNORECASE)
OUTPUT_RE = re.compile(r"^\s*Output\s*format\s*:\s*(.*)\s*$", re.IGNORECASE)


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_headers(lines: List[str]) -> List[Tuple[int, int, Optional[str]]]:
    """Return list of (line_index, case_number, genre)."""
    headers: List[Tuple[int, int, Optional[str]]] = []
    for i, line in enumerate(lines):
        mB = HEADER_B_RE.match(line)
        if mB:
            num = int(mB.group("num"))
            genre_raw = normalize_ws(mB.group("genre"))
            # If suffix exists in B format, treat it as part of genre (rare, but safe).
            suffix = normalize_ws(mB.group("suffix")) if mB.group("suffix") else ""
            genre = normalize_ws(f"{genre_raw} {suffix}".strip()) or None
            headers.append((i, num, genre))
            continue

        mA = HEADER_A_RE.match(line)
        if mA:
            num = int(mA.group("num"))
            after = normalize_ws(mA.group("after") or "")
            # In A format, everything after the colon is the genre/title line (optional)
            genre = after or None
            headers.append((i, num, genre))
            continue

    return headers


def parse_cases(md_text: str) -> List[Dict[str, Any]]:
    lines = md_text.splitlines()
    headers = parse_headers(lines)

    cases: List[Dict[str, Any]] = []
    for k, (start_i, num, genre) in enumerate(headers):
        end_i = headers[k + 1][0] if k + 1 < len(headers) else len(lines)

        # Body only (for parsed fields)
        block_lines = lines[start_i + 1 : end_i]

        # Raw full block (header + body), preserved as closely as possible
        full_content = "\n".join(lines[start_i:end_i]).rstrip()

        constraints: List[str] = []
        objective: Optional[str] = None
        output_format: Optional[str] = None
        desc_lines: List[str] = []

        for raw in block_lines:
            line = raw.rstrip()

            m_obj = OBJECTIVE_RE.match(line)
            if m_obj:
                v = normalize_ws(m_obj.group(1))
                objective = v if v else None
                continue

            m_out = OUTPUT_RE.match(line)
            if m_out:
                v = normalize_ws(m_out.group(1))
                output_format = v if v else None
                continue

            m_b = BULLET_RE.match(line)
            if m_b:
                v = normalize_ws(m_b.group(1))
                if v:
                    constraints.append(v)
                continue

            if line.strip():
                desc_lines.append(line.strip())

        prompt = "\n".join(desc_lines).strip() or None

        cases.append(
            {
                "case_number": num,
                "genre": genre,
                "prompt": prompt,
                "constraints": constraints,
                "objective": objective,
                "output_format": output_format,
                "full_content": full_content,
            }
        )

    return cases


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert Cases markdown blocks into simple JSON (flexible headers).")
    ap.add_argument("input_md", type=Path, help="Path to input markdown file (e.g., Cases.md)")
    ap.add_argument("-o", "--output", type=Path, default=None, help="Path to output JSON file.")
    ap.add_argument("--indent", type=int, default=2, help="JSON indentation (default: 2)")
    args = ap.parse_args()

    md_text = args.input_md.read_text(encoding="utf-8", errors="replace")
    cases = parse_cases(md_text)

    payload = {"cases": cases, "meta": {"count": len(cases)}}

    if args.output:
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=args.indent) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=args.indent))


if __name__ == "__main__":
    main()
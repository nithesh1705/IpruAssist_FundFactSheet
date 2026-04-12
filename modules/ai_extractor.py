"""
AI extractor module: GPT-4o vision-based extraction with batched page processing.

Strategy to handle large PDFs (100+ pages) within OpenAI TPM limits:
  - Pages are processed in small batches (BATCH_SIZE) to stay under token limits.
  - Fund name discovery: aggregates names across all batches.
  - Fund detail extraction: two-pass — find relevant pages first, then extract only those.
"""

import base64
import json
import time
from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

# Number of pages per API call — tune lower if still hitting limits
BATCH_SIZE = 10

# Seconds to wait between batch API calls to respect TPM limits
BATCH_DELAY = 2


# ── Helpers ───────────────────────────────────────────────────────────────────

def _encode_image(image_bytes: bytes) -> str:
    """Base64-encode image bytes for the OpenAI vision API."""
    return base64.b64encode(image_bytes).decode("utf-8")


def _build_image_content(page_images: list[bytes], start_page: int = 0) -> list[dict]:
    """
    Build GPT-4o message content blocks from a list of page images.
    start_page is the 0-based index of the first page in the batch (for labeling).
    """
    content = []
    for i, img_bytes in enumerate(page_images):
        content.append({"type": "text", "text": f"[Page {start_page + i + 1}]"})
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{_encode_image(img_bytes)}",
                "detail": "low"  # 'low' = ~85 tokens/image; change to 'high' for dense tables
            }
        })
    return content


def _parse_json_array(raw: str) -> list:
    """Safely parse a JSON array from GPT output, stripping markdown fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _call_gpt(client: OpenAI, system: str, user_content: list[dict], max_tokens: int = 1000) -> str:
    """Single GPT-4o call; returns the response text."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content}
        ],
        max_tokens=max_tokens,
        temperature=0
    )
    return response.choices[0].message.content.strip()


# ── Fund Name Extraction ───────────────────────────────────────────────────────

def extract_fund_names(client: OpenAI, page_images: list[bytes]) -> list[str]:
    """
    Scan all pages in batches and return a deduplicated sorted list of all fund scheme names.
    Each batch is processed independently; results are merged at the end.
    """
    system_prompt = (
        "You are a financial document parser specializing in mutual fund fact sheets. "
        "Your task is to identify distinct mutual fund SCHEME names — the official product name. "
        "CRITICAL RULES: "
        "1. Do NOT list plan variants as separate funds. "
        "   Examples of plan variants to IGNORE: 'Direct Plan', 'Regular Plan', 'Growth', 'IDCW', "
        "   'Dividend', 'Bonus', 'Fortnightly IDCW', 'Monthly IDCW', 'Quarterly IDCW'. "
        "   These are options WITHIN a fund, not separate fund names. "
        "2. Extract the root scheme name only, e.g. 'SBI Short Term Debt Fund', "
        "   NOT 'SBI Short Term Debt Fund - Direct Plan - Growth'. "
        "3. Ignore company/AMC names, section headers, table column labels, and footnotes. "
        "Return ONLY a valid JSON array of scheme name strings, nothing else."
    )
    user_prefix = (
        "List every distinct mutual fund SCHEME name visible on these pages. "
        "A scheme name is the core product name like 'Tata Flexi Cap Fund' or 'ICICI Prudential Bluechip Fund'. "
        "DO NOT include plan suffixes (Direct/Regular/Growth/IDCW/Dividend) — strip them off and return the base name. "
        "Return ONLY a JSON array like: [\"Scheme Name 1\", \"Scheme Name 2\"]. "
        "If no scheme names are found on these pages, return []."
    )

    all_names: set[str] = set()
    total_batches = (len(page_images) + BATCH_SIZE - 1) // BATCH_SIZE

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task(
            f"[yellow]Scanning pages for fund names (batches of {BATCH_SIZE})...",
            total=total_batches
        )

        for batch_num, start in enumerate(range(0, len(page_images), BATCH_SIZE)):
            batch = page_images[start: start + BATCH_SIZE]

            user_content = _build_image_content(batch, start_page=start)
            user_content.insert(0, {"type": "text", "text": user_prefix})

            try:
                raw = _call_gpt(client, system_prompt, user_content, max_tokens=1000)
                names = _parse_json_array(raw)
                all_names.update(names)
            except (json.JSONDecodeError, Exception):
                # Skip failed batches silently; partial results are still useful
                pass

            progress.advance(task)

            # Respect TPM — wait between batches (skip sleep after last batch)
            if batch_num < total_batches - 1:
                time.sleep(BATCH_DELAY)

    return sorted(all_names)


# ── Fund Page Locator ─────────────────────────────────────────────────────────

def find_fund_pages(client: OpenAI, page_images: list[bytes], fund_name: str) -> list[int]:
    """
    Quick two-pass scan to find which page indices (0-based) contain data about fund_name.
    Returns a list of relevant page indices so we only extract from those.
    """
    system_prompt = (
        "You are a document navigation assistant for mutual fund fact sheets. "
        "Identify which pages contain the fact sheet section for the named fund scheme. "
        "The section typically shows the fund's NAV, portfolio, returns table, holdings, etc. "
        "Return ONLY a JSON array of 1-based page numbers (integers), nothing else. "
        "If a page mentions the fund only in passing (e.g. an index or disclaimer), exclude it."
    )
    user_prefix = (
        f"Which of these pages contain the dedicated fact sheet section for the fund scheme: '{fund_name}'? "
        "Look for the page(s) that show this fund's NAV, AUM, portfolio details, returns, and holdings. "
        "Return ONLY a JSON array of 1-based page numbers like: [3, 4]. "
        "If none of these pages contain it, return []."
    )

    relevant_pages: set[int] = set()
    total_batches = (len(page_images) + BATCH_SIZE - 1) // BATCH_SIZE

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task(
            f"[yellow]Locating pages for '{fund_name}'...",
            total=total_batches
        )

        for batch_num, start in enumerate(range(0, len(page_images), BATCH_SIZE)):
            batch = page_images[start: start + BATCH_SIZE]

            user_content = _build_image_content(batch, start_page=start)
            user_content.insert(0, {"type": "text", "text": user_prefix})

            try:
                raw = _call_gpt(client, system_prompt, user_content, max_tokens=200)
                page_nums = _parse_json_array(raw)
                # Convert 1-based page numbers to 0-based indices
                relevant_pages.update(p - 1 for p in page_nums if isinstance(p, int))
            except (json.JSONDecodeError, Exception):
                pass

            progress.advance(task)

            if batch_num < total_batches - 1:
                time.sleep(BATCH_DELAY)

    return sorted(relevant_pages)


# ── Fund Detail Extraction ─────────────────────────────────────────────────────

def extract_fund_details(client: OpenAI, page_images: list[bytes], fund_name: str) -> str:
    """
    Two-pass extraction:
      Pass 1 — find which pages contain the fund's data.
      Pass 2 — extract structured Markdown from only those pages.

    Falls back to all pages if no relevant pages are found.
    """
    # Pass 1: locate relevant pages
    console.print(f"\n[yellow]⟳ Pass 1/2 — Locating pages for '{fund_name}'...[/yellow]")
    relevant_indices = find_fund_pages(client, page_images, fund_name)

    if relevant_indices:
        console.print(
            f"[green]✔ Found on pages:[/green] {[i + 1 for i in relevant_indices]}"
        )
        target_images = [page_images[i] for i in relevant_indices]
        page_offset = relevant_indices[0]
    else:
        # Fallback: use all pages (rare — only if fund page scan failed entirely)
        console.print("[yellow]⚠ Could not locate specific pages; scanning all pages.[/yellow]")
        target_images = page_images
        page_offset = 0

    # Pass 2: extract structured data from relevant pages
    console.print(f"\n[yellow]⟳ Pass 2/2 — Extracting data from {len(target_images)} page(s)...[/yellow]")

    system_prompt = (
        "You are an expert mutual fund analyst. "
        "Extract information from mutual fund fact sheets regardless of the layout, "
        "table format, or design. The format may vary across fund houses and over time. "
        "Always locate data semantically, not by fixed positions or coordinates. "
        "Output clean, well-structured Markdown only."
    )

    extraction_prompt = f"""
From the pages shown, extract ALL available information for the fund: **{fund_name}**

Generate a Markdown document with the sections below.
- If a section's data is absent, write "Not available".
- Never invent or assume values — only extract what is explicitly shown.
- For tables, use proper Markdown table syntax.

# {fund_name}

## Benchmark Index
State the benchmark index name(s) used for this fund.

## Portfolio Details
Include all of the following that are present:
- Fund Manager(s) and managing-since date
- Fund category / type
- Investment objective (brief summary)
- AUM (Assets Under Management)
- NAV (with date if shown)
- Launch / Inception date
- Exit load
- Expense ratio (regular and/or direct plan)
- Minimum investment / SIP amount
- Lock-in period (if any)
- Any other portfolio metadata visible

## Quantitative Indicators
Extract all risk/statistical metrics shown, such as:
- Standard Deviation, Beta, Sharpe Ratio, Sortino Ratio
- Alpha, Information Ratio, R-Squared, Treynor Ratio
- Any other indicators present

## Returns
Present as a Markdown table with time period columns
(e.g., 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, Since Inception).
Include rows for the fund and its benchmark(s).
Include both Absolute and CAGR figures if shown separately.

## Top 5 Stock Holdings
| Stock Name | Sector | % of Portfolio |
For each of the top 5 equity holdings visible.

## Top 5 Sector Holdings
| Sector | % of Portfolio |
For each of the top 5 sector allocations visible.

## Group Exposure
List group-level exposure data if shown (e.g., Tata Group, Adani Group).
If not shown, write "Not available".

## Rating Profile
List credit/rating breakdown (e.g., AAA, AA, Sovereign, Cash & Equivalents) with % weights.
If this is an equity fund with no rating data, write "Not applicable – equity fund".
"""

    user_content = _build_image_content(target_images, start_page=page_offset)
    user_content.insert(0, {"type": "text", "text": extraction_prompt})

    result = _call_gpt(client, system_prompt, user_content, max_tokens=4096)
    return result

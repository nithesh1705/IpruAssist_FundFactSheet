"""
AI extractor module: Hybrid GPT-4o extraction using BOTH high-res vision AND embedded PDF text.

Accuracy improvements over v2:
  1. Index-first page lookup  — Regex-parses the TOC/Index text (pages 1-15) to find the fund's
                                page number in milliseconds with ZERO API calls.
  2. Text-only GPT-mini scan  — If index lookup fails, sends only text (no images) to gpt-4o-mini
                                to narrow candidates — 10-30x faster than vision.
  3. Vision only on target    — High-res images are sent ONLY for the 1-3 confirmed pages.
  4. Image detail: "high"     — GPT reads every character in tables, footnotes, small text.
  5. Embedded text layer      — PyMuPDF extracts exact numbers/text directly from the PDF (100%
                                accuracy for digital PDFs). Sent alongside the image so GPT verifies.
  6. Strict anti-hallucination prompts — model is told to OUTPUT_ONLY what is literally present.
  7. Larger max_tokens (8192) — prevents response truncation mid-section.
  8. Retry logic on every API call — transient rate-limit/network errors no longer silently drop data.
  9. Higher DPI images (250) set in pdf_reader — better readability of dense fund tables.
 10. No fixed section format  — prompts ask for whatever IS present, not a fixed template.
"""

import base64
import json
import time
import re
from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from modules.pdf_reader import get_pdf_page_images

console = Console()

# Pages per batch — keep at 5 when using detail:'high' to avoid token overflows
BATCH_SIZE = 5

# Delay between batch API calls (seconds) — helps with TPM rate limits
BATCH_DELAY = 3

# Max retry attempts on rate-limit / transient errors
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries

# How many pages from the start to treat as Index/TOC for fast lookup
INDEX_SCAN_PAGES = 15


# ── Helpers ───────────────────────────────────────────────────────────────────

def _encode_image(image_bytes: bytes) -> str:
    """Base64-encode image bytes for the OpenAI vision API."""
    return base64.b64encode(image_bytes).decode("utf-8")


def _build_image_content(
    page_images: list[bytes],
    page_texts: list[str] | None,
    page_indices: list[int]
) -> list[dict]:
    """
    Build GPT-4o message content blocks combining:
      - Labelled page images (detail: 'high' for full accuracy)
      - Embedded PDF text alongside each image (if available)

    The text layer gives GPT exact numbers to work from; the image gives layout context.
    """
    content = []
    for img_bytes, p_idx in zip(page_images, page_indices):
        page_num = p_idx + 1
        raw_text = (page_texts[p_idx] if page_texts else "").strip()

        # Label + optional embedded text
        if raw_text:
            label = (
                f"[Page {page_num}]\n"
                f"--- EMBEDDED PDF TEXT (exact, use this for all numbers/values) ---\n"
                f"{raw_text}\n"
                f"--- END EMBEDDED TEXT ---"
            )
        else:
            label = f"[Page {page_num}] (scanned image — no embedded text available)"

        content.append({"type": "text", "text": label})
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{_encode_image(img_bytes)}",
                "detail": "high"  # Full resolution — essential for tables with small numbers
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


def _call_gpt(
    client: OpenAI,
    system: str,
    user_content: list[dict],
    max_tokens: int = 2000,
    model: str = "gpt-4o",
    json_mode: bool = False
) -> str:
    """
    Single GPT call with retry logic.
    Retries up to MAX_RETRIES times on rate-limit (429) or server errors (5xx).
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": max_tokens,
                "temperature": 0
            }
            if json_mode:
                kwargs["response_format"] = { "type": "json_object" }

            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str or "503" in err_str or "500" in err_str:
                if attempt < MAX_RETRIES:
                    console.print(
                        f"[yellow]⚠ Rate limit / server error (attempt {attempt}/{MAX_RETRIES}). "
                        f"Retrying in {RETRY_DELAY}s...[/yellow]"
                    )
                    time.sleep(RETRY_DELAY)
                    continue
            # Non-retriable error — raise immediately
            raise
    raise last_error


def _clean_fund_name(name: str) -> str:
    """Clean up extracted fund names to remove plan variants and ensure deduplication."""
    # Remove common hyphens used for plans (only if followed exactly by plan keywords)
    parts = re.split(r'\s+-\s+(?i:Direct|Regular|Growth|IDCW|Dividend|Bonus|Investment Plan|Savings Plan|Institutional Plan|Retail Plan|Plan)\b', name)
    name = parts[0].strip()
    
    # Remove plan-related suffixes at the end of the string
    name = re.sub(r'(?i)\s+(Direct Plan|Regular Plan|Direct|Regular|Growth|IDCW|Dividend|Investment Plan|Savings Plan)$', '', name).strip()
    
    # NEW: Aggressively strip the word " Plan" from the very end of the string.
    # Ex: "Tata Retirement Savings Fund - Conservative Plan" -> "Tata Retirement Savings Fund - Conservative"
    name = re.sub(r'(?i)\s+Plan$', '', name).strip()
    
    # Sometimes just " - " is left at the end
    if name.endswith('-'):
        name = name[:-1].strip()
        
    return name


# ── Fund Name Extraction ───────────────────────────────────────────────────────

def extract_fund_names(
    client: OpenAI,
    file_path: str,
    page_texts: list[str] | None = None
) -> list[str]:
    """
    Scan all pages in batches and return a deduplicated sorted list of all fund scheme names.
    Uses both image and embedded text for high-confidence identification.
    """
    system_prompt = (
        "You are a financial document parser specializing in mutual fund fact sheets. "
        "Your ONLY job is to identify distinct mutual fund SCHEME names that have a DEDICATED FACT SHEET SECTION "
        "in the provided pages — meaning a section that shows that fund's own NAV, AUM, returns table, "
        "and/or portfolio holdings. "
        "\n\nCRITICAL ACCURACY RULES:"
        "\n1. ONLY include a fund if it has its OWN dedicated section in these pages. "
        "   DO NOT include funds that are merely MENTIONED in passing (e.g. in disclaimers, footnotes, "
        "   SID references, benchmark comparisons, Scheme Information Documents, or 'other funds offered by' lists)."
        "\n2. DO NOT list plan variants as separate funds! "
        "   Examples to IGNORE: '- Direct Plan', '- Regular Plan', '- Growth', '- IDCW', "
        "   '- Investment Plan', '- Savings Plan'. These are options WITHIN a fund."
        "\n3. Extract only the EXACT ROOT scheme name. For example if you see 'SBI Children\\'s Fund - Investment Plan', "
        "   extract ONLY 'SBI Children\\'s Fund'."
        "\n4. Ignore AMC names, section headers, table column labels, footer text, and fund names that only "
        "   appear in disclaimer/legal/reference sections."
        "\n5. If embedded PDF text is provided, use it as the primary source for exact spelling."
        "\nReturn ONLY a JSON object with a single key 'data' containing an array of scheme name strings."
    )
    user_prefix = (
        "From these pages, identify every mutual fund SCHEME that has a DEDICATED FACT SHEET SECTION here. "
        "A dedicated section means the page actually displays that fund's own NAV, AUM, returns, or portfolio data. "
        "Do NOT include funds that only appear in disclaimers, footnotes, SID references, benchmark names, "
        "or sentences like 'units of Sundaram Liquid Fund may be used for...'. "
        "Use the EMBEDDED PDF TEXT (if shown) for exact spelling of fund names. "
        "Strip ANY plan suffixes (like - Direct/Regular/Growth/IDCW/Savings Plan/Investment Plan) — return ONLY the base scheme name. "
        "Return ONLY a JSON object: {\"data\": [\"Scheme Name 1\", \"Scheme Name 2\"]}. "
        "If no scheme names are found, return {\"data\": []}."
    )

    all_names: set[str] = set()

    # OPTIMIZATION: For multi-fund consolidated PDFs, the list of all funds is presented
    # in the Index or Table of Contents (almost always within the first 10-15 pages).
    SEARCH_LIMIT = 15
    scan_texts = page_texts[:SEARCH_LIMIT] if page_texts else None
    
    if page_texts and len(page_texts) > SEARCH_LIMIT:
        console.print(f"[cyan]  ℹ Large document detected ({len(page_texts)} pages). Scanning only the first {SEARCH_LIMIT} pages (Index/TOC) to find fund names.[/cyan]")

    # We consider it a "text-rich" PDF if at least 50% of the pages have text
    text_rich = scan_texts and sum(1 for t in scan_texts if t.strip()) > len(scan_texts) * 0.5

    if text_rich:
        TEXT_BATCH_SIZE = 50
        total_batches = (len(scan_texts) + TEXT_BATCH_SIZE - 1) // TEXT_BATCH_SIZE

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task(f"[yellow]Scanning Index/TOC text for fund names...", total=total_batches)

            for batch_num, start in enumerate(range(0, len(scan_texts), TEXT_BATCH_SIZE)):
                batch_text = scan_texts[start: start + TEXT_BATCH_SIZE]
                combined_text = ""
                for i, text in enumerate(batch_text):
                    if text.strip():
                        combined_text += f"\n--- Page {start + i + 1} ---\n{text}\n"

                if not combined_text.strip():
                    progress.advance(task)
                    continue

                user_content = [
                    {"type": "text", "text": user_prefix},
                    {"type": "text", "text": f"\nEMBEDDED PDF TEXT:\n{combined_text}"}
                ]

                try:
                    raw = _call_gpt(client, system_prompt, user_content, max_tokens=4096, json_mode=True)
                    names = json.loads(raw).get("data", [])
                    for n in names:
                        if isinstance(n, str) and n.strip():
                            cleaned = _clean_fund_name(n)
                            if cleaned:
                                all_names.add(cleaned)
                except Exception as e:
                    console.print(f"[red]⚠ Fast text batch {batch_num + 1} name scan failed: {e}[/red]")

                progress.advance(task)
                if batch_num < total_batches - 1:
                    time.sleep(1)

        return sorted(all_names)

    # Fallback: Scanned PDF / no text layer, use Vision processing
    scan_indices = list(range(min(SEARCH_LIMIT, len(page_texts) if page_texts else 1)))
    scan_images = get_pdf_page_images(file_path, scan_indices)
    
    total_batches = (len(scan_images) + BATCH_SIZE - 1) // BATCH_SIZE

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task(f"[yellow]Scanning images for fund names (vision mode, batches of {BATCH_SIZE})...", total=total_batches)

        for batch_num, start in enumerate(range(0, len(scan_images), BATCH_SIZE)):
            batch_imgs = scan_images[start: start + BATCH_SIZE]
            batch_indices = scan_indices[start: start + BATCH_SIZE]
            user_content = _build_image_content(batch_imgs, scan_texts, batch_indices)
            user_content.insert(0, {"type": "text", "text": user_prefix})

            try:
                raw = _call_gpt(client, system_prompt, user_content, max_tokens=4096, json_mode=True)
                names = json.loads(raw).get("data", [])
                for n in names:
                    if isinstance(n, str) and n.strip():
                        cleaned = _clean_fund_name(n)
                        if cleaned:
                            all_names.add(cleaned)
            except Exception as e:
                console.print(f"[red]⚠ Batch {batch_num + 1} name scan failed: {e}[/red]")

            progress.advance(task)
            if batch_num < total_batches - 1:
                time.sleep(BATCH_DELAY)

    return sorted(all_names)


# ── Fund Page Locator ─────────────────────────────────────────────────────────

def _index_page_lookup(fund_name: str, page_texts: list[str]) -> list[int]:
    """
    Tier-1 (ZERO API calls): Regex-parse the Index/TOC pages (first INDEX_SCAN_PAGES)
    to extract the page number(s) listed for fund_name.

    Handles TWO formats found in real AMC fact sheets:

    Format A — same line (plain TOC):
        'Tata Small Cap Fund ............... 22'

    Format B — consecutive separate lines (table cell extracted by PyMuPDF):
        'Tata Small Cap Fund'    <- line N
        '22'                     <- line N+1  (separate table cell)

    Format B uses STRICT normalized equality (not fuzzy regex) so that:
      - 'Tata Large & Mid Cap Fund' does NOT match 'Tata Large Cap Fund'
      - 'Tata Nifty Midcap 150 ...' does NOT match 'Tata Mid Cap Fund'

    Also handles page ranges like '65 - 66' -> captures ALL pages in the range.
    Returns a list of 0-based page indices, or [] if not found.
    """
    words = re.findall(r'[\w&]+', fund_name, re.IGNORECASE)
    if not words:
        return []

    name_pattern = r'.*?'.join(re.escape(w) for w in words)

    # Format A: fund name AND page number on the same line
    # Now captures optional range end: '22' or '65 - 66'
    same_line_re = re.compile(rf'(?i){name_pattern}.*?\b(\d{{1,3}})\s*(?:-\s*(\d{{1,3}}))?\b')

    # Format B step 1: quick pre-filter — line must contain the fund name words at all
    name_only_re = re.compile(rf'(?i){name_pattern}')

    # Format B step 2: standalone number / range line e.g. '22' or '65 - 66'
    standalone_num_re = re.compile(r'^\s*(\d{1,3})\s*(?:-\s*(\d{1,3}))?\s*$')

    found_pages: set[int] = set()
    index_texts = page_texts[:INDEX_SCAN_PAGES]

    def _is_valid_page(n: int) -> bool:
        return INDEX_SCAN_PAGES < n <= len(page_texts)

    def _add_range(start: int, end: int | None) -> None:
        """Add all 0-based indices in the page range [start, end] that are valid."""
        stop = end if (end and end >= start) else start
        for pg in range(start, stop + 1):
            if _is_valid_page(pg):
                found_pages.add(pg - 1)

    def _normalize(s: str) -> str:
        """Lowercase, strip special chars/punctuation, collapse whitespace."""
        return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', s).lower()).strip()

    norm_fund = _normalize(fund_name)

    for text in index_texts:
        lines = [ln.strip() for ln in text.splitlines()]

        for i, line in enumerate(lines):
            if not line:
                continue

            # ── Format A: name + page number (+ optional range end) on same line ──
            m = same_line_re.search(line)
            if m:
                start_pg = int(m.group(1))
                end_pg = int(m.group(2)) if m.group(2) else None
                _add_range(start_pg, end_pg)
                continue

            # ── Format B: name on line N, number/range on line N+K ────────────
            if name_only_re.search(line) and _normalize(fund_name) == _normalize(line):
                for lookahead_idx in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[lookahead_idx]
                    m_num = standalone_num_re.match(next_line)
                    if m_num:
                        start_pg = int(m_num.group(1))
                        end_pg = int(m_num.group(2)) if m_num.group(2) else None
                        _add_range(start_pg, end_pg)
                        break  # number found, stop lookahead

    return sorted(found_pages)


def _text_only_gpt_lookup(
    client: OpenAI,
    fund_name: str,
    candidate_indices: list[int],
    page_texts: list[str]
) -> list[int]:
    """
    Tier-2 (Text-only, gpt-4o-mini, NO images): Ask GPT which of the candidate pages
    contain the dedicated fact sheet section — using only the embedded text layer.
    Much faster and cheaper than vision; typically 1 API call for up to 30 pages.
    A fund's section may span MULTIPLE consecutive pages — all of them are returned.
    """
    system_prompt = (
        "You are a document navigation assistant for mutual fund fact sheets. "
        "Given embedded text from candidate pages, identify ALL page numbers that belong to "
        "the DEDICATED fact sheet section for the named fund. "
        "A fund's fact sheet section often spans 2 or even 3 consecutive pages — include EVERY page "
        "that contains this fund's own NAV, AUM, returns table, portfolio holdings, or sector breakdown. "
        "A page that only lists the fund in an index, disclaimer, or footer does NOT qualify. "
        "Return ONLY a JSON object with a single key 'data' containing an array of 1-based page numbers (integers)."
    )

    # Build a combined text block of all candidate pages
    combined = ""
    for idx in candidate_indices:
        text = page_texts[idx].strip() if idx < len(page_texts) else ""
        if text:
            combined += f"\n\n--- Page {idx + 1} ---\n{text}"

    if not combined.strip():
        return []

    user_content = [
        {
            "type": "text",
            "text": (
                f"Which of these pages contain the DEDICATED fact sheet section for: '{fund_name}'?\n"
                f"IMPORTANT: A fund section can span MULTIPLE consecutive pages (e.g. page 22 AND 23). "
                f"Return ALL pages that are part of this fund's dedicated section (NAV, AUM, returns, portfolio, sector breakdown).\n"
                f"Do NOT include pages that only mention the fund in an index or footer.\n"
                f"Return ONLY a JSON object: {{\"data\": [22, 23]}}. If none, return {{\"data\": []}}.\n\n"
                f"{combined}"
            )
        }
    ]

    try:
        raw = _call_gpt(
            client, system_prompt, user_content,
            max_tokens=200,
            model="gpt-4o-mini",
            json_mode=True
        )
        page_nums = json.loads(raw).get("data", [])
        return sorted(
            p - 1 for p in page_nums
            if isinstance(p, int) and p >= 1 and p - 1 < len(page_texts)
        )
    except Exception as e:
        console.print(f"[yellow]⚠ Text-only GPT lookup failed: {e}[/yellow]")
        return []


def find_fund_pages(
    client: OpenAI,
    file_path: str,
    fund_name: str,
    page_texts: list[str] | None = None
) -> list[int]:
    """
    3-Tier fast page locator — finds which page(s) contain the fund's dedicated fact sheet.

    Tier 1 — Index/TOC regex (0 API calls, <1 second)
    Tier 2 — Text-only gpt-4o-mini scan (~2-5 seconds, 1 API call)
    Tier 3 — Vision fallback (~30 seconds, 1-2 API calls)
    """
    is_large_doc = page_texts and len(page_texts) > INDEX_SCAN_PAGES

    # ── Tier 1: Index/TOC regex lookup (zero API calls) ──────────────────────
    if page_texts and is_large_doc:
        console.print(f"[cyan]  ℹ [Tier 1] Scanning Index/TOC for '{fund_name}'...[/cyan]")
        index_pages = _index_page_lookup(fund_name, page_texts)
        if index_pages:
            # Expand: also include immediately following pages that still contain
            # the fund name, to catch multi-page fund sections the TOC doesn't enumerate.
            expanded = set(index_pages)
            for start_p in index_pages:
                for offset in range(1, 4):          # check up to 3 continuation pages
                    next_p = start_p + offset
                    if next_p >= len(page_texts):
                        break
                    next_text = page_texts[next_p].lower()
                    fund_norm = re.sub(r'\s+', ' ', fund_name.lower()).strip()
                    if fund_norm in next_text:
                        expanded.add(next_p)
                    else:
                        break                       # stop at first page that no longer has the fund
            expanded_sorted = sorted(expanded)
            if len(expanded_sorted) > len(index_pages):
                console.print(
                    f"[green]  ✔ [Tier 1] Index lookup + continuation: page(s) "
                    f"{[p + 1 for p in expanded_sorted]} (0 API calls)[/green]"
                )
            else:
                console.print(f"[green]  ✔ [Tier 1] Index lookup found page(s): {[p + 1 for p in expanded_sorted]} (0 API calls)[/green]")
            return expanded_sorted
        console.print("[yellow]  ⚠ [Tier 1] Index lookup found nothing — falling back to Tier 2.[/yellow]")

    # ── Build candidate list from text pre-filter ─────────────────────────────
    text_matched_pages: set[int] = set()
    if page_texts:
        fund_normalized = re.sub(r'\s+', ' ', fund_name.lower()).strip()
        for idx, text in enumerate(page_texts):
            text_normalized = re.sub(r'\s+', ' ', text.lower()).strip()
            if fund_normalized in text_normalized:
                text_matched_pages.add(idx)

    if text_matched_pages:
        console.print(f"[cyan]  ℹ Text-layer pre-match: {len(text_matched_pages)} page(s) contain the fund name.[/cyan]")

    candidate_indices = sorted(
        idx for idx in text_matched_pages
        if not is_large_doc or idx >= INDEX_SCAN_PAGES
    ) if text_matched_pages else list(range(INDEX_SCAN_PAGES if is_large_doc else 0, len(page_texts) if page_texts else 1))

    if len(candidate_indices) > 40:
        console.print(f"[yellow]  ⚠ {len(candidate_indices)} candidates — capping at 40 for speed.[/yellow]")
        candidate_indices = candidate_indices[:40]

    # ── Tier 2: Text-only gpt-4o-mini lookup (1 API call, no images) ─────────
    if page_texts:
        console.print(f"[cyan]  ℹ [Tier 2] Text-only gpt-4o-mini scan on {len(candidate_indices)} candidate page(s)...[/cyan]")
        tier2_pages = _text_only_gpt_lookup(client, fund_name, candidate_indices, page_texts)
        if tier2_pages:
            console.print(f"[green]  ✔ [Tier 2] Text-only lookup found page(s): {[p + 1 for p in tier2_pages]}[/green]")
            return tier2_pages
        console.print("[yellow]  ⚠ [Tier 2] Text-only GPT found nothing — falling back to Tier 3 vision.[/yellow]")

    # ── Tier 3: Vision fallback (images, ONLY on narrowed candidates) ─────────
    vision_targets = candidate_indices if candidate_indices else list(range(len(page_texts) if page_texts else 1))
    console.print(f"[yellow]  ℹ [Tier 3] Vision scan on {len(vision_targets)} page(s)...[/yellow]")

    system_prompt = (
        "You are a document navigation assistant for mutual fund fact sheets. "
        "Identify ALL pages that belong to the DEDICATED FACT SHEET SECTION for the named fund. "
        "A fund's fact sheet section often spans 2 or even 3 consecutive pages. "
        "Include every page showing this fund's NAV, portfolio details, returns table, AUM, sector breakdown, or holdings. "
        "Return ONLY a JSON object with a single key 'data' containing an array of 1-based page numbers (integers)."
    )
    user_prefix = (
        f"Which of these pages contain the DEDICATED fact sheet section for: '{fund_name}'? "
        "IMPORTANT: A fund section can span MULTIPLE consecutive pages — return ALL of them. "
        "Include every page that shows this fund's NAV, AUM, returns, portfolio, sector breakdown, or holdings. "
        "Return ONLY a JSON object: {\"data\": [22, 23]}. If none, return {\"data\": []}."
    )

    relevant_pages: set[int] = set()
    vision_images = get_pdf_page_images(file_path, vision_targets)
    total_batches = (len(vision_targets) + BATCH_SIZE - 1) // BATCH_SIZE

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task(f"[yellow][Tier 3] Vision scan: {len(vision_targets)} page(s)...", total=total_batches)

        for batch_num in range(total_batches):
            batch_indices = vision_targets[batch_num * BATCH_SIZE: (batch_num + 1) * BATCH_SIZE]
            batch_imgs = vision_images[batch_num * BATCH_SIZE: (batch_num + 1) * BATCH_SIZE]
            
            user_content = _build_image_content(batch_imgs, page_texts, batch_indices)
            user_content.insert(0, {"type": "text", "text": user_prefix})

            try:
                raw = _call_gpt(client, system_prompt, user_content, max_tokens=300, json_mode=True)
                page_nums = json.loads(raw).get("data", [])
                relevant_pages.update(p - 1 for p in page_nums if isinstance(p, int) and p >= 1)
            except Exception as e:
                console.print(f"[red]⚠ Vision batch {batch_num + 1} failed: {e}[/red]")

            progress.advance(task)
            if batch_num < total_batches - 1:
                time.sleep(BATCH_DELAY)

    if not relevant_pages and text_matched_pages:
        return sorted(
            idx for idx in text_matched_pages
            if not is_large_doc or idx >= INDEX_SCAN_PAGES
        ) or sorted(text_matched_pages)

    return sorted(relevant_pages)


# ── Fund Detail Extraction ─────────────────────────────────────────────────────

def extract_fund_details(
    client: OpenAI,
    file_path: str,
    fund_name: str,
    page_texts: list[str] | None = None
) -> str:
    """
    High-accuracy two-pass extraction:
      Pass 1 — locate pages containing this fund's data (using text-layer + vision).
      Pass 2 — extract ALL data from those pages using hybrid image+text approach.

    Anti-hallucination: GPT is explicitly told to ONLY use printed values, never infer or fill in.
    """
    # Pass 1: locate relevant pages (3-tier: Index lookup → text-only GPT → vision)
    console.print(f"\n[yellow]⟳ Pass 1/2 — Locating pages for '{fund_name}'...[/yellow]")
    relevant_indices = find_fund_pages(client, file_path, fund_name, page_texts)

    if relevant_indices:
        console.print(f"[green]✔ Found on pages:[/green] {[i + 1 for i in relevant_indices]}")
        target_indices = relevant_indices
    else:
        console.print("[yellow]⚠ Could not locate specific pages; scanning all pages.[/yellow]")
        target_indices = list(range(len(page_texts) if page_texts else 1))

    target_images = get_pdf_page_images(file_path, target_indices)

    # Pass 2: extract — use ALL relevant pages in one call if possible, else batch
    console.print(f"\n[yellow]⟳ Pass 2/2 — Extracting data from {len(target_images)} page(s)...[/yellow]")

    system_prompt = (
        "You are an expert mutual fund analyst performing data extraction with forensic accuracy. "
        "Your rule #1: NEVER invent, estimate, or assume any value. "
        "If a value is not explicitly printed on these pages, write 'Not available'. "
        "Rule #2: Use the EMBEDDED PDF TEXT as your primary source of truth for all numbers, "
        "percentages, names, and dates — it is the exact machine-readable text from the PDF. "
        "Rule #3: Use the images to understand layout, tables, and structure; cross-verify "
        "numbers from the image against the embedded text. If they differ, prefer the embedded text. "
        "Rule #4: The document format will vary by AMC and by month — do not assume any fixed layout. "
        "Discover all sections dynamically from whatever is present. "
        "Rule #5: Output well-structured Markdown. Do not add commentary or disclaimers."
    )

    extraction_prompt = f"""Extract ALL data for fund: **{fund_name}** from the pages provided.

STRICT RULES:
- Use EMBEDDED PDF TEXT (shown above each page image) as the PRIMARY source for all values.
- The image is your secondary source to understand table structure and visual layout.
- ONLY output values that are LITERALLY PRESENT in these pages. Never fill in, estimate, or hallucinate.
- If a field is not present, write exactly: `Not available`
- Do NOT infer fund type, category, or any field — read it from the page or mark it as Not available.
- Preserve exact numbers: NAV, AUM, returns, percentages — copy them exactly as printed.
- Discover sections dynamically — every fact sheet has different sections; extract whatever IS shown.

---

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

Note:
- If a section's data is absent, write "Not available".
- Never invent or assume values — only extract what is explicitly shown.
- For tables, use proper Markdown table syntax.
"""

    # If many target pages, process in batches and concatenate
    if len(target_images) <= BATCH_SIZE:
        user_content = _build_image_content(target_images, page_texts, target_indices)
        user_content.insert(0, {"type": "text", "text": extraction_prompt})
        result = _call_gpt(client, system_prompt, user_content, max_tokens=8192)
        return result
    else:
        # Multi-batch: extract per sub-batch, then merge with GPT
        console.print(f"[yellow]  ℹ Many pages ({len(target_images)}), extracting in sub-batches...[/yellow]")
        batch_results = []
        sub_total = (len(target_images) + BATCH_SIZE - 1) // BATCH_SIZE

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("[yellow]Extracting data sub-batches...", total=sub_total)
            for b_num, b_start in enumerate(range(0, len(target_images), BATCH_SIZE)):
                sub_imgs = target_images[b_start: b_start + BATCH_SIZE]
                sub_indices = target_indices[b_start: b_start + BATCH_SIZE]

                sub_content = _build_image_content(sub_imgs, page_texts, sub_indices)
                sub_prompt = (
                    f"Extract ALL data for '{fund_name}' from these pages ONLY.\n"
                    f"Copy values EXACTLY as printed. Do NOT hallucinate or fill in missing values.\n"
                    f"Use the EMBEDDED PDF TEXT as primary source. Format as structured Markdown.\n\n"
                    f"{extraction_prompt}"
                )
                sub_content.insert(0, {"type": "text", "text": sub_prompt})

                try:
                    batch_md = _call_gpt(client, system_prompt, sub_content, max_tokens=8192)
                    batch_results.append(batch_md)
                except Exception as e:
                    console.print(f"[red]⚠ Sub-batch {b_num + 1} extraction failed: {e}[/red]")

                progress.advance(task)
                if b_num < sub_total - 1:
                    time.sleep(BATCH_DELAY)

        if not batch_results:
            return "# Extraction Failed\n\nAll sub-batches failed. Please try again."

        if len(batch_results) == 1:
            return batch_results[0]

        # Merge sub-batch results with GPT
        console.print("[yellow]  ⟳ Merging sub-batch results...[/yellow]")
        merge_prompt = (
            f"You have received partial extractions for the fund '{fund_name}' from different page batches. "
            f"Merge them into ONE complete, well-structured Markdown document. "
            f"Rules:\n"
            f"- Remove duplicates but keep ALL unique data points.\n"
            f"- If the same field appears in multiple batches, use the most complete/detailed version.\n"
            f"- Do NOT add any information not present in the inputs below.\n"
            f"- Preserve all exact numbers and values.\n\n"
            + "\n\n---BATCH SEPARATOR---\n\n".join(batch_results)
        )
        merge_content = [{"type": "text", "text": merge_prompt}]
        return _call_gpt(client, system_prompt, merge_content, max_tokens=8192)

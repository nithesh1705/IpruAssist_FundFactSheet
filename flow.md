# Fund Fact Sheet Extractor Pipeline Flow

This document outlines the step-by-step pseudo-code logic used by the system to process PDF mutual fund fact sheets. The pipeline dynamically adapts its strategy depending on whether the uploaded document is a "Single Fund Fact Sheet" (small PDF) or a "Consolidated Multiple Fund Booklet" (large PDF).

---

## 1. Single Fund File (Small PDF: <= 15 Pages)

In a small PDF, there is usually no Table of Contents, and the document is entirely focused on one (or a few) funds.

**Step 1. Read PDF & Extract Text**
- *Action:* Extract embedded text from every page using PyMuPDF.
- *Reason:* We use this exact digital text layer to feed the AI, prioritizing it over OCR to guarantee 100% accurate numbers.

**Step 2. Identify Valid Fund Names (STRICT Mode)**
- *Action:* Send the extracted text to GPT-4o with a **STRICT** prompt.
- *Prompt Logic:* "Only extract the fund name if you see its dedicated fact sheet data (NAV, Portfolio, AUM). Ignore any funds merely mentioned in disclaimers or footers."
- *Reason:* Prevents false positives (e.g., "Liquid Fund" picked up from a cash-allocation disclaimer).

**Step 3. User Selection**
- *Action:* Present the unique, verified list of funds to the user via the terminal.
- *Reason:* Allows the user to select exactly which fund data they want to extract.

**Step 4. Locate Target Pages (Fast Verification)**
- *Action:* Search the PDF text for the selected fund's name to build a "Candidate Pool" of pages.
- *Action (Tier 2):* Send the text of only these candidate pages to `gpt-4o-mini`.
- *Prompt Logic:* "Which of these specific pages contain the actual dedicated section for this fund?"
- *Reason:* Cheaply and quickly drops pages where the fund is mentioned in passing, avoiding expensive image API calls later.

**Step 5. Final Extraction (Hybrid Vision + Text)**
- *Action:* Render the confirmed target pages as high-resolution images (250 DPI).
- *Action:* Send BOTH the images and the exact embedded text to GPT-4o.
- *Prompt Logic:* "Extract AUM variants, sort Top 5 stock/sector holdings mathematically in descending order, extract rating pie charts via vision, and copy legal fields (Exit Load) verbatim."
- *Reason:* Images provide structure/layout awareness (like pie chart colors), while embedded text provides 100% accuracy for values.

**Step 6. Save Output**
- *Action:* Strip markdown formatting blocks and save the final report to `/Output/<Fund_Name>_<ddMMyyyy>_<hhmmss>.md`.

---

## 2. Multiple Fund File (Large PDF: > 15 Pages)

Consolidated fact sheets (like a 200-page monthly booklet) require an index-first approach to avoid scanning massive amounts of data unnecessarily.

**Step 1. Read PDF & Extract Text**
- *Action:* Extract embedded text from all pages using PyMuPDF.
- *Reason:* Text extraction is highly efficient and provides the foundation for our zero-API lookup strategies.

**Step 2. Identify Valid Fund Names (TOC PERMISSIVE Mode)**
- *Action:* Slice only the first 15 pages (acting as the Index/TOC region) and send to GPT-4o with a **PERMISSIVE** prompt.
- *Prompt Logic:* "This is a Table of Contents. Extract every single fund name listed here."
- *Reason:* In an index, funds do not have their "dedicated fact sheet numbers" printed next to them, so we must be permissive to capture the master list.

**Step 3. User Selection**
- *Action:* Present the 50+ extracted fund names in the terminal menu.
- *Reason:* The user picks the single fund out of the entire booklet that they want to process.

**Step 4. Locate Target Pages (3-Tier Funnel)**
- *Action (Tier 1 - Regex):* Parse the first 15 pages locally using Python Regular Expressions to find the selected fund name and its mapped page number (e.g., "SBI MNC Fund ........ 36"). 
- *Action (Tier 1 - Expand):* Predict continuation pages (e.g., check pages 37, 38 to see if the fund name continues) and add all to a "Candidate Pool". Zero API calls used.
- *Action (Text Pre-match):* Do a lightweight string match across the entire PDF and add any hits to the Candidate Pool.
- *Action (Tier 2 - Verification):* Pass the Candidate Pool text to `gpt-4o-mini` to definitively verify and filter which pages contain the dedicated section.
- *Reason:* Rapidly pinpoints a 2-page fact sheet inside a 200-page PDF with incredible accuracy in seconds, primarily using local regex speed.

**Step 5. Final Extraction (Hybrid Vision + Text)**
- *Action:* Take the exactly verified target pages (usually 1 to 3 pages) and render them as images.
- *Action:* Issue a highly detailed prompt to GPT-4o combining the images and text for the chosen fund. 
- *Reason:* Focuses the heavy, expensive vision extraction strictly on the isolated pages. GPT parses tables, sorts values strictly downwards, and matches pie chart legend colors.

**Step 6. Save Output**
- *Action:* Format cleanly and save as markdown using the timestamped naming convention.

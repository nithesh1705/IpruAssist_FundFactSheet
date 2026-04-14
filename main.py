"""
FundFactSheet Extractor — Main Entry Point

Usage:
    python main.py
    python main.py --file "Documents/MyFactSheet.pdf"

The tool reads a mutual fund fact sheet PDF, lists all fund schemes found,
lets the user pick one, and generates a structured Markdown report in /Output.
"""

import os
import sys
import argparse

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import print as rprint

from modules.pdf_reader import is_valid_pdf, get_pdf_page_images, get_pdf_page_texts, get_pdf_filename_stem
from modules.ai_extractor import extract_fund_names, extract_fund_details
from modules.output_writer import save_markdown

# ── initialise ───────────────────────────────────────────────────────────────
load_dotenv()
console = Console()


def get_openai_client() -> OpenAI:
    """Create and return an authenticated OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        console.print("[bold red]✗ OPENAI_API_KEY is not set in your .env file.[/bold red]")
        sys.exit(1)
    return OpenAI(api_key=api_key)


def prompt_for_file_path() -> str:
    """Prompt the user to enter a PDF file path interactively."""
    return Prompt.ask("\n[bold cyan]Enter the path to the Fund Fact Sheet PDF[/bold cyan]").strip().strip('"')


def select_fund(fund_names: list[str]) -> str:
    """Display a numbered list of funds and return the one the user selects."""
    table = Table(title="Funds Found in Document", show_lines=True)
    table.add_column("#", style="bold yellow", justify="right")
    table.add_column("Fund Name", style="bold white")

    for idx, name in enumerate(fund_names, start=1):
        table.add_row(str(idx), name)

    console.print(table)

    while True:
        choice = Prompt.ask(
            f"\n[bold cyan]Select a fund (1-{len(fund_names)})[/bold cyan]"
        )
        if choice.isdigit() and 1 <= int(choice) <= len(fund_names):
            return fund_names[int(choice) - 1]
        console.print(f"[red]Please enter a number between 1 and {len(fund_names)}.[/red]")


def main():
    # ── argument parsing ──────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="Extract fund data from a Fact Sheet PDF.")
    parser.add_argument("--file", "-f", help="Path to the input PDF file", default=None)
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold green]FundFactSheet Extractor[/bold green]\n"
        "[dim]Powered by GPT-4o · Supports any AMC format[/dim]",
        border_style="green"
    ))

    # ── Step 1-2: Get and validate PDF path ───────────────────────────────────
    file_path = args.file if args.file else prompt_for_file_path()

    if not is_valid_pdf(file_path):
        console.print(f"[bold red]✗ Invalid input:[/bold red] '{file_path}' is not a valid PDF file.")
        sys.exit(1)

    console.print(f"\n[green]✔ PDF validated:[/green] {file_path}")
    filename_stem = get_pdf_filename_stem(file_path)

    # ── Step 3: Extract text layer ────────────────
    console.print("\n[yellow]⟳ Extracting embedded text layer...[/yellow]", end=" ")
    page_texts = get_pdf_page_texts(file_path)
    text_pages_count = sum(1 for t in page_texts if t.strip())
    console.print(
        f"[green]{text_pages_count}/{len(page_texts)} page(s) have embedded text "
        f"(used as primary accuracy source).[/green]"
    )

    # ── Initialise OpenAI client ──────────────────────────────────────────────
    client = get_openai_client()

    # ── Step 4: Extract fund names via GPT-4o ─────────────────────────────────
    console.print("\n[yellow]⟳ Asking GPT-4o to identify all funds in the document...[/yellow]")
    try:
        fund_names = extract_fund_names(client, file_path, page_texts)
    except Exception as e:
        console.print(f"[bold red]✗ Failed to extract fund names:[/bold red] {e}")
        sys.exit(1)

    if not fund_names:
        console.print("[bold red]✗ No fund names could be identified in this document.[/bold red]")
        sys.exit(1)

    console.print(f"[green]✔ Found {len(fund_names)} fund(s).[/green]")

    # ── Step 5: User selects a fund ───────────────────────────────────────────
    selected_fund = select_fund(fund_names)
    console.print(f"\n[bold green]✔ Selected:[/bold green] {selected_fund}")

    # ── Step 6: Extract detailed data and save Markdown ───────────────────────
    console.print(f"\n[yellow]⟳ Extracting detailed data for '{selected_fund}'...[/yellow]")
    try:
        markdown_content = extract_fund_details(client, file_path, selected_fund, page_texts)
    except Exception as e:
        console.print(f"[bold red]✗ Failed to extract fund details:[/bold red] {e}")
        sys.exit(1)

    output_path = save_markdown(filename_stem, markdown_content)
    console.print(f"\n[bold green]✔ Report saved:[/bold green] {output_path}")
    console.print(Panel.fit(
        f"[bold white]Output:[/bold white] {output_path}",
        border_style="green",
        title="Done"
    ))


if __name__ == "__main__":
    main()

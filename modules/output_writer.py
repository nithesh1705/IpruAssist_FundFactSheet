"""
Output writer module: saves the AI-generated Markdown to the /Output folder.
"""

import os


OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Output")


def save_markdown(filename_stem: str, markdown_content: str) -> str:
    """
    Write markdown_content to Output/<filename_stem>.md.
    Returns the full path of the saved file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{filename_stem}.md")

    # Strip markdown code block wrappers if GPT included them
    content_stripped = markdown_content.strip()
    if content_stripped.startswith("```"):
        lines = content_stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines.pop(0)
        if lines and lines[-1].startswith("```"):
            lines.pop(-1)
        content_stripped = "\n".join(lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content_stripped)

    return output_path

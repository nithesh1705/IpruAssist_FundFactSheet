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

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return output_path

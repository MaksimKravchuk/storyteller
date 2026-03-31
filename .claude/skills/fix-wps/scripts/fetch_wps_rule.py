"""Fetch WPS rule documentation from wemake-python-styleguide docs.

Parses the readthedocs HTML to extract violation details including
reasoning, solution, and code examples for a given WPS code.
"""

import re
import sys
import urllib.request


WPS_CATEGORIES = {
    range(0, 100): "system",
    range(100, 200): "naming",
    range(200, 300): "complexity",
    range(300, 400): "consistency",
    range(400, 500): "best_practices",
    range(500, 600): "refactoring",
    range(600, 700): "oop",
}

BASE_URL = "https://wemake-python-styleguide.readthedocs.io/en/latest/pages/usage/violations"


def get_category(code: int) -> str:
    for code_range, category in WPS_CATEGORIES.items():
        if code in code_range:
            return category
    raise ValueError(f"Unknown WPS code range: {code}")


def html_to_markdown(html: str) -> str:
    """Convert violation HTML block to readable markdown."""

    # Extract and replace code blocks first
    def replace_highlight(match: re.Match) -> str:
        code = re.sub(r"<[^>]+>", "", match.group(1))
        code = code.replace("&lt;", "<").replace("&gt;", ">")
        code = code.replace("&amp;", "&").replace("&#39;", "'")
        return f"\n```python\n{code.strip()}\n```\n"

    text = re.sub(
        r'<div class="highlight[^"]*"[^>]*>\s*<div class="highlight">\s*<pre>(.*?)</pre>\s*</div>\s*</div>',
        replace_highlight,
        html,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"<pre[^>]*>(.*?)</pre>",
        replace_highlight,
        text,
        flags=re.DOTALL,
    )

    # Remove nested py attribute blocks (full_code, summary metadata)
    text = re.sub(r'<dl class="py attribute">.*?</dl>', "", text, flags=re.DOTALL)

    # Remove version info divs
    text = re.sub(r'<div class="version\w+">\s*<p>.*?</p>\s*</div>', "", text, flags=re.DOTALL)

    # Convert inline code
    text = re.sub(r"<code[^>]*>(.*?)</code>", lambda m: "`" + re.sub(r"<[^>]+>", "", m.group(1)) + "`", text)

    # Convert dt/dd pairs to bold labels
    text = re.sub(
        r"<dt>([^<]+)</dt>\s*<dd>(.*?)</dd>",
        lambda m: f"\n**{m.group(1)}** {re.sub(r'<[^>]+>', '', m.group(2)).strip()}\n",
        text,
        flags=re.DOTALL,
    )

    # Convert remaining tags
    text = re.sub(r"</?p>", "\n", text)
    text = re.sub(r"</?li>", "\n- ", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)

    # Decode entities
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&amp;", "&").replace("&quot;", '"')
    text = text.replace("&#39;", "'").replace("&nbsp;", " ")
    text = text.replace("\u00b6", "")

    # Clean up whitespace
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_rule(code_str: str) -> str:
    code_str = code_str.strip().upper().replace("WPS", "")
    try:
        code = int(code_str)
    except ValueError:
        return f"Error: '{code_str}' is not a valid WPS code number."

    try:
        category = get_category(code)
    except ValueError as exc:
        return str(exc)

    url = f"{BASE_URL}/{category}.html"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
    except Exception as exc:
        return f"Error fetching {url}: {exc}"

    # Split HTML into violation blocks by <dl class="py class">
    # Each violation starts with <dl class="py class"> and ends before the next one
    block_starts = [m.start() for m in re.finditer(r'<dl class="py class">', html)]

    target_pattern = rf"WPS{code}\b"

    for i, start in enumerate(block_starts):
        end = block_starts[i + 1] if i + 1 < len(block_starts) else len(html)
        block = html[start:end]

        if not re.search(target_pattern, block):
            continue

        # Extract class name from dt
        name_match = re.search(
            r'<span class="sig-name descname"><span class="pre">([^<]+)</span>',
            block,
        )
        class_name = name_match.group(1) if name_match else "Unknown"

        # Extract the <dd> content
        dd_match = re.search(r"<dd>(.*)", block, re.DOTALL)
        if not dd_match:
            continue

        dd_content = dd_match.group(1)
        # Trim at the closing </dd></dl> of the outer block
        # We need to find the right </dd></dl> - it's the last one before end
        outer_close = dd_content.rfind("</dd></dl>")
        if outer_close > 0:
            dd_content = dd_content[:outer_close]

        markdown = html_to_markdown(dd_content)
        return f"# WPS{code} -- {class_name} ({category})\n\nSource: {url}\n\n{markdown}"

    return f"WPS{code} not found on {url}. The rule may not exist or may have been removed."


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_wps_rule.py <WPS_CODE>")
        print("Example: python fetch_wps_rule.py WPS301")
        print("Example: python fetch_wps_rule.py 301")
        sys.exit(1)

    result = fetch_rule(sys.argv[1])
    print(result)

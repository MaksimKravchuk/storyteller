"""Consumer-side guard: the live stream preview in ``app.js`` agrees with the server renderer.

While Narrator prose streams, the web client previews it with ``streamingHTML``,
a JS port of ``formatting.markdown_render``'s inline subset. These tests run that
function from the shipped ``app.js`` under node, so the preview cannot drift from
the final HTML that replaces it or leak half-typed markers mid-stream.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import allure
import pytest

from formatting.markdown_render import to_html

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
    pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed"),
]

_APP_JS = Path(__file__).resolve().parents[1] / "interfaces" / "web" / "static" / "app.js"
_ESCAPE_JS = 'const escapeHTML = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");'
_PASSAGE = 'The **harbourmaster** looks up, *rain dripping*. A note reads `_ACCESS_DENIED`. "_Nobody_ sails," he says.'
_COMPLETE = (
    _PASSAGE,
    "**Bold** and *soft* and `sign` and _quiet_",
    "snake_case_name and a _ b",
    "<script>alert(1)</script> & `*literal*`",
)


def _streaming_html(texts: list[str]) -> list[str]:
    source = re.search(r"function streamingHTML[\s\S]*?\n  }\n", _APP_JS.read_text(encoding="utf-8"))
    assert source is not None, "streamingHTML not found in app.js"
    script = "{0}\n{1}\nconsole.log(JSON.stringify({2}.map(streamingHTML)));".format(
        _ESCAPE_JS,
        source.group(0),
        json.dumps(texts),
    )
    node = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(node.stdout)


@allure.story("Streamed turn")
@allure.title("A fully streamed passage previews exactly as the server renders it")
def test_complete_text_matches_server_renderer() -> None:
    expected = [to_html(text).removeprefix("<p>").removesuffix("</p>") for text in _COMPLETE]
    assert _streaming_html(list(_COMPLETE)) == expected


@allure.story("Streamed turn")
@allure.title("No prefix of a streamed passage shows a half-typed marker outside code spans")
def test_prefixes_hide_unpaired_markers() -> None:
    previews = _streaming_html([_PASSAGE[:end] for end in range(1, len(_PASSAGE) + 1)])
    for preview in previews:
        outside_code = re.sub(r"<code>.*?</code>", "", preview)
        assert not re.search(r"[*`]|(?<![A-Za-z0-9_])_(?!\s)", outside_code), preview

#!/usr/bin/env python3
"""Build the Pages patcher as one self-contained downloadable HTML file."""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DEFAULT_OUTPUT = ROOT / "MariosMaskBuilder-web.html"


def require_replace(document: str, old: str, new: str, label: str) -> str:
    if document.count(old) != 1:
        raise SystemExit(f"web release: expected one {label}, found {document.count(old)}")
    return document.replace(old, new)


def build(output: Path) -> None:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    styles = (SITE / "styles.css").read_text(encoding="utf-8")
    main = (SITE / "patcher.js").read_text(encoding="utf-8")
    worker = (SITE / "patcher-worker.js").read_text(encoding="utf-8")
    loader = (SITE / "pkg/marios_mask_builder.js").read_text(encoding="utf-8")
    wasm = (SITE / "pkg/marios_mask_builder_bg.wasm").read_bytes()
    version = json.loads((SITE / "stable.json").read_text(encoding="utf-8"))["version"]

    loader = require_replace(
        loader,
        "        module_or_path = new URL('marios_mask_builder_bg.wasm', import.meta.url);",
        '        throw new Error("Embedded WASM was not supplied");',
        "generated WASM fallback URL",
    )

    worker = require_replace(
        worker,
        'import init, { build_marios_mask } from "./pkg/marios_mask_builder.js";\n\n',
        "",
        "worker loader import",
    )
    encoded_wasm = base64.b64encode(wasm).decode("ascii")
    worker = require_replace(
        worker,
        "  await init();",
        "  const wasmBytes = Uint8Array.from(atob(\""
        + encoded_wasm
        + "\"), (character) => character.charCodeAt(0));\n"
        "  await __wbg_init(wasmBytes);",
        "WASM initialization call",
    )
    worker_source = loader + "\n" + worker

    stable_pattern = re.compile(
        r'const stableVersion = fetch\("stable\.json"\)\n'
        r"  \.then\(\(response\) => response\.json\(\)\)\n"
        r"  \.then\(\(stable\) => stable\.version\)\n"
        r'  \.catch\(\(\) => "latest"\);'
    )
    main, changes = stable_pattern.subn(
        f'const stableVersion = Promise.resolve("{version}");', main
    )
    if changes != 1:
        raise SystemExit(f"web release: expected one stable-version fetch, found {changes}")

    worker_setup = (
        "const standaloneWorkerSource = "
        + json.dumps(worker_source).replace("<", "\\u003c")
        + ";\n"
        "const standaloneWorkerUrl = URL.createObjectURL(\n"
        "  new Blob([standaloneWorkerSource], { type: \"text/javascript\" }),\n"
        ");\n"
        "const worker = new Worker(standaloneWorkerUrl, { type: \"module\" });"
    )
    main = require_replace(
        main,
        'const worker = new Worker(new URL("patcher-worker.js", import.meta.url), { type: "module" });',
        worker_setup,
        "worker construction",
    )

    csp_pattern = re.compile(
        r'<meta\n\s+http-equiv="Content-Security-Policy"\n\s+content="[^"]+"\n\s+>'
    )
    standalone_csp = (
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; script-src \'unsafe-inline\' \'wasm-unsafe-eval\'; '
        "style-src 'unsafe-inline'; worker-src blob:; img-src data: https:; "
        "object-src 'none'; base-uri 'none'; form-action 'none'\">"
    )
    html, changes = csp_pattern.subn(standalone_csp, html)
    if changes != 1:
        raise SystemExit(f"web release: expected one CSP declaration, found {changes}")
    html = require_replace(
        html,
        '    <link rel="stylesheet" href="styles.css">',
        "    <style>\n" + styles + "    </style>",
        "stylesheet link",
    )
    html = require_replace(
        html,
        '    <script src="patcher.js" type="module"></script>',
        "    <script type=\"module\">\n" + main + "    </script>",
        "patcher script",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"web release: wrote {output} ({output.stat().st_size} bytes, v{version})")


def check(path: Path) -> None:
    document = path.read_text(encoding="utf-8")
    required = (
        "Marios-Mask-v",
        "standaloneWorkerSource",
        "marios_mask_builder",
        "Build Mario's Mask",
        "wasm-unsafe-eval",
    )
    for marker in required:
        if marker not in document:
            raise SystemExit(f"web release: missing {marker!r}")
    forbidden = (
        'src="patcher.js"',
        'href="styles.css"',
        'fetch("stable.json")',
        'new URL("patcher-worker.js"',
        'marios_mask_builder_bg.wasm\'',
    )
    for marker in forbidden:
        if marker in document:
            raise SystemExit(f"web release: retained external dependency {marker!r}")
    if path.stat().st_size > 16 * 1024 * 1024:
        raise SystemExit("web release: standalone HTML exceeds 16 MiB")
    print(f"web release: PASS ({path.stat().st_size} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.check:
        check(arguments.output)
    else:
        build(arguments.output)
        check(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

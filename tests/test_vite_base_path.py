"""Die gebauten Asset-Pfade muessen unter einem Unterverzeichnis funktionieren.

Befund 16.08.2026 (GH#1059-Wirkungspruefung): Die App mountet live nicht.

    HTML referenziert   /assets/index-C8FX6KSF.js            -> HTTP 404
    Bundle liegt unter  /apps/atw/assets/index-C8FX6KSF.js   -> HTTP 200, 148 KB

Ursache: vite.config.ts setzt kein `base`. Vite erzeugt dann absolute Pfade
ab Domainwurzel. Die App wird aber unter /apps/atw/ ausgeliefert, der Browser
sucht das Bundle also an der falschen Stelle und rendert nichts.

Warum das lange unbemerkt blieb: /apps/atw/ liefert HTTP 200 mit 330 Bytes
und einem leeren <div id="root">. Jeder HTTP- oder Textpruefer bestaetigt das
als gesund — nur ein echter Browser sieht, dass die App nicht startet. Sie
war sogar an ZWEI URLs als "live" registriert und wurde doppelt als gesund
gezaehlt.

base: "./" (relativ) statt "/apps/atw/" (absolut), weil die App unter zwei
Pfaden erreichbar ist:
    agentic-movers.com/apps/atw/
    apps.agentic-movers.com/atw/
Ein absoluter Basispfad wuerde genau einen davon reparieren und den anderen
festschreiben. Relative Pfade tragen unter beiden.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CONFIG = PROJECT / "vite.config.ts"
DIST_INDEX = PROJECT / "dist" / "index.html"


def test_vite_config_declares_a_base():
    """Ohne base erzeugt Vite absolute Pfade ab Domainwurzel."""
    src = CONFIG.read_text(encoding="utf-8")
    assert re.search(r"\bbase\s*:", src), (
        "vite.config.ts setzt kein 'base'. Die App wird unter /apps/atw/ "
        "ausgeliefert — ohne base sucht der Browser das Bundle unter "
        "/assets/ und findet es nicht (HTTP 404, leeres div#root)."
    )


def test_base_is_relative_not_pinned_to_one_path():
    """Die App ist unter zwei URLs erreichbar — ein absoluter Pfad bricht eine.

    agentic-movers.com/apps/atw/  und  apps.agentic-movers.com/atw/
    """
    src = CONFIG.read_text(encoding="utf-8")
    m = re.search(r"""\bbase\s*:\s*["']([^"']+)["']""", src)
    assert m, "base nicht als String gesetzt"
    base = m.group(1)
    assert base.startswith("."), (
        f"base={base!r} ist absolut. Die App laeuft unter zwei Pfaden; ein "
        "absoluter Basispfad repariert genau einen und schreibt den anderen "
        "fest. './' traegt unter beiden."
    )


def test_built_index_uses_relative_asset_paths():
    """Wirkung statt Konfiguration: das erzeugte HTML muss relativ verweisen.

    Faengt den Fall ab, dass base gesetzt ist, aber ein alter Build im dist/
    liegt — genau die Lage am 16.08. (Build vom 23.07., live ein neuerer).
    """
    if not DIST_INDEX.exists():
        import pytest
        pytest.skip("kein Build vorhanden (dist/index.html fehlt)")
    html = DIST_INDEX.read_text(encoding="utf-8")
    absolute = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
    assert not absolute, (
        f"Build verweist absolut auf {absolute} — unter /apps/atw/ ergibt "
        "das HTTP 404. Neu bauen nach der base-Aenderung: npm run build"
    )


def test_built_index_still_has_a_bundle():
    """Regression: kein Build ohne Skript-Verweis.

    Ein leeres index.html wuerde alle anderen Tests hier bestehen.
    """
    if not DIST_INDEX.exists():
        import pytest
        pytest.skip("kein Build vorhanden")
    html = DIST_INDEX.read_text(encoding="utf-8")
    assert re.search(r'src="[^"]*assets/[^"]+\.js"', html), (
        "kein Bundle-Verweis im gebauten index.html"
    )
    assert 'id="root"' in html, "Mount-Punkt fehlt"

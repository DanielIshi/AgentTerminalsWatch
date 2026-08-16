import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  // Relative Asset-Pfade (Befund 16.08.2026, GH#1059-Wirkungsprüfung).
  //
  // Ohne `base` erzeugt Vite absolute Pfade ab Domainwurzel:
  //     HTML referenziert   /assets/index-*.js            -> HTTP 404
  //     Bundle liegt unter  /apps/atw/assets/index-*.js   -> HTTP 200
  // Die App wird unter einem Unterverzeichnis ausgeliefert, der Browser
  // sucht das Bundle an der Wurzel und rendert nichts.
  //
  // Unbemerkt geblieben, weil /apps/atw/ HTTP 200 mit 330 Bytes und leerem
  // <div id="root"> liefert. Jeder HTTP- oder Textprüfer bestätigt das als
  // gesund — nur ein echter Browser sieht, dass die App nicht startet.
  // Sie war an ZWEI URLs als "live" registriert und doppelt als gesund
  // gezählt.
  //
  // "./" statt "/apps/atw/": die App ist unter zwei Pfaden erreichbar
  //     agentic-movers.com/apps/atw/
  //     apps.agentic-movers.com/atw/
  // Ein absoluter Basispfad repariert genau einen davon und schreibt den
  // anderen fest. Relative Pfade tragen unter beiden.
  base: "./",
  plugins: [react()],
  build: {
    outDir: "dist",
  },
});

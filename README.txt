VESPER KEEP CATALOGUE RELAY AND ENTRY PAGE

The public entry page opens the Vesper Keep player already running on the visitor's own computer. A distributable local-player setup is still being prepared. This service does not sign into Jellyfin, proxy Jellyfin, or stream movies.

Catalogue shares contain only projected title metadata and poster images. Jellyfin passwords, account access and source paths remain outside this service. Provider controls remain in the local connector. Read capabilities are bearer access and must be shared only in the intended instance; this service cannot independently verify VRChat membership.

Start: python shared_catalogue_http.py. PORT defaults to8080. Deploy one process and one instance: temporary shares live in memory. Restart clears shares. Provider lease30seconds; total catalogue/poster budget64MiB; concurrent HTTP requests24. HTTPS termination is required for public use.

GET /health checks readiness. GET /shared/<cap> returns JSON or PNG for image/* Accept. The root serves the entry page. No arbitrary filesystem or URL proxy routes are exposed.

Brand artwork is the original Vesper Keep sigil, copied unchanged. Cinzel is copyright2020 The Cinzel Project Authors, licensed under SIL Open Font License1.1; full license in Cinzel-OFL.txt.

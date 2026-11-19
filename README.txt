VESPER KEEP CATALOGUE RELAY — REVIEW CANDIDATE

Contains only catalogue metadata/poster relay code. No Jellyfin proxy, movie streaming, local files, account sign-in or credentials.
Start: python shared_catalogue_http.py (PORT defaults 8080). Deploy one process/one instance only; connections are RAM-only. Restart clears all shares. Provider heartbeat lease:30 seconds; metadata/posters total budget:64 MiB; maximum concurrent HTTP requests:24. HTTPS termination required for public use.

GET /health is an anonymous service check. /shared/<cap> returns JSON for normal requests or PNG for image/* Accept, matching observed VRChat downloader requests. Read capabilities are bearer access; distribution must occur only in the intended world instance. The service itself does not verify VRChat accounts or instance membership. Provider control remains in the local connector.

This is NOT the finished public player webpage. Do not replace the current site or publish until the provider/menu integration and publication review are complete. No media is included.

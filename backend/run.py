"""
run.py — Development & Production launcher for PriceRadar.

Usage:
    Development : python run.py
    Production  : python run.py --prod
                  (uses Waitress WSGI server — no WinError 10038 risk)
"""

import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PORT = int(os.environ.get("PORT", 5000))

if "--prod" in sys.argv:
    # ── Production: Waitress (Windows-compatible, no socket issues) ──────────
    try:
        from waitress import serve
        from app import app
        print(f"[PriceRadar] Production server starting on http://0.0.0.0:{PORT}")
        serve(app, host="0.0.0.0", port=PORT, threads=8)
    except ImportError:
        print("ERROR: 'waitress' not installed. Run: pip install waitress")
        sys.exit(1)
else:
    # ── Development: Flask with reloader DISABLED (fixes WinError 10038) ────
    from app import app
    print(f"[PriceRadar] Dev server starting on http://127.0.0.1:{PORT}")
    print("[PriceRadar] Note: reloader disabled to prevent WinError 10038 on Windows.")
    print("[PriceRadar] Restart manually after code changes.")
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=True,          # enables Jinja template error pages
        use_reloader=False,  # ← critical fix for WinError 10038
        threaded=True,
    )

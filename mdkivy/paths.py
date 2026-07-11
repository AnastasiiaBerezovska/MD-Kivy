"""Repository-root-relative paths for assets and runtime data.

All asset lookups go through this module so source files can live
anywhere inside the mdkivy package without breaking.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONTS_DIR    = os.path.join(ROOT, "Fonts")
GRAPHICS_DIR = os.path.join(ROOT, "Graphics")

FONT_IMPACT = os.path.join(FONTS_DIR, "Impact.ttf")

# Runtime data (gitignored)
LEADERBOARD_FILE = os.path.join(ROOT, "leaderboard.json")

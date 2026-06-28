"""DB access for the serving layer (Phase 1). The API reads only published
tables (current_view/board_view/digest, store='published'). Phase 0 uses seed."""
from pipeline.db.connection import connect  # re-export the shared helper

__all__ = ["connect"]

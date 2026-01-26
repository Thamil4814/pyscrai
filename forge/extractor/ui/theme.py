"""
PyScrAI Forge Theme - Centralized color palette with semantic tinting.

Color Philosophy:
- Base colors are cyan (#48b0f7) and teal (#4ECDC4) for data/graph elements
- Headers use subtle tints of their semantic color
- Text uses tinted grays for visual hierarchy while maintaining readability
"""

# =============================================================================
# PRIMARY ACCENT COLORS
# =============================================================================
CYAN_PRIMARY = "#48b0f7"       # Main accent, icons, highlights
TEAL_PRIMARY = "#4ECDC4"       # Success, data, relationships
GOLD_PRIMARY = "#3D60C8"       # Warnings, exports, actions
RED_PRIMARY = "#FF6B6B"        # Errors

# =============================================================================
# SECTION HEADERS (Tinted for semantic meaning)
# =============================================================================
HEADER_CYAN = "#A8D4E6"        # Project Management, Analysis, Processing History, Log
HEADER_TEAL = "#A8E6D8"        # Knowledge Graph, Data sections
HEADER_GOLD = "#3D60C8"        # Export, Action sections

# =============================================================================
# TEXT COLORS (Tinted grays for hierarchy)
# =============================================================================
# Brightest - Main titles, important content
TEXT_BRIGHT = "#AFC5D6"
TEXT_BRIGHT_CYAN = "#5FBEDE"   # Title with subtle cyan tint

# Medium - Secondary labels, descriptions
TEXT_MEDIUM = "#6E879B"
TEXT_MEDIUM_CYAN = "#4B7B97"   # Cyan-tinted medium text
TEXT_MEDIUM_TEAL = "#649F97"   # Teal-tinted medium text

# Muted - Tertiary text, placeholders, hints
TEXT_MUTED = "#8A9BA8"
TEXT_MUTED_CYAN = "#8AB4C4"    # Cyan-tinted muted (stat labels)
TEXT_MUTED_TEAL = "#8AC4BE"    # Teal-tinted muted (stat labels)
TEXT_MUTED_GOLD = "#C4B48A"    # Gold-tinted muted

# Subtle - Version text, very low emphasis
TEXT_SUBTLE = "#7A8A96"
TEXT_SUBTLE_CYAN = "#7EB8C4"   # Subtle cyan accent

# =============================================================================
# ICON COLORS
# =============================================================================
ICON_PRIMARY = CYAN_PRIMARY    # Primary action icons
ICON_SECONDARY = "#84AED0"     # Secondary/inactive icons
ICON_MUTED = TEXT_SUBTLE_CYAN  # Very subtle icons (close buttons)

# =============================================================================
# LOG LEVEL COLORS
# =============================================================================
LOG_INFO = CYAN_PRIMARY
LOG_SUCCESS = TEAL_PRIMARY
LOG_WARNING = GOLD_PRIMARY
LOG_ERROR = RED_PRIMARY
LOG_DEBUG = TEXT_MUTED

# =============================================================================
# BACKGROUND COLORS
# =============================================================================
BG_NAV = "#0a0d1f"             # Navigation rail
BG_GRADIENT_START = "#0d1528"  # Main gradient start
BG_GRADIENT_MID = "#0a0f1c"    # Main gradient middle
BG_GRADIENT_END = "#060a12"    # Main gradient end
BG_CARD = "rgba(255,255,255,0.025)"    # Card backgrounds
BG_PANEL = "rgba(255,255,255,0.04)"    # Panel backgrounds
BG_INDICATOR = "rgba(72, 176, 247, 0.15)"  # Processing indicator

# =============================================================================
# BORDER COLORS
# =============================================================================
BORDER_SUBTLE = "rgba(255,255,255,0.06)"   # Very subtle borders
BORDER_LIGHT = "rgba(255,255,255,0.08)"    # Light borders (panels)
BORDER_MEDIUM = "rgba(255,255,255,0.1)"    # Medium borders (cards)
BORDER_DIVIDER = "rgba(255,255,255,0.12)"  # Dividers

# =============================================================================
# STATUS COLORS (for document processing, etc.)
# =============================================================================
STATUS_COMPLETED = TEAL_PRIMARY
STATUS_FAILED = RED_PRIMARY
STATUS_PROCESSING = GOLD_PRIMARY

# =============================================================================
# SEMANTIC UI TOKENS (Use these in shell.py - change colors here only)
# =============================================================================

# --- Text ---
TEXT_TITLE = GOLD_PRIMARY             # Main app title (e.g., "PyScrAI")
TEXT_SUBTITLE = CYAN_PRIMARY          # Secondary title text (e.g., version info)
TEXT_SECTION_HEADER = GOLD_PRIMARY    # Section headers (e.g., "Project Management", "Analysis")
TEXT_LABEL = TEXT_MUTED_CYAN          # Form labels, dropdown labels
TEXT_VALUE = TEAL_PRIMARY             # Values in dropdowns, stats
TEXT_PLACEHOLDER = TEXT_MUTED         # Placeholder/empty state text

# --- Buttons ---
BUTTON_TEXT_ACTIVE = CYAN_PRIMARY     # Active/enabled button text
BUTTON_TEXT_DISABLED = RED_PRIMARY    # Disabled button text
BUTTON_ICON_ACTIVE = CYAN_PRIMARY     # Active button icons
BUTTON_ICON_DISABLED = TEXT_MUTED     # Disabled button icons

# --- Stats Cards ---
STAT_VALUE = TEXT_BRIGHT              # The numeric value (e.g., "0")
STAT_LABEL_PRIMARY = GOLD_PRIMARY     # Primary stat label (e.g., "Entities")
STAT_LABEL_SECONDARY = TEAL_PRIMARY   # Secondary stat label (e.g., "Relations")
STAT_ICON_PRIMARY = CYAN_PRIMARY      # Icon for primary stats
STAT_ICON_SECONDARY = TEAL_PRIMARY    # Icon for secondary stats

# --- Dropdowns ---
DROPDOWN_LABEL = TEXT_MUTED           # Dropdown field label
DROPDOWN_VALUE = TEAL_PRIMARY         # Selected value text
DROPDOWN_ICON = TEXT_MUTED            # Dropdown arrow icon

# --- Log Panel ---
LOG_PANEL_TITLE = GOLD_PRIMARY        # "Log" header
LOG_PANEL_CLOSE = ICON_MUTED          # Close button icon

# --- Panels & Cards ---
PANEL_HEADER = GOLD_PRIMARY           # Generic panel headers
CARD_BORDER = BORDER_MEDIUM           # Card borders
PANEL_BORDER = BORDER_LIGHT           # Panel borders

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_log_color(level: str) -> str:
    """Get the color for a log level."""
    colors = {
        "INFO": LOG_INFO,
        "SUCCESS": LOG_SUCCESS,
        "WARNING": LOG_WARNING,
        "ERROR": LOG_ERROR,
        "DEBUG": LOG_DEBUG,
    }
    return colors.get(level.upper(), TEXT_MUTED)


def get_status_color(status: str) -> str:
    """Get the color for a status value."""
    colors = {
        "completed": STATUS_COMPLETED,
        "failed": STATUS_FAILED,
        "processing": STATUS_PROCESSING,
    }
    return colors.get(status.lower(), TEXT_MUTED)

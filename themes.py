# themes.py - NZscan theme definitions
#
# All themes are defined here. THEME is the active theme dict — it is mutated
# in-place by apply_theme() so that any module that does `from themes import THEME`
# automatically sees the updated colors without re-importing.

THEMES = {
    "Dark": {
        # Backgrounds
        "bg_primary":   "#0d1117",
        "bg_secondary": "#161b22",
        "bg_tertiary":  "#21262d",
        "bg_card":      "#1c2128",
        # Accents
        "accent_primary":   "#00d4ff",
        "accent_secondary": "#7c3aed",
        # Text
        "text_primary":   "#e6edf3",
        "text_secondary": "#8b949e",
        "text_muted":     "#484f58",
        # Borders & status
        "border":  "#30363d",
        "success": "#3fb950",
        "warning": "#d29922",
        "danger":  "#f85149",
        # Signal quality colours
        "signal_excellent": "#00d4ff",
        "signal_good":      "#3fb950",
        "signal_fair":      "#d29922",
        "signal_weak":      "#f85149",
        # Button hover/press
        "btn_hover":   "#00b8e6",
        "btn_pressed": "#0099cc",
    },

    "Light": {
        # Backgrounds
        "bg_primary":   "#f6f8fa",
        "bg_secondary": "#ffffff",
        "bg_tertiary":  "#eaeef2",
        "bg_card":      "#f0f3f6",
        # Accents
        "accent_primary":   "#0969da",
        "accent_secondary": "#8250df",
        # Text
        "text_primary":   "#1f2328",
        "text_secondary": "#57606a",
        "text_muted":     "#8c959f",
        # Borders & status
        "border":  "#d0d7de",
        "success": "#1a7f37",
        "warning": "#9a6700",
        "danger":  "#cf222e",
        # Signal quality colours
        "signal_excellent": "#0969da",
        "signal_good":      "#1a7f37",
        "signal_fair":      "#9a6700",
        "signal_weak":      "#cf222e",
        # Button hover/press
        "btn_hover":   "#0860ca",
        "btn_pressed": "#0550ae",
    },

    "Nord": {
        # Backgrounds — Nord Polar Night
        "bg_primary":   "#2e3440",
        "bg_secondary": "#3b4252",
        "bg_tertiary":  "#434c5e",
        "bg_card":      "#3b4252",
        # Accents — Nord Frost
        "accent_primary":   "#88c0d0",
        "accent_secondary": "#b48ead",
        # Text — Nord Snow Storm
        "text_primary":   "#eceff4",
        "text_secondary": "#d8dee9",
        "text_muted":     "#4c566a",
        # Borders & status
        "border":  "#4c566a",
        "success": "#a3be8c",
        "warning": "#ebcb8b",
        "danger":  "#bf616a",
        # Signal quality colours
        "signal_excellent": "#88c0d0",
        "signal_good":      "#a3be8c",
        "signal_fair":      "#ebcb8b",
        "signal_weak":      "#bf616a",
        # Button hover/press
        "btn_hover":   "#79b2c4",
        "btn_pressed": "#6aa4b6",
    },

    "Dracula": {
        # Backgrounds
        "bg_primary":   "#282a36",
        "bg_secondary": "#1e1f29",
        "bg_tertiary":  "#343746",
        "bg_card":      "#2d2f3f",
        # Accents
        "accent_primary":   "#bd93f9",
        "accent_secondary": "#ff79c6",
        # Text
        "text_primary":   "#f8f8f2",
        "text_secondary": "#6272a4",
        "text_muted":     "#44475a",
        # Borders & status
        "border":  "#44475a",
        "success": "#50fa7b",
        "warning": "#f1fa8c",
        "danger":  "#ff5555",
        # Signal quality colours
        "signal_excellent": "#bd93f9",
        "signal_good":      "#50fa7b",
        "signal_fair":      "#f1fa8c",
        "signal_weak":      "#ff5555",
        # Button hover/press
        "btn_hover":   "#ae84f0",
        "btn_pressed": "#9f75e1",
    },
}

# Active theme — mutated in-place so all `from themes import THEME` references
# reflect the current theme automatically.
THEME: dict = dict(THEMES["Dark"])


def apply_theme(name: str) -> None:
    """Switch to a named theme. Updates THEME dict in-place."""
    if name not in THEMES:
        return
    THEME.clear()
    THEME.update(THEMES[name])


def get_theme_names() -> list[str]:
    return list(THEMES.keys())


def current_theme_name() -> str:
    for name, t in THEMES.items():
        if t.get("bg_primary") == THEME.get("bg_primary"):
            return name
    return "Dark"

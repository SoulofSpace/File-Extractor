from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    # Documents
    ".pdf", ".docx", ".txt", ".md", ".rtf",
    # Images (OCR supported)
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif",
    # Spreadsheets & Data
    ".xlsx", ".xls", ".csv", ".tsv",
    # Presentations
    ".pptx", ".ppt",
    # Archives
    ".zip", ".rar", ".7z", ".tar", ".gz",
    # Videos
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    # Audio
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma",
    # Code
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
    ".cs", ".go", ".rs", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql",
}

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"}

# Movie detection patterns (Resolution, Source, Codecs, Groups, Years)
MOVIE_TAGS_REGEX = re.compile(
    r"(?i)\b(1080p|720p|2160p|4k|uhd|fhd|bluray|bdrip|brrip|web-dl|webrip|hdrip|dvdrip|x264|x265|hevc|yify|yts|rarbg)\b"
)
YEAR_REGEX = re.compile(r"\b(19\d\d|20\d\d)\b")


def classify_video(path: Path | str, size_bytes: int = 0) -> tuple[str, str]:
    """
    Classifies a video file as either a Movie or a Normal Video Clip:
      Returns (subtype, label)
      e.g. ("Movie", "Movie (1080p)") or ("Video", "Video Clip")
    """
    p = Path(path)
    name = p.name

    # Size threshold: >= 350 MB strongly suggests a feature film or movie episode
    is_large = size_bytes >= 350 * 1024 * 1024

    tag_match = MOVIE_TAGS_REGEX.search(name)
    year_match = YEAR_REGEX.search(name)

    if is_large or (tag_match and year_match) or tag_match:
        tag_str = tag_match.group(0).upper() if tag_match else "HD"
        return ("Movie", f"Movie ({tag_str})")
    
    return ("Video", "Video Clip")


# Strictly Monochrome Category Styles (Black, White, and Grey with Vector Glyphs)
CATEGORY_COLORS = {
    "Document":     {"fg": "#ffffff", "bg": "rgba(255, 255, 255, 0.08)", "emoji": "▤", "badge": "DOC"},
    "Image":        {"fg": "#e4e4e7", "bg": "rgba(255, 255, 255, 0.08)", "emoji": "⊞", "badge": "IMAGE"},
    "Video":        {"fg": "#ffffff", "bg": "rgba(255, 255, 255, 0.12)", "emoji": "▶", "badge": "VIDEO"},
    "Movie":        {"fg": "#ffffff", "bg": "rgba(255, 255, 255, 0.16)", "emoji": "🎬", "badge": "MOVIE"},
    "Audio":        {"fg": "#d4d4d8", "bg": "rgba(255, 255, 255, 0.08)", "emoji": "♫", "badge": "AUDIO"},
    "Spreadsheet":  {"fg": "#d4d4d8", "bg": "rgba(255, 255, 255, 0.08)", "emoji": "☷", "badge": "SHEET"},
    "Presentation": {"fg": "#e4e4e7", "bg": "rgba(255, 255, 255, 0.08)", "emoji": "◈", "badge": "SLIDES"},
    "Code":         {"fg": "#ffffff", "bg": "rgba(255, 255, 255, 0.08)", "emoji": "</>", "badge": "CODE"},
    "Archive":      {"fg": "#a1a1aa", "bg": "rgba(255, 255, 255, 0.08)", "emoji": "◧", "badge": "ZIP"},
    "Other":        {"fg": "#71717a", "bg": "rgba(255, 255, 255, 0.08)", "emoji": "▪", "badge": "FILE"},
}


@dataclass(frozen=True)
class DiscoveredFile:
    path: Path
    extension: str
    size: int
    created_at: float
    modified_at: float

    @property
    def file_type(self) -> str:
        ext = self.extension.lower()
        if ext in VIDEO_EXTENSIONS:
            _subtype, label = classify_video(self.path, self.size)
            return label

        mapping = {
            ".pdf": "PDF Document",
            ".docx": "Word Document",
            ".txt": "Text Document",
            ".jpg": "JPG Image",
            ".jpeg": "JPEG Image",
            ".png": "PNG Image",
            ".gif": "GIF Image",
            ".webp": "WebP Image",
            ".bmp": "Bitmap Image",
            ".tiff": "TIFF Image",
            ".xlsx": "Excel Spreadsheet",
            ".xls": "Excel Spreadsheet",
            ".csv": "CSV File",
            ".pptx": "PowerPoint Presentation",
            ".ppt": "PowerPoint Presentation",
            ".zip": "ZIP Archive",
            ".rar": "RAR Archive",
            ".7z": "7Z Archive",
            ".mp3": "MP3 Audio",
            ".wav": "WAV Audio",
            ".flac": "FLAC Audio",
            ".py": "Python Script",
            ".js": "JavaScript File",
            ".ts": "TypeScript File",
            ".java": "Java Source",
            ".c": "C Source",
            ".cpp": "C++ Source",
            ".html": "HTML Document",
            ".css": "CSS Stylesheet",
            ".json": "JSON Data",
            ".md": "Markdown Document",
        }
        return mapping.get(ext, ext.upper().lstrip(".") + " File")

    @property
    def category(self) -> str:
        ext = self.extension.lower()
        if ext in {".pdf", ".docx", ".txt", ".md", ".rtf"}:
            return "Document"
        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}:
            return "Image"
        if ext in VIDEO_EXTENSIONS:
            return "Video"
        if ext in AUDIO_EXTENSIONS:
            return "Audio"
        if ext in {".xlsx", ".xls", ".csv", ".tsv"}:
            return "Spreadsheet"
        if ext in {".pptx", ".ppt"}:
            return "Presentation"
        if ext in {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql"}:
            return "Code"
        if ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
            return "Archive"
        return "Other"

    @property
    def video_classification(self) -> tuple[str, str]:
        if self.extension.lower() in VIDEO_EXTENSIONS:
            return classify_video(self.path, self.size)
        return ("", "")


def get_category_style(category: str) -> dict[str, str]:
    """Returns {'fg': ..., 'bg': ..., 'emoji': ..., 'badge': ...} for a category."""
    if category in CATEGORY_COLORS:
        return CATEGORY_COLORS[category]
    for k, v in CATEGORY_COLORS.items():
        if k.lower() in category.lower():
            return v
    return CATEGORY_COLORS["Other"]

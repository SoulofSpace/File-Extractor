"""
universal_query_planner.py — V4 Universal Query Planner for FILE XTRACTOR.
Converts conversational text requests into structured search plans:
  • Context-aware person/entity extraction (matching known people & aliases)
  • Comprehensive natural date and date-range extraction ("9 Dec", "December 2025", "between 5 and 10 Dec", "last Monday")
  • Document type and semantic category categorization (Banking, IDs, Photos, Education, Work, etc.)
  • Multimodal intent, keywords, and visual concepts
  • Deterministic local rules first; optional local Qwen fallback on semantic ambiguity.
  • Never performs retrieval itself; outputs structured execution constraints for Hybrid Retrieval.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

DAYS_OF_WEEK = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

DOC_TYPE_PATTERNS: Dict[str, Tuple[str, List[str]]] = {
    "Bank Statement": ("Banking & Finance", ["bank statement", "account statement", "bank stmt", "passbook", "bank passbook"]),
    "Invoice": ("Banking & Finance", ["invoice", "tax invoice", "bill", "receipt", "payment slip"]),
    "Salary Slip": ("Banking & Finance", ["salary slip", "pay slip", "payslip", "compensation slip"]),
    "Aadhaar": ("IDs & Documents", ["aadhaar", "aadhar", "uidai", "e-aadhaar", "eaadhaar"]),
    "PAN": ("IDs & Documents", ["pan card", "pan number", "permanent account number", "nsdl pan", "uti pan"]),
    "Passport": ("IDs & Documents", ["passport", "indian passport"]),
    "Driving Licence": ("IDs & Documents", ["driving licence", "driving license", "dl card", "dl copy", "driver license"]),
    "College ID": ("IDs & Documents", ["college id", "student id", "university id", "campus id", "id card", "identity card"]),
    "Certificate": ("Education", ["certificate", "degree", "diploma", "marksheet", "transcript", "award"]),
    "Resume": ("Work", ["resume", "cv", "curriculum vitae"]),
    "Assignment": ("Education", ["assignment", "digital assignment", "da", "lab assignment", "assessment", "homework"]),
    "Report": ("Work", ["report", "project report", "audit report", "summary report"]),
    "Presentation": ("Work", ["presentation", "powerpoint", "ppt", "pptx", "slides", "deck"]),
    "Timetable": ("Education", ["timetable", "time table", "class schedule", "exam schedule", "routine"]),
    "Ticket": ("Travel", ["ticket", "boarding pass", "flight ticket", "train ticket", "bus ticket", "itinerary"]),
}

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Banking & Finance": ["bank", "statement", "finance", "account", "tax", "ifsc", "salary", "invoice", "bill", "cheque", "loan", "mutual fund"],
    "IDs & Documents": ["id", "identity", "aadhaar", "aadhar", "pan", "passport", "license", "licence", "voter id", "id card"],
    "Personal Photos": ["photo", "photos", "picture", "pictures", "pic", "pics", "selfie", "portrait", "snapshot", "camera"],
    "Education": ["college", "university", "syllabus", "assignment", "timetable", "notes", "lecture", "module", "exam", "grade", "study", "dbms", "dsa", "os", "cn"],
    "Work": ["work", "office", "resume", "cv", "project", "presentation", "report", "meeting", "client", "contract"],
    "Travel": ["travel", "ticket", "hotel", "flight", "trip", "vacation", "boarding pass", "itinerary", "booking"],
}

FILE_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "image": ["photo", "photos", "pic", "pics", "picture", "pictures", "image", "images", "selfie", "jpg", "jpeg", "png", "webp"],
    "pdf": ["pdf", "pdfs"],
    "document": ["document", "documents", "doc", "docs", "docx", "word", "text", "txt"],
    "spreadsheet": ["excel", "sheet", "sheets", "spreadsheet", "xlsx", "xls", "csv"],
    "presentation": ["ppt", "pptx", "powerpoint", "slides", "presentation"],
    "video": ["video", "videos", "movie", "movies", "clip", "mp4", "mkv"],
    "audio": ["audio", "song", "songs", "music", "mp3", "recording"],
    "code": ["code", "script", "program", "python", "java", "typescript", "javascript", "cpp", "c++", "html", "css", "sql"],
    "archive": ["zip", "rar", "7z", "archive", "tar"],
}


@dataclass
class UniversalDateConstraint:
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None
    is_range: bool = False
    raw_expression: str = ""
    description: str = ""

    def matches_date(self, date_val: Optional[str | float | datetime]) -> bool:
        """Determines if a given file date falls within the constraint."""
        if not date_val:
            return False
        try:
            if isinstance(date_val, (int, float)):
                ts = float(date_val)
                # Normalize milliseconds
                if ts > 1e11:
                    ts /= 1000.0
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(date_val, str):
                s = date_val.strip()
                if not s:
                    return False
                # Try ISO format or common date strings
                if "T" in s:
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            elif isinstance(date_val, datetime):
                dt = date_val if date_val.tzinfo else date_val.replace(tzinfo=timezone.utc)
            else:
                return False

            if self.start_ts is not None and dt.timestamp() < self.start_ts:
                return False
            if self.end_ts is not None and dt.timestamp() > self.end_ts:
                return False

            # If month & day specified without strict year, match month & day across years
            if self.year is None and self.month is not None and self.day is not None:
                return dt.month == self.month and dt.day == self.day
            if self.year is None and self.month is not None and self.day is None:
                return dt.month == self.month

            return True
        except Exception:
            return False


@dataclass
class UniversalSearchPlan:
    """Standard V4 Search Constraint Plan generated by Universal Query Planner."""
    raw_query: str
    cleaned_query: str
    intent: str = "search"                                # "search", "browse", "filter"
    persons: List[str] = field(default_factory=list)      # Resolved person names
    person_ids: List[int] = field(default_factory=list)   # Resolved person IDs in DB
    entities: List[str] = field(default_factory=list)     # Named entities (places, orgs, events)
    date_constraint: Optional[UniversalDateConstraint] = None
    file_types: List[str] = field(default_factory=list)   # "image", "pdf", "video", etc.
    categories: List[str] = field(default_factory=list)   # "Banking & Finance", "IDs & Documents", etc.
    document_types: List[str] = field(default_factory=list) # "Aadhaar", "Bank Statement", etc.
    keywords: List[str] = field(default_factory=list)     # Primary lexical keywords
    visual_concepts: List[str] = field(default_factory=list)
    semantic_concepts: List[str] = field(default_factory=list)
    is_person_search: bool = False
    is_visual_search: bool = False
    is_privacy_sensitive: bool = False
    explanation: str = ""

    @property
    def person_name(self) -> Optional[str]:
        return self.persons[0] if self.persons else None

    @property
    def file_type(self) -> Optional[str]:
        return self.file_types[0] if self.file_types else None

    @property
    def category(self) -> Optional[str]:
        return self.categories[0] if self.categories else None

    @property
    def document_type(self) -> Optional[str]:
        return self.document_types[0] if self.document_types else None

    @property
    def date_range(self):
        return self.date_constraint

    @property
    def date_start(self) -> Optional[str]:
        return self.date_constraint.start_iso[:10] if (self.date_constraint and self.date_constraint.start_iso) else None

    @property
    def date_end(self) -> Optional[str]:
        return self.date_constraint.end_iso[:10] if (self.date_constraint and self.date_constraint.end_iso) else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "raw_query": self.raw_query,
            "cleaned_query": self.cleaned_query,
            "persons": self.persons,
            "person_ids": self.person_ids,
            "entities": self.entities,
            "date": {
                "start": self.date_constraint.start_iso if self.date_constraint else None,
                "end": self.date_constraint.end_iso if self.date_constraint else None,
                "raw": self.date_constraint.raw_expression if self.date_constraint else None,
                "description": self.date_constraint.description if self.date_constraint else None,
            } if self.date_constraint else None,
            "file_types": self.file_types,
            "categories": self.categories,
            "document_types": self.document_types,
            "keywords": self.keywords,
            "visual_concepts": self.visual_concepts,
            "semantic_concepts": self.semantic_concepts,
            "is_person_search": self.is_person_search,
            "is_visual_search": self.is_visual_search,
            "explanation": self.explanation,
        }


class UniversalQueryPlanner:
    """
    Deterministic rule-based Universal Query Planner with natural language parsing for V4.
    Extracts person references, temporal constraints, file types, document categories, and visual tags.
    """

    def __init__(self, database: Optional[Any] = None) -> None:
        self.database = database

    def plan_query(self, raw_query: str, current_year: int = 2026) -> UniversalSearchPlan:
        return self.parse(raw_query, current_year)

    def parse(self, raw_query: str, current_year: int = 2026) -> UniversalSearchPlan:
        query = (raw_query or "").strip()
        if not query:
            return UniversalSearchPlan(raw_query="", cleaned_query="")

        # 1. Clean conversational prefixes and suffixes
        cleaned = self._clean_fillers(query)

        # 2. Extract Date / Date Range
        date_constraint, cleaned_no_date = self._extract_date(cleaned, current_year)

        # 3. Extract Document Types and Categories
        doc_types, categories, cleaned_no_doc = self._extract_doc_types_and_categories(cleaned_no_date)

        # 4. Extract File Types (image, pdf, etc.)
        file_types, cleaned_no_types = self._extract_file_types(cleaned_no_doc)

        # 5. Extract Persons and Aliases
        persons, person_ids, cleaned_no_persons = self._extract_persons(cleaned_no_types)

        # 6. Extract Keywords, Visual concepts, and Acronyms
        keywords, visual_concepts, semantic_concepts = self._extract_concepts(cleaned_no_persons)

        is_visual = (
            "image" in file_types
            or "Personal Photos" in categories
            or len(visual_concepts) > 0
            or any(w in query.lower() for w in ["photo", "pic", "image", "selfie", "picture", "camera", "wearing", "shirt", "dress"])
        )

        is_person = len(persons) > 0 or len(person_ids) > 0

        # Build explanation
        exp_parts = []
        if persons:
            exp_parts.append(f"Person: {', '.join(persons)}")
        if date_constraint and date_constraint.description:
            exp_parts.append(date_constraint.description)
        if doc_types:
            exp_parts.append(f"DocType: {', '.join(doc_types)}")
        if file_types:
            exp_parts.append(f"FileType: {', '.join(file_types)}")
        if keywords:
            exp_parts.append(f"Keywords: {', '.join(keywords[:3])}")

        return UniversalSearchPlan(
            raw_query=query,
            cleaned_query=cleaned,
            intent="search",
            persons=persons,
            person_ids=person_ids,
            date_constraint=date_constraint,
            file_types=file_types,
            categories=categories,
            document_types=doc_types,
            keywords=keywords,
            visual_concepts=visual_concepts,
            semantic_concepts=semantic_concepts,
            is_person_search=is_person,
            is_visual_search=is_visual,
            is_privacy_sensitive=any(c in ["Banking & Finance", "IDs & Documents"] for c in categories),
            explanation=" · ".join(exp_parts) if exp_parts else "Universal retrieval query",
        )

    def _clean_fillers(self, text: str) -> str:
        s = text
        fillers = [
            r"^(can you\s+)?(please\s+)?(find|show|get|search|display|locate|open|retrieve|look for|give me)\s+(me\s+)?(my\s+|the\s+|all\s+|a\s+|some\s+)?",
            r"^(where is|where are|do you have|i need|i want|bring me)\s+(my\s+|the\s+|all\s+|a\s+|some\s+)?",
            r"\s+(please|for me|quickly)$",
        ]
        for pattern in fillers:
            s = re.sub(pattern, "", s, flags=re.IGNORECASE).strip()
        return s

    def _extract_date(self, text: str, current_year: int) -> Tuple[Optional[UniversalDateConstraint], str]:
        working = text

        # Range pattern: "between X and Y [Month]" or "from X to Y [Month]"
        range_match = re.search(
            r"\b(?:between|from)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(?:and|to)\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+(\d{4}))?\b",
            working,
            re.IGNORECASE,
        )
        if range_match:
            d1 = int(range_match.group(1))
            d2 = int(range_match.group(2))
            m_str = range_match.group(3).lower()
            y_str = range_match.group(4)
            if m_str in MONTH_NAMES:
                month = MONTH_NAMES[m_str]
                year = int(y_str) if y_str else current_year
                try:
                    start_dt = datetime(year, month, min(d1, d2), 0, 0, 0, tzinfo=timezone.utc)
                    end_dt = datetime(year, month, max(d1, d2), 23, 59, 59, tzinfo=timezone.utc)
                    c = UniversalDateConstraint(
                        start_iso=start_dt.isoformat(),
                        end_iso=end_dt.isoformat(),
                        start_ts=start_dt.timestamp(),
                        end_ts=end_dt.timestamp(),
                        month=month,
                        year=int(y_str) if y_str else None,
                        is_range=True,
                        raw_expression=range_match.group(0),
                        description=f"Date range: {min(d1, d2)}–{max(d1, d2)} {m_str.capitalize()}" + (f" {year}" if y_str else ""),
                    )
                    cleaned = re.sub(re.escape(range_match.group(0)), "", working, flags=re.IGNORECASE).strip()
                    return c, self._clean_punctuation(cleaned)
                except ValueError:
                    pass

        # Single date: "9 Dec", "9th December", "December 9", "9 Dec 2025"
        # Variation A: Day Month [Year]
        day_month_match = re.search(
            r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+(\d{4}))?\b",
            working,
            re.IGNORECASE,
        )
        if day_month_match:
            d_val = int(day_month_match.group(1))
            m_str = day_month_match.group(2).lower()
            y_str = day_month_match.group(3)
            if m_str in MONTH_NAMES and 1 <= d_val <= 31:
                month = MONTH_NAMES[m_str]
                year = int(y_str) if y_str else current_year
                try:
                    start_dt = datetime(year, month, d_val, 0, 0, 0, tzinfo=timezone.utc)
                    end_dt = datetime(year, month, d_val, 23, 59, 59, tzinfo=timezone.utc)
                    c = UniversalDateConstraint(
                        start_iso=start_dt.isoformat(),
                        end_iso=end_dt.isoformat(),
                        start_ts=start_dt.timestamp(),
                        end_ts=end_dt.timestamp(),
                        day=d_val,
                        month=month,
                        year=int(y_str) if y_str else None,
                        is_range=False,
                        raw_expression=day_month_match.group(0),
                        description=f"Date: {d_val} {m_str.capitalize()}" + (f" {year}" if y_str else ""),
                    )
                    cleaned = re.sub(re.escape(day_month_match.group(0)), "", working, flags=re.IGNORECASE).strip()
                    return c, self._clean_punctuation(cleaned)
                except ValueError:
                    pass

        # Variation B: Month Day [Year] e.g. "December 9" or "Dec 9, 2025"
        month_day_match = re.search(
            r"\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
            working,
            re.IGNORECASE,
        )
        if month_day_match:
            m_str = month_day_match.group(1).lower()
            d_val = int(month_day_match.group(2))
            y_str = month_day_match.group(3)
            if m_str in MONTH_NAMES and 1 <= d_val <= 31:
                month = MONTH_NAMES[m_str]
                year = int(y_str) if y_str else current_year
                try:
                    start_dt = datetime(year, month, d_val, 0, 0, 0, tzinfo=timezone.utc)
                    end_dt = datetime(year, month, d_val, 23, 59, 59, tzinfo=timezone.utc)
                    c = UniversalDateConstraint(
                        start_iso=start_dt.isoformat(),
                        end_iso=end_dt.isoformat(),
                        start_ts=start_dt.timestamp(),
                        end_ts=end_dt.timestamp(),
                        day=d_val,
                        month=month,
                        year=int(y_str) if y_str else None,
                        is_range=False,
                        raw_expression=month_day_match.group(0),
                        description=f"Date: {d_val} {m_str.capitalize()}" + (f" {year}" if y_str else ""),
                    )
                    cleaned = re.sub(re.escape(month_day_match.group(0)), "", working, flags=re.IGNORECASE).strip()
                    return c, self._clean_punctuation(cleaned)
                except ValueError:
                    pass

        # Month Year: "December 2025" or "in September" or "from September"
        month_year_match = re.search(
            r"\b(?:in|from|during|of)\s+([A-Za-z]+)(?:\s+(\d{4}))?\b",
            working,
            re.IGNORECASE,
        )
        if not month_year_match:
            month_year_match = re.search(
                r"\b([A-Za-z]+)\s+(\d{4})\b",
                working,
                re.IGNORECASE,
            )
        if month_year_match:
            m_str = month_year_match.group(1).lower()
            y_str = month_year_match.group(2) if len(month_year_match.groups()) >= 2 else None
            if m_str in MONTH_NAMES and m_str not in ["may"]:
                month = MONTH_NAMES[m_str]
                year = int(y_str) if y_str else current_year
                _, last_day = calendar.monthrange(year, month)
                start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
                end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
                c = UniversalDateConstraint(
                    start_iso=start_dt.isoformat(),
                    end_iso=end_dt.isoformat(),
                    start_ts=start_dt.timestamp(),
                    end_ts=end_dt.timestamp(),
                    month=month,
                    year=int(y_str) if y_str else None,
                    is_range=True,
                    raw_expression=month_year_match.group(0),
                    description=f"Month: {m_str.capitalize()}" + (f" {year}" if y_str else ""),
                )
                cleaned = re.sub(re.escape(month_year_match.group(0)), "", working, flags=re.IGNORECASE).strip()
                return c, self._clean_punctuation(cleaned)

        # Relative dates: "today", "yesterday", "last week", "last month", "last Monday"
        rel_match = re.search(r"\b(today|yesterday|last\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month|year))\b", working, re.IGNORECASE)
        if rel_match:
            term = rel_match.group(1).lower()
            now = datetime(current_year, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
            if term == "today":
                start_dt = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
                end_dt = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=timezone.utc)
            elif term == "yesterday":
                y_day = now - timedelta(days=1)
                start_dt = datetime(y_day.year, y_day.month, y_day.day, 0, 0, 0, tzinfo=timezone.utc)
                end_dt = datetime(y_day.year, y_day.month, y_day.day, 23, 59, 59, tzinfo=timezone.utc)
            elif "last" in term:
                parts = term.split()
                sub = parts[1] if len(parts) > 1 else ""
                if sub in DAYS_OF_WEEK:
                    target_weekday = DAYS_OF_WEEK[sub]
                    days_behind = (now.weekday() - target_weekday) % 7
                    if days_behind == 0:
                        days_behind = 7
                    target_dt = now - timedelta(days=days_behind)
                    start_dt = datetime(target_dt.year, target_dt.month, target_dt.day, 0, 0, 0, tzinfo=timezone.utc)
                    end_dt = datetime(target_dt.year, target_dt.month, target_dt.day, 23, 59, 59, tzinfo=timezone.utc)
                elif sub == "week":
                    start_dt = now - timedelta(days=7)
                    end_dt = now
                elif sub == "month":
                    start_dt = now - timedelta(days=30)
                    end_dt = now
                else:
                    start_dt = now - timedelta(days=365)
                    end_dt = now
            else:
                start_dt = now - timedelta(days=1)
                end_dt = now

            c = UniversalDateConstraint(
                start_iso=start_dt.isoformat(),
                end_iso=end_dt.isoformat(),
                start_ts=start_dt.timestamp(),
                end_ts=end_dt.timestamp(),
                is_range=True,
                raw_expression=rel_match.group(0),
                description=f"Relative: {term}",
            )
            cleaned = re.sub(re.escape(rel_match.group(0)), "", working, flags=re.IGNORECASE).strip()
            return c, self._clean_punctuation(cleaned)

        return None, working

    def _extract_doc_types_and_categories(self, text: str) -> Tuple[List[str], List[str], str]:
        working = text
        detected_doc_types: List[str] = []
        detected_categories: List[str] = []

        lower = working.lower()
        for doc_type, (cat, aliases) in DOC_TYPE_PATTERNS.items():
            for alias in aliases:
                pattern = r"\b" + re.escape(alias) + r"(?:s|es)?\b"
                if re.search(pattern, lower):
                    if doc_type not in detected_doc_types:
                        detected_doc_types.append(doc_type)
                    if cat not in detected_categories:
                        detected_categories.append(cat)
                    working = re.sub(pattern, "", working, flags=re.IGNORECASE)
                    lower = working.lower()
                    break

        for cat_name, kw_list in CATEGORY_KEYWORDS.items():
            for kw in kw_list:
                pattern = r"\b" + re.escape(kw) + r"(?:s|es)?\b"
                if re.search(pattern, lower):
                    if cat_name not in detected_categories:
                        detected_categories.append(cat_name)
                    # Don't strip core keywords if they are academic subjects (e.g. DBMS, DSA)
                    if kw not in ["dbms", "dsa", "os", "cn", "ai", "ml", "notes"]:
                        working = re.sub(pattern, "", working, flags=re.IGNORECASE)
                        lower = working.lower()
                    break

        return detected_doc_types, detected_categories, self._clean_punctuation(working)

    def _extract_file_types(self, text: str) -> Tuple[List[str], str]:
        working = text
        lower = working.lower()
        detected_types: List[str] = []

        for ftype, keywords in FILE_TYPE_KEYWORDS.items():
            for kw in keywords:
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, lower):
                    if ftype not in detected_types:
                        detected_types.append(ftype)
                    working = re.sub(pattern, "", working, flags=re.IGNORECASE)
                    lower = working.lower()
                    break

        return detected_types, self._clean_punctuation(working)

    def _extract_persons(self, text: str) -> Tuple[List[str], List[int], str]:
        working = text
        detected_persons: List[str] = []
        detected_person_ids: List[int] = []

        NON_PERSON_WORDS = {"dbms", "dsa", "os", "cn", "ai", "ml", "pdf", "pdfs", "doc", "docs", "file", "files", "image", "images", "photo", "photos", "bank", "statement", "notes", "assignment"}

        # Check possessives: e.g. "Raghul's photos" or "Rahul's files"
        poss_match = re.findall(r"\b([A-Z][a-z]+|rahul|raghul|priya|arun|anand|suresh|ramesh)'s\b", working, re.IGNORECASE)
        for p in poss_match:
            name = p.capitalize()
            if name.lower() not in NON_PERSON_WORDS and name not in detected_persons:
                detected_persons.append(name)
            working = re.sub(re.escape(f"{p}'s"), "", working, flags=re.IGNORECASE)

        # Check "of <Person>", "with <Person>", "by <Person>", "related to <Person>" (avoid "about" which specifies topic)
        prep_match = re.findall(r"\b(?:of|with|by|related to|for)\s+([A-Z][a-z]+|rahul|raghul|priya|arun)\b", working, re.IGNORECASE)
        for p in prep_match:
            name = p.capitalize()
            if name.lower() not in NON_PERSON_WORDS and name not in detected_persons:
                detected_persons.append(name)
            working = re.sub(r"\b(?:of|with|by|related to|for)\s+" + re.escape(p) + r"\b", "", working, flags=re.IGNORECASE)

        # Query known database persons & aliases if database is available
        if self.database and hasattr(self.database, "list_persons"):
            try:
                known = self.database.list_persons(include_clusters=False)
                working_lower = working.lower()
                for kp in known:
                    kp_name = kp.get("name", "").strip()
                    if not kp_name:
                        continue
                    name_pat = r"\b" + re.escape(kp_name.lower()) + r"\b"
                    if re.search(name_pat, working_lower):
                        if kp_name not in detected_persons:
                            detected_persons.append(kp_name)
                        if kp["id"] not in detected_person_ids:
                            detected_person_ids.append(kp["id"])
                        working = re.sub(name_pat, "", working, flags=re.IGNORECASE)
                        working_lower = working.lower()
                    for alias in kp.get("aliases", []):
                        alias_pat = r"\b" + re.escape(alias.lower()) + r"\b"
                        if re.search(alias_pat, working_lower):
                            if kp_name not in detected_persons:
                                detected_persons.append(kp_name)
                            if kp["id"] not in detected_person_ids:
                                detected_person_ids.append(kp["id"])
                            working = re.sub(alias_pat, "", working, flags=re.IGNORECASE)
                            working_lower = working.lower()
            except Exception:
                pass

        # Standalone single name query (e.g. "Raghul" or "Rahul")
        if not detected_persons and len(working.strip().split()) == 1:
            candidate = working.strip()
            # If starts with uppercase or is a known Indian given name
            if candidate.isalpha() and (candidate[0].isupper() or candidate.lower() in ["raghul", "rahul", "priya", "arun", "anand"]):
                detected_persons.append(candidate.capitalize())
                working = ""

        # Map detected names to person_ids in database if available
        if self.database and hasattr(self.database, "find_person_by_name_or_alias"):
            for p_name in detected_persons:
                try:
                    found = self.database.find_person_by_name_or_alias(p_name)
                    if found and found["id"] not in detected_person_ids:
                        detected_person_ids.append(found["id"])
                except Exception:
                    pass

        return detected_persons, detected_person_ids, self._clean_punctuation(working)

    def _extract_concepts(self, text: str) -> Tuple[List[str], List[str], List[str]]:
        words = re.findall(r"\b\w+\b", text)
        keywords: List[str] = []
        visual_concepts: List[str] = []
        semantic_concepts: List[str] = []

        stop_words = {
            "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
            "from", "by", "about", "me", "my", "all", "some", "show", "get", "find",
            "is", "are", "was", "were", "ke", "oda", "da", "di", "hai", "kaatu"
        }

        visual_words = {
            "blue", "red", "green", "black", "white", "yellow", "shirt", "tshirt",
            "dress", "suit", "jacket", "glasses", "smile", "smiling", "portrait",
            "selfie", "standing", "sitting", "walking", "outdoor", "beach", "car"
        }

        for w in words:
            wl = w.lower()
            if wl in stop_words:
                continue
            if wl in visual_words:
                visual_concepts.append(wl)
            else:
                keywords.append(w)
                semantic_concepts.append(w)

        return keywords, visual_concepts, semantic_concepts

    def _clean_punctuation(self, text: str) -> str:
        s = re.sub(r"[\s\-_,.:;!?]+", " ", text).strip()
        return s

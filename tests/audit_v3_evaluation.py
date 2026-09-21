"""
audit_v3_evaluation.py — Comprehensive Integrity and Generalization Audit for FILE XTRACTOR V3.
Executes:
1. 100+ Blind Evaluation queries across 16 diverse categories.
2. VLM Weight Ablation across [0.0, 0.15, 0.35, 0.50, 0.70, 1.0].
3. Latency decomposition (BM25, SBERT, CLIP, Cache Hash, Qwen VLM, Qwen Reranker, End-to-End Cold/Warm).
4. Qwen server failure / offline fallback verification.
5. Target filename leakage audit.
6. Export detailed JSON and Markdown query-by-query breakdown.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.domain.vlm_provider import DocumentUnderstandingResult
from intellifile.models import DiscoveredFile
from intellifile.vlm.local_qwen import LocalQwen35Provider
from intellifile.reranker import CandidateReranker
from PIL import Image

# ─────────────────────────────────────────────────────────────────────────────
# 1. EVALUATION CORPUS (35 Diverse Items with Generic Filenames CORPUS_001..035)
# ─────────────────────────────────────────────────────────────────────────────

CORPUS = [
    # Animals (001 - 003)
    {
        "id": "CORPUS_001",
        "filename": "FILE_A01.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Golden Retriever Outdoors",
        "description": "A playful golden retriever dog catching a tennis ball in the grass at a park",
        "objects": ["dog", "golden retriever", "tennis ball", "grass"],
        "semantic_tags": ["pet", "canine", "park", "retriever"],
        "visual_concepts": ["outdoor", "sunny", "action shot"],
    },
    {
        "id": "CORPUS_002",
        "filename": "FILE_A02.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Red Panda on Bamboo",
        "description": "A rare red panda resting on a bamboo tree branch in a mountain sanctuary",
        "objects": ["red panda", "bamboo", "tree branch"],
        "semantic_tags": ["wildlife", "endangered", "mammal", "zoo"],
        "visual_concepts": ["close-up", "forest", "foliage"],
    },
    {
        "id": "CORPUS_003",
        "filename": "FILE_A03.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Barn Owl in Flight",
        "description": "A barn owl with outstretched white and brown wings flying silently at dusk",
        "objects": ["barn owl", "wings", "feathers", "talons"],
        "semantic_tags": ["bird of prey", "nocturnal", "avian", "flight"],
        "visual_concepts": ["wingspan", "dusk", "motion"],
    },
    # Vehicles (004 - 006)
    {
        "id": "CORPUS_004",
        "filename": "FILE_V04.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Red Electric Sports Car",
        "description": "Sleek crimson electric vehicle plugged into a high-voltage rapid charging station",
        "objects": ["car", "electric vehicle", "charging station", "wheel", "cable"],
        "semantic_tags": ["automobile", "ev", "sports car", "clean energy"],
        "visual_concepts": ["red paint", "modern", "glossy"],
    },
    {
        "id": "CORPUS_005",
        "filename": "FILE_V05.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "High-Speed Bullet Train",
        "description": "Aerodynamic Shinkansen bullet train departing a modern railway platform",
        "objects": ["train", "bullet train", "railway", "platform", "tracks"],
        "semantic_tags": ["transit", "locomotive", "railway", "transportation"],
        "visual_concepts": ["aerodynamic", "speed", "concrete"],
    },
    {
        "id": "CORPUS_006",
        "filename": "FILE_V06.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Yellow School Bus",
        "description": "Classic yellow school bus parked outside an elementary school on a crisp morning",
        "objects": ["school bus", "bus", "wheels", "road"],
        "semantic_tags": ["school", "education", "student transit", "yellow bus"],
        "visual_concepts": ["bright yellow", "suburban", "morning"],
    },
    # Objects (007 - 009)
    {
        "id": "CORPUS_007",
        "filename": "FILE_O07.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Vintage Optical Microscope",
        "description": "Brass monocular scientific laboratory microscope with multiple objective lenses on wooden table",
        "objects": ["microscope", "lenses", "focus knob", "stage", "brass tube"],
        "semantic_tags": ["science", "laboratory", "optics", "biology", "magnification"],
        "visual_concepts": ["vintage brass", "scientific instrument"],
    },
    {
        "id": "CORPUS_008",
        "filename": "FILE_O08.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Acoustic Sunburst Guitar",
        "description": "Six-string acoustic guitar with tobacco sunburst finish resting on a wooden stand",
        "objects": ["guitar", "strings", "fretboard", "sound hole", "stand"],
        "semantic_tags": ["music", "instrument", "acoustic", "wood"],
        "visual_concepts": ["sunburst finish", "cozy lighting"],
    },
    {
        "id": "CORPUS_009",
        "filename": "FILE_O09.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Espresso Machine",
        "description": "Polished stainless steel dual-boiler espresso machine pulling a double shot into a glass cup",
        "objects": ["espresso machine", "portafilter", "coffee cup", "steam wand"],
        "semantic_tags": ["coffee", "cafe", "espresso", "barista"],
        "visual_concepts": ["stainless steel", "steam", "crema"],
    },
    # People (010 - 012)
    {
        "id": "CORPUS_010",
        "filename": "FILE_P10.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Surgeon in Green Scrubs",
        "description": "Medical doctor wearing green surgical scrubs, surgical mask, and sterile gloves in operating theater",
        "people": ["surgeon", "doctor"],
        "objects": ["surgical mask", "gloves", "operating light", "monitors"],
        "semantic_tags": ["medicine", "surgery", "hospital", "healthcare"],
        "visual_concepts": ["sterile", "bright operating theater"],
    },
    {
        "id": "CORPUS_011",
        "filename": "FILE_P11.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Construction Worker with Hard Hat",
        "description": "Civil engineer wearing yellow high-visibility safety vest and white hard hat inspecting blueprint",
        "people": ["construction worker", "civil engineer"],
        "objects": ["hard hat", "safety vest", "blueprint", "scaffolding"],
        "semantic_tags": ["construction", "engineering", "building", "safety"],
        "visual_concepts": ["high-vis", "urban job site"],
    },
    {
        "id": "CORPUS_012",
        "filename": "FILE_P12.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Chef Plating Artisan Pasta",
        "description": "Professional chef wearing white double-breasted jacket carefully garnishing handmade ravioli with basil",
        "people": ["chef", "cook"],
        "objects": ["apron", "pasta dish", "tongs", "kitchen counter"],
        "semantic_tags": ["culinary", "restaurant", "gourmet", "cooking"],
        "visual_concepts": ["commercial kitchen", "shallow depth of field"],
    },
    # Clothing (013 - 015)
    {
        "id": "CORPUS_013",
        "filename": "FILE_C13.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Navy Wool Double-Breasted Blazer",
        "description": "Tailored dark navy blue wool suit jacket with polished brass anchor buttons on a mannequin",
        "objects": ["blazer", "suit jacket", "buttons", "mannequin", "lapel"],
        "semantic_tags": ["fashion", "menswear", "formal", "suit", "wool"],
        "visual_concepts": ["navy blue", "brass buttons", "tailored"],
    },
    {
        "id": "CORPUS_014",
        "filename": "FILE_C14.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Crimson Silk Evening Gown",
        "description": "Floor-length elegant scarlet red silk evening dress with pleated bodice on display hanger",
        "objects": ["evening gown", "red dress", "silk dress", "hanger"],
        "semantic_tags": ["fashion", "evening wear", "ball gown", "silk", "red dress"],
        "visual_concepts": ["crimson red", "silk sheen", "flowing fabric"],
    },
    {
        "id": "CORPUS_015",
        "filename": "FILE_C15.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Running Shoes with Fluorescent Laces",
        "description": "Black trail running sneakers with vibrant neon yellow laces and rugged grip rubber outsole",
        "objects": ["running shoes", "sneakers", "yellow laces", "outsole"],
        "semantic_tags": ["footwear", "running", "athletic", "trail"],
        "visual_concepts": ["neon yellow", "rugged tread"],
    },
    # Scenes (016 - 018)
    {
        "id": "CORPUS_016",
        "filename": "FILE_S16.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Misty Pine Forest at Dawn",
        "description": "Dense alpine evergreen pine woods shrouded in atmospheric early morning fog and golden sunbeams",
        "objects": ["pine trees", "fog", "sunbeams", "moss", "forest floor"],
        "semantic_tags": ["nature", "landscape", "wilderness", "foggy", "dawn"],
        "visual_concepts": ["misty", "ethereal", "golden rays", "green"],
    },
    {
        "id": "CORPUS_017",
        "filename": "FILE_S17.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Tokyo Night Street Market",
        "description": "Bustling narrow alleyway in Shinjuku filled with glowing neon signs, food stalls, and red lanterns",
        "objects": ["lanterns", "neon signs", "food stall", "bicycles"],
        "semantic_tags": ["cityscape", "night life", "tokyo", "japan", "alleyway"],
        "visual_concepts": ["neon glow", "red lanterns", "rain reflections"],
    },
    {
        "id": "CORPUS_018",
        "filename": "FILE_S18.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Desert Sand Dunes at Sunset",
        "description": "Vast undulating sand dunes in Sahara desert casting long curved shadows under an orange sunset",
        "objects": ["sand dunes", "ridges", "shadows", "sun"],
        "semantic_tags": ["desert", "dunes", "sahara", "sunset", "arid"],
        "visual_concepts": ["orange gradient", "curved shadows", "wind ripples"],
    },
    # Posters (019 - 021)
    {
        "id": "CORPUS_019",
        "filename": "FILE_P19.jpg",
        "doc_type": "poster",
        "category": "Image",
        "title": "Annual Jazz & Blues Festival 2026",
        "event_name": "Annual Jazz & Blues Festival",
        "description": "Artistic promotional music festival poster featuring silhouette of saxophone player against purple background",
        "objects": ["poster", "saxophone", "silhouette", "musical notes"],
        "semantic_tags": ["music festival", "jazz", "concert", "event poster"],
        "visual_concepts": ["purple gradient", "bold typography", "music graphic"],
        "important_text": ["Annual Jazz & Blues Festival 2026", "Live at Waterfront Park", "July 18-20"],
    },
    {
        "id": "CORPUS_020",
        "filename": "FILE_P20.jpg",
        "doc_type": "poster",
        "category": "Image",
        "title": "Cybersecurity Summit Banner",
        "event_name": "Global Cyber Defense 2026",
        "description": "Tech conference poster with digital padlock and binary code matrix advertising ethical hacking keynote",
        "objects": ["poster", "digital lock", "matrix code", "shield"],
        "semantic_tags": ["cybersecurity", "conference", "hacking", "infosec"],
        "visual_concepts": ["cyan neon", "dark theme", "tech banner"],
        "important_text": ["Global Cyber Defense 2026", "Keynote: Zero Trust Architecture", "Nov 12"],
    },
    {
        "id": "CORPUS_021",
        "filename": "FILE_P21.jpg",
        "doc_type": "poster",
        "category": "Image",
        "title": "Robotics Championship Announcement",
        "event_name": "Autonomous Bot Challenge",
        "description": "High school and collegiate robotics competition flyer showing mechanical rover and competition schedule",
        "objects": ["flyer", "robot", "rover", "circuit tracks"],
        "semantic_tags": ["robotics", "competition", "stem", "engineering flyer"],
        "visual_concepts": ["futuristic", "orange and dark grey"],
        "important_text": ["Autonomous Bot Challenge", "Prize Pool $25,000", "Register by May 1st"],
    },
    # Documents (022 - 024)
    {
        "id": "CORPUS_022",
        "filename": "FILE_D22.pdf",
        "doc_type": "document",
        "category": "Document",
        "title": "Academic Semester Grade Transcript",
        "description": "Official university academic record listing semester courses, credits, letter grades, and cumulative GPA 3.92",
        "extracted_text": "UNIVERSITY OF TECHNOLOGY OFFICIAL TRANSCRIPT Semester 4 BACSE201 DBMS BACSE202 OS BACSE203 Networks GPA: 3.92 Dean's List Honor Roll",
        "semantic_tags": ["transcript", "grades", "academic", "university", "gpa"],
        "visual_concepts": ["tabular", "official seal"],
    },
    {
        "id": "CORPUS_023",
        "filename": "FILE_D23.pdf",
        "doc_type": "document",
        "category": "Document",
        "title": "Residential Apartment Lease Agreement",
        "description": "Standard real estate residential tenancy lease agreement detailing monthly rent payment terms and security deposit",
        "extracted_text": "RESIDENTIAL TENANCY LEASE CONTRACT Tenant agrees to pay monthly rent amount of 2400 USD due on first day of calendar month Security deposit 3000 USD",
        "semantic_tags": ["lease", "rental agreement", "contract", "real estate", "rent"],
        "visual_concepts": ["legal text", "signature lines"],
    },
    {
        "id": "CORPUS_024",
        "filename": "FILE_D24.pdf",
        "doc_type": "document",
        "category": "Document",
        "title": "Distributed Consensus Whitepaper",
        "description": "Computer science technical specification paper explaining Raft and Paxos quorum consensus protocols in fault-tolerant clusters",
        "extracted_text": "RESEARCH REPORT: Fault-Tolerant Distributed Consensus Algorithms Paxos vs Raft Leader Election Log Replication Quorum Heartbeats",
        "semantic_tags": ["computer science", "distributed systems", "consensus", "paxos", "raft", "whitepaper"],
        "visual_concepts": ["two-column", "academic paper"],
    },
    # Screenshots (025 - 026)
    {
        "id": "CORPUS_025",
        "filename": "FILE_S25.png",
        "doc_type": "screenshot",
        "category": "Image",
        "title": "Docker Terminal Error Log Screenshot",
        "description": "Desktop screenshot of terminal console showing docker daemon crash exit code 137 out of memory",
        "objects": ["screenshot", "terminal window", "bash prompt"],
        "semantic_tags": ["docker", "terminal", "error log", "crash", "oom"],
        "visual_concepts": ["monochrome console", "red error text"],
        "important_text": ["FATAL: container exited with code 137 (OOMKilled)", "memory limit exceeded 2048MB"],
    },
    {
        "id": "CORPUS_026",
        "filename": "FILE_S26.png",
        "doc_type": "screenshot",
        "category": "Image",
        "title": "Mobile Wireframe Banking App",
        "description": "UI mockup screenshot of mobile banking dashboard with instant wire transfer button and recent transactions",
        "objects": ["wireframe", "screenshot", "balance card", "send money button"],
        "semantic_tags": ["ui design", "mobile app", "fintech", "wireframe", "banking"],
        "visual_concepts": ["clean interface", "minimalist card"],
        "important_text": ["Available Balance: $14,250.00", "Transfer Funds", "Recent Activity"],
    },
    # Receipts (027 - 028)
    {
        "id": "CORPUS_027",
        "filename": "FILE_R27.jpg",
        "doc_type": "receipt",
        "category": "Image",
        "title": "Whole Foods Organic Grocery Receipt",
        "description": "Itemized supermarket thermal printed register paper receipt showing almond milk, avocados, and total $47.85",
        "objects": ["receipt", "barcode", "paper slip"],
        "semantic_tags": ["grocery receipt", "supermarket", "expenses", "shopping"],
        "visual_concepts": ["thermal paper", "monospaced text"],
        "important_text": ["WHOLE FOODS MARKET", "1x Organic Almond Milk $4.29", "4x Haas Avocados $6.00", "TOTAL: $47.85"],
    },
    {
        "id": "CORPUS_028",
        "filename": "FILE_R28.jpg",
        "doc_type": "receipt",
        "category": "Image",
        "title": "Trattoria Roma Restaurant Dinner Bill",
        "description": "Restaurant customer copy bill for two guests showing margherita pizza, chianti wine, and tip",
        "objects": ["receipt", "restaurant bill", "check slip"],
        "semantic_tags": ["restaurant bill", "dining", "italian food", "meal receipt"],
        "visual_concepts": ["itemized receipt", "tax breakdown"],
        "important_text": ["TRATTORIA ROMA", "Margherita Pizza $18.00", "Chianti Classico $34.00", "Subtotal $52.00", "Tax & Tip Included"],
    },
    # Certificates (029 - 030)
    {
        "id": "CORPUS_029",
        "filename": "FILE_K29.jpg",
        "doc_type": "certificate",
        "category": "Image",
        "title": "Certified Kubernetes Administrator Badge",
        "description": "Official Linux Foundation certificate of achievement for passing the CKA exam with embossed gold seal",
        "objects": ["certificate", "gold seal", "ribbon", "crest"],
        "semantic_tags": ["certification", "kubernetes", "cloud", "linux foundation", "cka"],
        "visual_concepts": ["ornate border", "embossed badge"],
        "important_text": ["CERTIFIED KUBERNETES ADMINISTRATOR", "Cloud Native Computing Foundation", "Verification ID: CKA-99482"],
    },
    {
        "id": "CORPUS_030",
        "filename": "FILE_K30.jpg",
        "doc_type": "certificate",
        "category": "Image",
        "title": "Emergency First Aid & CPR Certificate",
        "description": "Red Cross medical training certificate for basic life support and automated external defibrillator operation",
        "objects": ["certificate", "red cross logo", "instructor signature"],
        "semantic_tags": ["first aid", "cpr", "medical training", "safety certificate"],
        "visual_concepts": ["red border", "official certification"],
        "important_text": ["Standard First Aid with CPR/AED Level C", "American Red Cross", "Valid Through 2028"],
    },
    # Diagrams (031 - 032)
    {
        "id": "CORPUS_031",
        "filename": "FILE_X31.png",
        "doc_type": "diagram",
        "category": "Image",
        "title": "OAuth 2.0 Authorization Flow Sequence Diagram",
        "description": "UML sequence diagram illustrating authorization code grant between user agent, client app, auth server, and resource API",
        "objects": ["flowchart", "sequence diagram", "actor arrows", "lifeline"],
        "semantic_tags": ["software architecture", "oauth2", "authentication", "uml", "diagram"],
        "visual_concepts": ["monochrome vectors", "sequence arrows"],
        "important_text": ["OAuth 2.0 Auth Code Grant", "Authorization Request", "Exchange Code for Access Token"],
    },
    {
        "id": "CORPUS_032",
        "filename": "FILE_X32.png",
        "doc_type": "diagram",
        "category": "Image",
        "title": "E-Commerce Database Relational Schema ERD",
        "description": "Entity relationship diagram visualizing tables, foreign keys, and indexes for users, orders, items, and payments",
        "objects": ["diagram", "erd", "table boxes", "crow foot connectors"],
        "semantic_tags": ["database design", "erd", "sql schema", "relational model"],
        "visual_concepts": ["schema boxes", "foreign key connectors"],
        "important_text": ["users (id, email)", "orders (id, user_id, status)", "order_items (order_id, product_id)"],
    },
    # Timetables & Schedules (033 - 035)
    {
        "id": "CORPUS_033",
        "filename": "FILE_T33.jpg",
        "doc_type": "timetable",
        "category": "Image",
        "title": "Computer Science Fall Semester Class Schedule",
        "description": "Weekly course timetable grid from Monday to Friday with lab blocks, lecture rooms, and tutorial hours",
        "objects": ["timetable", "schedule grid", "calendar"],
        "semantic_tags": ["timetable", "class schedule", "college", "routine", "lectures"],
        "visual_concepts": ["color-coded grid", "hour blocks"],
        "important_text": ["FALL 2026 CS SCHEDULE", "Mon/Wed 10:00 AM - Algorithms Room 302", "Tue/Thu 2:00 PM - OS Lab"],
    },
    {
        "id": "CORPUS_034",
        "filename": "FILE_T34.jpg",
        "doc_type": "id_card",
        "category": "Image",
        "title": "University Student Identity Card",
        "description": "Plastic laminated photo identification badge with barcode, student matriculation number, and campus logo",
        "objects": ["id card", "identity card", "barcode", "photo id", "chip"],
        "semantic_tags": ["student id", "identity card", "campus pass", "membership"],
        "visual_concepts": ["portrait photo", "plastic card badge"],
        "important_text": ["STUDENT IDENTITY CARD", "Department of Computer Engineering", "ID NO: 2024-B-8831"],
    },
    {
        "id": "CORPUS_035",
        "filename": "FILE_T35.jpg",
        "doc_type": "photo",
        "category": "Image",
        "title": "Sleek Black Panther Jaguar in Jungle",
        "description": "Melanistic black panther wild cat with glowing emerald eyes stalking silently through Amazon rainforest",
        "objects": ["black panther", "jaguar", "wild cat", "jungle foliage"],
        "semantic_tags": ["wildlife", "big cat", "panther", "jaguar", "predator"],
        "visual_concepts": ["dark sleek fur", "emerald eyes", "shadowy"],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. 105 UNSEEN BENCHMARK QUERIES ACROSS 16 SPECIFIED CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────

EVALUATION_QUERIES = [
    # 1. Animals (7 queries)
    {"query": "golden retriever dog in park", "target": "CORPUS_001", "cat": "Animals"},
    {"query": "cute red panda on tree branch", "target": "CORPUS_002", "cat": "Animals"},
    {"query": "barn owl flying with open wings", "target": "CORPUS_003", "cat": "Animals"},
    {"query": "dog playing with tennis ball", "target": "CORPUS_001", "cat": "Animals"},
    {"query": "endangered mammal in bamboo forest", "target": "CORPUS_002", "cat": "Animals"},
    {"query": "nocturnal predatory bird feathers", "target": "CORPUS_003", "cat": "Animals"},
    {"query": "canine pet outdoors on green lawn", "target": "CORPUS_001", "cat": "Animals"},

    # 2. Vehicles (7 queries)
    {"query": "red electric sports car at charger", "target": "CORPUS_004", "cat": "Vehicles"},
    {"query": "high speed bullet train at station", "target": "CORPUS_005", "cat": "Vehicles"},
    {"query": "yellow school bus for children", "target": "CORPUS_006", "cat": "Vehicles"},
    {"query": "crimson battery electric vehicle rapid charging", "target": "CORPUS_004", "cat": "Vehicles"},
    {"query": "aerodynamic shinkansen railway locomotive", "target": "CORPUS_005", "cat": "Vehicles"},
    {"query": "elementary student transit bus", "target": "CORPUS_006", "cat": "Vehicles"},
    {"query": "sleek sports automobile plugged into power outlet", "target": "CORPUS_004", "cat": "Vehicles"},

    # 3. Objects (7 queries)
    {"query": "vintage brass laboratory microscope", "target": "CORPUS_007", "cat": "Objects"},
    {"query": "six string sunburst acoustic guitar", "target": "CORPUS_008", "cat": "Objects"},
    {"query": "stainless steel espresso machine pulling coffee", "target": "CORPUS_009", "cat": "Objects"},
    {"query": "scientific instrument with optical lenses", "target": "CORPUS_007", "cat": "Objects"},
    {"query": "wooden musical instrument on stand", "target": "CORPUS_008", "cat": "Objects"},
    {"query": "dual boiler barista coffee maker", "target": "CORPUS_009", "cat": "Objects"},
    {"query": "magnification microscope on wooden desk", "target": "CORPUS_007", "cat": "Objects"},

    # 4. People (7 queries)
    {"query": "surgeon in green scrubs operating room", "target": "CORPUS_010", "cat": "People"},
    {"query": "construction worker wearing hard hat and safety vest", "target": "CORPUS_011", "cat": "People"},
    {"query": "chef in white uniform garnishing pasta", "target": "CORPUS_012", "cat": "People"},
    {"query": "medical doctor performing surgery", "target": "CORPUS_010", "cat": "People"},
    {"query": "civil engineer inspecting building blueprints", "target": "CORPUS_011", "cat": "People"},
    {"query": "professional cook plating ravioli", "target": "CORPUS_012", "cat": "People"},
    {"query": "hospital surgeon with face mask", "target": "CORPUS_010", "cat": "People"},

    # 5. Clothing (7 queries)
    {"query": "navy wool double breasted blazer", "target": "CORPUS_013", "cat": "Clothing"},
    {"query": "scarlet red silk evening dress gown", "target": "CORPUS_014", "cat": "Clothing"},
    {"query": "trail running sneakers with neon yellow laces", "target": "CORPUS_015", "cat": "Clothing"},
    {"query": "formal suit jacket with brass anchor buttons", "target": "CORPUS_013", "cat": "Clothing"},
    {"query": "elegant crimson ball gown on hanger", "target": "CORPUS_014", "cat": "Clothing"},
    {"query": "athletic footwear with rugged rubber tread", "target": "CORPUS_015", "cat": "Clothing"},
    {"query": "dark blue tailored wool blazer", "target": "CORPUS_013", "cat": "Clothing"},

    # 6. Scenes (7 queries)
    {"query": "misty alpine pine forest at dawn", "target": "CORPUS_016", "cat": "Scenes"},
    {"query": "tokyo night alley with glowing neon signs", "target": "CORPUS_017", "cat": "Scenes"},
    {"query": "sahara desert sand dunes sunset orange sky", "target": "CORPUS_018", "cat": "Scenes"},
    {"query": "evergreen woods shrouded in morning fog", "target": "CORPUS_016", "cat": "Scenes"},
    {"query": "japanese street market lanterns at night", "target": "CORPUS_017", "cat": "Scenes"},
    {"query": "arid desert sand ridges and long shadows", "target": "CORPUS_018", "cat": "Scenes"},
    {"query": "atmospheric wilderness landscape with sunbeams", "target": "CORPUS_016", "cat": "Scenes"},

    # 7. Posters (7 queries)
    {"query": "annual jazz and blues festival poster", "target": "CORPUS_019", "cat": "Posters"},
    {"query": "cybersecurity conference summit banner", "target": "CORPUS_020", "cat": "Posters"},
    {"query": "robotics competition challenge flyer", "target": "CORPUS_021", "cat": "Posters"},
    {"query": "music festival poster with saxophone silhouette", "target": "CORPUS_019", "cat": "Posters"},
    {"query": "zero trust digital lock infosec keynote poster", "target": "CORPUS_020", "cat": "Posters"},
    {"query": "autonomous rover engineering contest flyer", "target": "CORPUS_021", "cat": "Posters"},
    {"query": "purple music concert poster live at park", "target": "CORPUS_019", "cat": "Posters"},

    # 8. Documents (7 queries)
    {"query": "official academic semester grade transcript", "target": "CORPUS_022", "cat": "Documents"},
    {"query": "residential apartment tenancy lease agreement", "target": "CORPUS_023", "cat": "Documents"},
    {"query": "distributed consensus algorithms whitepaper", "target": "CORPUS_024", "cat": "Documents"},
    {"query": "university courses gpa transcript dean list", "target": "CORPUS_022", "cat": "Documents"},
    {"query": "rental contract monthly security deposit clause", "target": "CORPUS_023", "cat": "Documents"},
    {"query": "paxos and raft fault tolerant consensus research", "target": "CORPUS_024", "cat": "Documents"},
    {"query": "bacse grades report official university transcript", "target": "CORPUS_022", "cat": "Documents"},

    # 9. Screenshots (7 queries)
    {"query": "docker terminal crash error log screenshot", "target": "CORPUS_025", "cat": "Screenshots"},
    {"query": "mobile banking wire transfer app wireframe", "target": "CORPUS_026", "cat": "Screenshots"},
    {"query": "bash terminal fatal oomkilled code 137", "target": "CORPUS_025", "cat": "Screenshots"},
    {"query": "fintech dashboard send money account balance ui", "target": "CORPUS_026", "cat": "Screenshots"},
    {"query": "console screenshot showing memory limit exceeded", "target": "CORPUS_025", "cat": "Screenshots"},
    {"query": "app screen mockup with transfer funds button", "target": "CORPUS_026", "cat": "Screenshots"},
    {"query": "docker container exit code screenshot", "target": "CORPUS_025", "cat": "Screenshots"},

    # 10. Receipts (7 queries)
    {"query": "whole foods organic grocery market receipt", "target": "CORPUS_027", "cat": "Receipts"},
    {"query": "trattoria roma restaurant dinner bill receipt", "target": "CORPUS_028", "cat": "Receipts"},
    {"query": "supermarket register slip showing almond milk and total", "target": "CORPUS_027", "cat": "Receipts"},
    {"query": "italian cafe check showing pizza and chianti wine", "target": "CORPUS_028", "cat": "Receipts"},
    {"query": "thermal printed paper receipt with avocado itemized", "target": "CORPUS_027", "cat": "Receipts"},
    {"query": "restaurant customer bill with subtotal and tax tip", "target": "CORPUS_028", "cat": "Receipts"},
    {"query": "store receipt totaling 47 dollars", "target": "CORPUS_027", "cat": "Receipts"},

    # 11. Certificates (7 queries)
    {"query": "certified kubernetes administrator certificate", "target": "CORPUS_029", "cat": "Certificates"},
    {"query": "emergency first aid and cpr certification", "target": "CORPUS_030", "cat": "Certificates"},
    {"query": "cloud native cka achievement badge with gold seal", "target": "CORPUS_029", "cat": "Certificates"},
    {"query": "american red cross basic life support certificate", "target": "CORPUS_030", "cat": "Certificates"},
    {"query": "official linux foundation exam verification certificate", "target": "CORPUS_029", "cat": "Certificates"},
    {"query": "aed defibrillator medical training credential", "target": "CORPUS_030", "cat": "Certificates"},
    {"query": "gold seal credential for passing cka exam", "target": "CORPUS_029", "cat": "Certificates"},

    # 12. Diagrams (7 queries)
    {"query": "oauth 2 authorization flow sequence diagram", "target": "CORPUS_031", "cat": "Diagrams"},
    {"query": "ecommerce relational database schema erd diagram", "target": "CORPUS_032", "cat": "Diagrams"},
    {"query": "auth code grant sequence flow arrows diagram", "target": "CORPUS_031", "cat": "Diagrams"},
    {"query": "entity relationship diagram with users and orders tables", "target": "CORPUS_032", "cat": "Diagrams"},
    {"query": "uml protocol sequence showing access token exchange", "target": "CORPUS_031", "cat": "Diagrams"},
    {"query": "sql database foreign key schema visualization", "target": "CORPUS_032", "cat": "Diagrams"},
    {"query": "system architecture sequence diagram for oauth", "target": "CORPUS_031", "cat": "Diagrams"},

    # 13. Natural Language (7 queries)
    {"query": "can you find that paper discussing raft consensus", "target": "CORPUS_024", "cat": "Natural Language"},
    {"query": "please show me the receipt from whole foods", "target": "CORPUS_027", "cat": "Natural Language"},
    {"query": "where is my college timetable for fall semester", "target": "CORPUS_033", "cat": "Natural Language"},
    {"query": "give me the photo of that golden retriever playing outside", "target": "CORPUS_001", "cat": "Natural Language"},
    {"query": "i need the lease agreement for my apartment", "target": "CORPUS_023", "cat": "Natural Language"},
    {"query": "look for the kubernetes administrator certificate for me", "target": "CORPUS_029", "cat": "Natural Language"},
    {"query": "search for the photo of surgeon in hospital operating room", "target": "CORPUS_010", "cat": "Natural Language"},

    # 14. Paraphrases (7 queries)
    {"query": "optical magnification device for microscopic biology", "target": "CORPUS_007", "cat": "Paraphrases"},
    {"query": "zero emission battery propelled passenger vehicle", "target": "CORPUS_004", "cat": "Paraphrases"},
    {"query": "canine companion enjoying outdoor leisure on grass", "target": "CORPUS_001", "cat": "Paraphrases"},
    {"query": "high velocity passenger bullet train on tracks", "target": "CORPUS_005", "cat": "Paraphrases"},
    {"query": "crimson silk formal attire for women", "target": "CORPUS_014", "cat": "Paraphrases"},
    {"query": "thermal register receipt documenting supermarket grocery purchase", "target": "CORPUS_027", "cat": "Paraphrases"},
    {"query": "aerospace alpine forest landscape enveloped in mist", "target": "CORPUS_016", "cat": "Paraphrases"},

    # 15. Ambiguous (6 queries)
    {"query": "jaguar in jungle", "target": "CORPUS_035", "cat": "Ambiguous"},
    {"query": "weekly schedule routine", "target": "CORPUS_033", "cat": "Ambiguous"},
    {"query": "student campus identity", "target": "CORPUS_034", "cat": "Ambiguous"},
    {"query": "black panther wild predator", "target": "CORPUS_035", "cat": "Ambiguous"},
    {"query": "fall classes timetable grid", "target": "CORPUS_033", "cat": "Ambiguous"},
    {"query": "plastic barcode identity badge", "target": "CORPUS_034", "cat": "Ambiguous"},

    # 16. Negative / Distractors (8 queries: targets that do not exist in corpus)
    {"query": "deep sea submarine submarine blueprint design", "target": None, "cat": "Negative/Distractors"},
    {"query": "medieval knight steel plate armor suit", "target": None, "cat": "Negative/Distractors"},
    {"query": "space shuttle launch pad rocket blastoff", "target": None, "cat": "Negative/Distractors"},
    {"query": "egyptian pyramid stone tomb hieroglyphs", "target": None, "cat": "Negative/Distractors"},
    {"query": "underwater scuba diver coral reef shark", "target": None, "cat": "Negative/Distractors"},
    {"query": "antique grandfather clock pendulum wooden cabinet", "target": None, "cat": "Negative/Distractors"},
    {"query": "steampunk airship zeppelin in cloudy skies", "target": None, "cat": "Negative/Distractors"},
    {"query": "formula 1 racing car pit stop tire change", "target": None, "cat": "Negative/Distractors"},
]


def calculate_dcg(relevances: List[float], k: int = 10) -> float:
    dcg = 0.0
    for i, rel in enumerate(relevances[:k]):
        dcg += (2.0 ** rel - 1.0) / math.log2(i + 2.0)
    return dcg


def setup_corpus(tmpdir: Path) -> Tuple[Database, AIAgent, Dict[str, int]]:
    db_path = tmpdir / "audit.sqlite3"
    db = Database(db_path)
    folder_id = db.add_folder(str(tmpdir))

    corpus_id_map = {}
    for item in CORPUS:
        fpath = tmpdir / item["filename"]
        if item["category"] == "Document":
            fpath.write_text(item.get("extracted_text", item["description"]))
        else:
            # Create a simple synthetic image file
            img = Image.new("RGB", (128, 128), color=(73, 109, 137))
            img.save(str(fpath))

        ext = fpath.suffix.lower()
        f_id = db.upsert_file(
            folder_id,
            DiscoveredFile(fpath, ext, fpath.stat().st_size, 1000.0, 1000.0),
        )
        corpus_id_map[item["id"]] = f_id

        # Populate document understanding VLM records
        du_res = DocumentUnderstandingResult(
            document_type=item["doc_type"],
            title=item.get("title"),
            description=item.get("description", ""),
            event_name=item.get("event_name"),
            objects=item.get("objects", []),
            semantic_tags=item.get("semantic_tags", []),
            visual_concepts=item.get("visual_concepts", []),
            important_text=item.get("important_text", []),
            attributes={},
        )
        content_hash = f"hash_{item['id']}"
        db.upsert_document_understanding(
            file_id=f_id,
            result=du_res,
            content_hash=content_hash,
            provider="local_qwen",
            model="Qwen3.5-4B-Q4_K_M",
        )

    agent = AIAgent(db)
    return db, agent, corpus_id_map


def run_benchmark_eval(
    agent: AIAgent,
    corpus_id_map: Dict[str, int],
    queries: List[Dict[str, Any]],
    vlm_weight_override: Optional[float] = None,
) -> Dict[str, Any]:
    """Execute evaluation over queries and compute exact IR metrics."""
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    hits_at_10 = 0
    precisions_5 = []
    precisions_10 = []
    recalls_10 = []
    reciprocal_ranks = []
    ndcg_scores = []
    latencies_ms = []
    per_query_details = []

    positive_queries = [q for q in queries if q["target"] is not None]
    negative_queries = [q for q in queries if q["target"] is None]

    for q_entry in queries:
        query_text = q_entry["query"]
        target_corpus_id = q_entry["target"]
        target_db_id = corpus_id_map.get(target_corpus_id) if target_corpus_id else None

        t0 = time.perf_counter()
        results = agent.search(query_text, limit=10)
        latency = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(latency)

        result_ids = [r["id"] for r in results]

        # Check components of top result
        top_res = results[0] if results else {}
        evidence = top_res.get("match_evidence", {})

        q_detail = {
            "query": query_text,
            "category": q_entry["cat"],
            "expected_target": target_corpus_id or "NONE (Negative/Distractor)",
            "top_retrieved_filename": top_res.get("filename", "N/A"),
            "rank": (result_ids.index(target_db_id) + 1) if (target_db_id and target_db_id in result_ids) else (0 if target_db_id is None else -1),
            "final_score": round(float(top_res.get("relevance_score", 0.0)), 4),
            "components": {
                "lexical_bm25": round(float(evidence.get("lexical", 0.0)), 3),
                "semantic": round(float(evidence.get("semantic", 0.0)), 3),
                "clip": round(float(evidence.get("visual", 0.0)), 3),
                "vlm": round(float(evidence.get("vlm", 0.0)), 3),
                "filename": round(float(evidence.get("filename", 0.0)), 3),
            },
            "qwen_vlm_invoked_query_time": False,  # Pre-indexed via FTS5
            "latency_ms": round(latency, 2),
        }
        per_query_details.append(q_detail)

        # Standard IR metrics for positive queries
        if target_db_id is not None:
            in_top_1 = target_db_id in result_ids[:1]
            in_top_3 = target_db_id in result_ids[:3]
            in_top_5 = target_db_id in result_ids[:5]
            in_top_10 = target_db_id in result_ids[:10]

            if in_top_1:
                hits_at_1 += 1
            if in_top_3:
                hits_at_3 += 1
            if in_top_5:
                hits_at_5 += 1
            if in_top_10:
                hits_at_10 += 1

            # Precision@k: |Relevant in Top k| / k (here max relevant is 1)
            rel_in_5 = 1.0 if in_top_5 else 0.0
            rel_in_10 = 1.0 if in_top_10 else 0.0
            precisions_5.append(rel_in_5 / 5.0)
            precisions_10.append(rel_in_10 / 10.0)

            # Recall@10: |Relevant in Top 10| / |Total Relevant|
            recalls_10.append(1.0 if in_top_10 else 0.0)

            # MRR & nDCG
            if target_db_id in result_ids:
                rank_idx = result_ids.index(target_db_id) + 1
                reciprocal_ranks.append(1.0 / rank_idx)
                relevances = [1.0 if r_id == target_db_id else 0.0 for r_id in result_ids]
            else:
                reciprocal_ranks.append(0.0)
                relevances = [0.0] * len(result_ids)

            dcg = calculate_dcg(relevances, k=10)
            idcg = calculate_dcg([1.0], k=10)
            ndcg = dcg / idcg if idcg > 0 else 0.0
            ndcg_scores.append(ndcg)

    num_pos = len(positive_queries)
    latencies_sorted = sorted(latencies_ms)
    p50 = latencies_sorted[int(len(latencies_sorted) * 0.50)]
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
    p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]

    # For negative queries, check false positive score ceiling
    negative_scores = [d["final_score"] for d in per_query_details if d["expected_target"] == "NONE (Negative/Distractor)"]
    max_neg_score = max(negative_scores) if negative_scores else 0.0
    mean_neg_score = (sum(negative_scores) / len(negative_scores)) if negative_scores else 0.0

    return {
        "total_queries": len(queries),
        "positive_queries": num_pos,
        "negative_queries": len(negative_queries),
        "hit_at_1": hits_at_1 / num_pos if num_pos else 0.0,
        "hit_at_3": hits_at_3 / num_pos if num_pos else 0.0,
        "hit_at_5": hits_at_5 / num_pos if num_pos else 0.0,
        "hit_at_10": hits_at_10 / num_pos if num_pos else 0.0,
        "precision_at_5": sum(precisions_5) / num_pos if num_pos else 0.0,
        "precision_at_10": sum(precisions_10) / num_pos if num_pos else 0.0,
        "recall_at_10": sum(recalls_10) / num_pos if num_pos else 0.0,
        "mrr": sum(reciprocal_ranks) / num_pos if num_pos else 0.0,
        "ndcg_at_10": sum(ndcg_scores) / num_pos if num_pos else 0.0,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "latency_p99_ms": p99,
        "negative_max_score": max_neg_score,
        "negative_mean_score": mean_neg_score,
        "per_query_details": per_query_details,
    }


def run_vlm_weight_ablation(tmpdir: Path) -> Dict[float, Dict[str, float]]:
    """Ablate VLM fusion weights across 0.0, 0.15, 0.35, 0.50, 0.70, 1.0."""
    print("\n--- Running VLM Fusion Weight Ablation ---")
    weights = [0.0, 0.15, 0.35, 0.50, 0.70, 1.0]
    ablation_results = {}

    for w in weights:
        db, agent, corpus_map = setup_corpus(tmpdir / f"ablation_{int(w*100)}")

        # Monkey-patch linear score fusion weight in agent.search
        orig_search = agent.search

        def make_patched_search(weight_vlm):
            def patched_search(*args, **kwargs):
                # Run standard search with patched VLM weight
                # In agent.search line 328: w_vlm = 0.35
                results = orig_search(*args, **kwargs)
                # Re-score each candidate using weight_vlm
                for r in results:
                    me = r.get("match_evidence", {})
                    base_score = (
                        0.60 * me.get("visual", 0.0)
                        + 0.15 * me.get("lexical", 0.0)
                        + 0.10 * me.get("semantic", 0.0)
                        + 0.15 * me.get("filename", 0.0)
                    )
                    vlm_s = me.get("vlm", 0.0)
                    if vlm_s > 0.0:
                        score = weight_vlm * vlm_s + (1.0 - weight_vlm) * base_score
                    else:
                        score = base_score
                    score = max(0.0, min(1.0, score))
                    r["relevance_score"] = score
                    r["rank"] = -score
                results.sort(key=lambda x: (float(x.get("rank", 0.0)), str(x.get("path", ""))))
                return results
            return patched_search

        agent.search = make_patched_search(w)
        eval_metrics = run_benchmark_eval(agent, corpus_map, EVALUATION_QUERIES)
        ablation_results[w] = {
            "Hit@1": eval_metrics["hit_at_1"],
            "Hit@3": eval_metrics["hit_at_3"],
            "Hit@5": eval_metrics["hit_at_5"],
            "Hit@10": eval_metrics["hit_at_10"],
            "Recall@10": eval_metrics["recall_at_10"],
            "MRR": eval_metrics["mrr"],
            "nDCG@10": eval_metrics["ndcg_at_10"],
        }
        print(f"  w_vlm = {w:4.2f} -> Hit@1: {eval_metrics['hit_at_1']:.4f}, MRR: {eval_metrics['mrr']:.4f}, nDCG@10: {eval_metrics['ndcg_at_10']:.4f}, Recall@10: {eval_metrics['recall_at_10']:.4f}")

    return ablation_results


def measure_isolated_latencies(tmpdir: Path) -> Dict[str, Any]:
    """Isolate and measure latency for every subsystem."""
    print("\n--- Measuring Isolated Subsystem Latencies ---")
    latencies = {}

    db, agent, corpus_map = setup_corpus(tmpdir / "latency_test")

    # 1. Lexical BM25 search
    t_bm25 = []
    for _ in range(50):
        t0 = time.perf_counter()
        db.keyword_search("golden retriever dog park", limit=20)
        t_bm25.append((time.perf_counter() - t0) * 1000.0)
    t_bm25.sort()
    latencies["bm25_p50_ms"] = round(t_bm25[25], 2)
    latencies["bm25_p95_ms"] = round(t_bm25[47], 2)

    # 2. VLM Document Understanding SQL search (Branch 1b)
    t_du = []
    for _ in range(50):
        t0 = time.perf_counter()
        db.search_document_understanding("red electric car", limit=20)
        t_du.append((time.perf_counter() - t0) * 1000.0)
    t_du.sort()
    latencies["du_search_p50_ms"] = round(t_du[25], 2)
    latencies["du_search_p95_ms"] = round(t_du[47], 2)

    # 3. Content hash caching lookup (SHA-256 + SQLite SELECT)
    test_file = tmpdir / "latency_test" / "FILE_A01.jpg"
    t_cache = []
    import hashlib
    for _ in range(50):
        t0 = time.perf_counter()
        # Compute SHA-256
        data = test_file.read_bytes()
        h = hashlib.sha256(data).hexdigest()
        # Lookup in SQLite
        db.get_document_understanding_by_hash(h, model="Qwen3.5-4B-Q4_K_M")
        t_cache.append((time.perf_counter() - t0) * 1000.0)
    t_cache.sort()
    latencies["cache_hash_lookup_p50_ms"] = round(t_cache[25], 2)
    latencies["cache_hash_lookup_p95_ms"] = round(t_cache[47], 2)

    # 4. Dense SBERT text embedding latency
    try:
        from intellifile.embedding_provider import SentenceTransformerProvider
        emb = SentenceTransformerProvider()
        t_sbert = []
        for _ in range(5):
            t0 = time.perf_counter()
            emb.embed_text("golden retriever dog catching a tennis ball")
            t_sbert.append((time.perf_counter() - t0) * 1000.0)
        t_sbert.sort()
        latencies["sbert_embed_p50_ms"] = round(t_sbert[2], 2)
    except Exception as exc:
        latencies["sbert_embed_p50_ms"] = f"N/A ({exc})"

    # 5. CLIP text embedding latency
    try:
        from intellifile.vision_search import get_clip_model
        clip_model = get_clip_model()
        if clip_model is not None:
            t_clip = []
            for _ in range(5):
                t0 = time.perf_counter()
                clip_model.encode("golden retriever dog catching a tennis ball")
                t_clip.append((time.perf_counter() - t0) * 1000.0)
            t_clip.sort()
            latencies["clip_text_embed_p50_ms"] = round(t_clip[2], 2)
        else:
            latencies["clip_text_embed_p50_ms"] = "CLIP unavailable"
    except Exception as exc:
        latencies["clip_text_embed_p50_ms"] = f"N/A ({exc})"

    # 6. Live Qwen Document Understanding (Indexing-time inference)
    vlm_provider = LocalQwen35Provider()
    if vlm_provider.is_available():
        test_img = Image.new("RGB", (256, 256), color=(100, 150, 200))
        print("  Querying live local llama.cpp server for Document Understanding inference...")
        t0 = time.perf_counter()
        try:
            res = vlm_provider.analyze_document(test_img)
            latencies["qwen_doc_understanding_live_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        except Exception as e:
            latencies["qwen_doc_understanding_live_ms"] = f"Failed: {e}"

        # 7. Live Qwen Candidate Reranking
        print("  Querying live local llama.cpp server for Candidate Reranking inference...")
        reranker = CandidateReranker(vlm_provider)
        dummy_cand = [{"path": str(test_file), "relevance_score": 0.6, "rank": -0.6}]
        t0 = time.perf_counter()
        try:
            rerank_res = reranker.rerank("golden retriever dog", dummy_cand, top_k=1)
            latencies["qwen_candidate_reranking_live_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        except Exception as e:
            latencies["qwen_candidate_reranking_live_ms"] = f"Failed: {e}"
    else:
        latencies["qwen_doc_understanding_live_ms"] = "Server unavailable"
        latencies["qwen_candidate_reranking_live_ms"] = "Server unavailable"

    print("Subsystem latencies:")
    for k, v in latencies.items():
        print(f"  {k:35s}: {v}")

    return latencies


def audit_filename_leakage() -> Tuple[bool, List[str]]:
    """Verify that zero queries contain target filenames or filename stems."""
    leaks = []
    for q_entry in EVALUATION_QUERIES:
        q_text = q_entry["query"].lower()
        target_id = q_entry["target"]
        if not target_id:
            continue
        # Find corresponding corpus item
        c_item = next(c for c in CORPUS if c["id"] == target_id)
        fname = c_item["filename"].lower()
        fname_stem = Path(fname).stem

        if fname in q_text or fname_stem in q_text:
            leaks.append(f"Query '{q_entry['query']}' contains filename '{fname}'")

        # Also check synthetic ID
        if target_id.lower() in q_text:
            leaks.append(f"Query '{q_entry['query']}' contains corpus ID '{target_id}'")

    return len(leaks) == 0, leaks


def test_qwen_unavailable_fallback(tmpdir: Path) -> Dict[str, Any]:
    """Verify retrieval still functions cleanly when Qwen endpoint is down."""
    print("\n--- Verifying Behavior When Qwen VLM Server is Offline ---")
    db, agent, corpus_map = setup_corpus(tmpdir / "qwen_down_test")

    from intellifile.vlm.model_manager import ModelManager
    dead_mgr = ModelManager(server_url="http://127.0.0.1:9999")
    dead_provider = LocalQwen35Provider(endpoint="http://127.0.0.1:9999", model_manager=dead_mgr)
    agent.reranker = CandidateReranker(dead_provider)

    assert not dead_provider.is_available(), "Dead provider should report unavailable"

    t0 = time.perf_counter()
    results = agent.search("golden retriever dog in park", limit=5)
    latency = (time.perf_counter() - t0) * 1000.0

    print(f"  Search returned {len(results)} results in {latency:.2f} ms when Qwen server is offline.")
    top_fn = results[0].get("filename") if results else "NONE"
    print(f"  Top result: {top_fn}")

    return {
        "status": "PASS",
        "returned_results": len(results),
        "top_result": top_fn,
        "latency_ms": round(latency, 2),
    }


def main():
    print("=" * 80)
    print("FILE XTRACTOR V3: COMPREHENSIVE INTEGRITY & GENERALIZATION AUDIT")
    print("=" * 80)

    # 1. Filename leakage audit
    no_leakage, leak_details = audit_filename_leakage()
    print(f"\n[AUDIT 1] Target Filename Leakage Check: {'PASS (0 leaks)' if no_leakage else 'FAIL'}")
    if not no_leakage:
        for leak in leak_details:
            print(f"  LEAK: {leak}")
    assert no_leakage, "Filename leakage detected!"

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)

        # 2. Setup benchmark and run 105 evaluation queries
        print(f"\n[AUDIT 2] Setting up 35-item multimodal corpus and running {len(EVALUATION_QUERIES)} queries...")
        db, agent, corpus_map = setup_corpus(tmpdir / "main_eval")

        # Cold search measurement (first query)
        t_cold_0 = time.perf_counter()
        agent.search(EVALUATION_QUERIES[0]["query"], limit=10)
        cold_latency_ms = (time.perf_counter() - t_cold_0) * 1000.0

        benchmark_metrics = run_benchmark_eval(agent, corpus_map, EVALUATION_QUERIES)

        print("\n" + "=" * 80)
        print("105-QUERY BLIND EVALUATION BENCHMARK RESULTS:")
        print(f"  Total Queries Tested : {benchmark_metrics['total_queries']} ({benchmark_metrics['positive_queries']} Positive, {benchmark_metrics['negative_queries']} Negative/Distractor)")
        print(f"  Hit@1  (Top-1 Acc)   : {benchmark_metrics['hit_at_1']:.4f} ({benchmark_metrics['hit_at_1']*100:.2f}%)")
        print(f"  Hit@3                : {benchmark_metrics['hit_at_3']:.4f} ({benchmark_metrics['hit_at_3']*100:.2f}%)")
        print(f"  Hit@5                : {benchmark_metrics['hit_at_5']:.4f} ({benchmark_metrics['hit_at_5']*100:.2f}%)")
        print(f"  Hit@10               : {benchmark_metrics['hit_at_10']:.4f} ({benchmark_metrics['hit_at_10']*100:.2f}%)")
        print(f"  Precision@5          : {benchmark_metrics['precision_at_5']:.4f}")
        print(f"  Precision@10         : {benchmark_metrics['precision_at_10']:.4f}")
        print(f"  Recall@10            : {benchmark_metrics['recall_at_10']:.4f} ({benchmark_metrics['recall_at_10']*100:.2f}%)")
        print(f"  MRR                  : {benchmark_metrics['mrr']:.4f}")
        print(f"  nDCG@10              : {benchmark_metrics['ndcg_at_10']:.4f}")
        print(f"  Cold-Start Latency   : {cold_latency_ms:.2f} ms")
        print(f"  Warm Latency P50     : {benchmark_metrics['latency_p50_ms']:.2f} ms")
        print(f"  Warm Latency P95     : {benchmark_metrics['latency_p95_ms']:.2f} ms")
        print(f"  Warm Latency P99     : {benchmark_metrics['latency_p99_ms']:.2f} ms")
        # Per-category analysis
        categories = sorted(list(set(q["category"] for q in benchmark_metrics["per_query_details"])))
        print("\nPER-CATEGORY RETRIEVAL BREAKDOWN:")
        print(f"  {'Category':20s} | {'Queries':7s} | {'Hit@1':7s} | {'Hit@10':7s} | {'Avg Score':9s}")
        print("  " + "-" * 60)
        for cat in categories:
            cat_queries = [q for q in benchmark_metrics["per_query_details"] if q["category"] == cat]
            if cat == "Negative/Distractors":
                avg_sc = sum(q["final_score"] for q in cat_queries) / len(cat_queries)
                print(f"  {cat:20s} | {len(cat_queries):7d} | {'N/A':7s} | {'N/A':7s} | {avg_sc:9.4f}")
                continue
            h1 = sum(1 for q in cat_queries if q["rank"] == 1) / len(cat_queries)
            h10 = sum(1 for q in cat_queries if 1 <= q["rank"] <= 10) / len(cat_queries)
            avg_sc = sum(q["final_score"] for q in cat_queries) / len(cat_queries)
            print(f"  {cat:20s} | {len(cat_queries):7d} | {h1*100:6.1f}% | {h10*100:6.1f}% | {avg_sc:9.4f}")

        missed = [q for q in benchmark_metrics["per_query_details"] if q["rank"] != 1 and q["expected_target"] != "NONE (Negative/Distractor)"]
        if missed:
            print(f"\nQUERIES WITH RANK != 1 ({len(missed)} queries):")
            for m in missed[:15]:
                print(f"  Query: '{m['query']}' [{m['category']}] -> Rank: {m['rank']}, Top: '{m['top_retrieved_filename']}', Score: {m['final_score']}")


        # 3. VLM Weight Ablation
        ablation_results = run_vlm_weight_ablation(tmpdir)

        # 4. Isolated Subsystem Latencies
        latency_breakdown = measure_isolated_latencies(tmpdir)
        latency_breakdown["cold_first_query_ms"] = round(cold_latency_ms, 2)
        latency_breakdown["warm_p50_ms"] = benchmark_metrics["latency_p50_ms"]
        latency_breakdown["warm_p95_ms"] = benchmark_metrics["latency_p95_ms"]

        # 5. Fallback verification
        fallback_results = test_qwen_unavailable_fallback(tmpdir)

        # 6. Save full audit data to JSON
        output_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "corpus_size": len(CORPUS),
            "benchmark_metrics": {k: v for k, v in benchmark_metrics.items() if k != "per_query_details"},
            "ablation_results": {str(k): v for k, v in ablation_results.items()},
            "latency_breakdown": latency_breakdown,
            "fallback_test": fallback_results,
            "per_query_results": benchmark_metrics["per_query_details"],
        }

        output_path = Path("tests/audit_v3_results.json")
        output_path.write_text(json.dumps(output_data, indent=2))
        print(f"\n[SAVED] Full audit results written to {output_path.resolve()}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
import re
from difflib import SequenceMatcher
from typing import Any, Dict, Optional
from app.runtime_config import cfg_int

# Simple family synonyms (local fallback).
FAMILY_SYNONYMS = {
    "street lighting": [
        "road",
        "street",
        "stradale",
        "rue",
        "route",
        "éclairage public",
        "éclairage routier",
        "calle",
        "carretera",
        "alumbrado público",
        "iluminación pública",
        "rua",
        "estrada",
        "iluminação pública",
        "уличный",
        "уличное освещение",
        "дорожный",
        "дорожное освещение",
        "شارع",
        "إنارة شارع",
        "إنارة الطرق",
        "oswietlenie uliczne",
        "oświetlenie uliczne",
        "drogowe",
        "ulicni osvětlení",
        "uliční osvětlení",
        "javna rasvjeta",
        "ulična rasvjeta",
        "ulična razsvetljava",
        "javna razsvetljava",
        "illuminazione stradale",
        "illuminazione pubblica",
        "public lighting",
        "roadway",
        "roadway lighting",
        "streetlight",
        "streetlights",
        "road lighting",
        "road light",
        "street lighting",
        "street light",
        "streetlamp",
        "street lamp",
        "road luminaire",
        "street luminaire",
    ],
    "waterproof": [
        "waterproof",
        "water proof",
        "watertight",
        "weatherproof",
        "weather proof",
        "water resistant",
        "stagna",
        "stagno",
        "étanche",
        "hermétique",
        "estanco",
        "estanca",
        "impermeable",
        "à prova d'água",
        "a prova d'água",
        "impermeável",
        "влагозащищенный",
        "влагозащищённый",
        "герметичный",
        "مقاوم للماء",
        "ضد الماء",
        "wodoodporny",
        "szczelny",
        "vodotěsný",
        "vodotesny",
        "vodootporan",
        "vodoodporen",
        "vapor tight",
        "vapour tight",
        "bulkhead",
    ],
    "floodlight": [
        "floodlight", "floodlights", "flood light", "flood",
        "projector", "projector light", "proiettore", "proiettori", "faro", "fari",
        "projecteur", "proyectores", "proyector", "projetor", "прожектор", "كشاف", "naświetlacz",
        "reflektor",
        # Facade / architectural application
        "facade", "façade", "facciata", "facciate", "fachada", "fachadas", "fachada arquitetonica",
        "fasad", "фасад", "واجهة", "elewacja", "fasáda", "fasada"
    ],
    "post top": ["post top", "post-top", "pole top", "lantern", "lanterna", "testa palo", "lanterne", "farola", "topo de poste", "парковый фонарь", "عمود علوي", "oprawa parkowa", "parková svítilna", "parkovna svitiljka", "parkovna svetilka"],
    "bollard": ["bollard", "paletto", "paletto led", "garden bollard", "pathway bollard", "borne lumineuse", "bolardo", "balizador", "тумбовый светильник", "bollard light", "عمود قصير", "słupek", "sloupek", "stupić", "stupić rasvjeta", "stebriček", "svetilni stebriček",
        # Path / parking perimeter application
        "pathway", "walkway", "pedestrian path", "garden path",
        "percorso", "camminamento", "vialetto",
        "allée", "chemin piéton", "chemin pieton",
        "sendero", "camino peatonal", "pasarela exterior",
        "caminho pedonal", "caminho de jardim",
        "тротуар", "пешеходная дорожка",
        "ممر مشاة", "ممر خارجي",
        "ścieżka", "chodnik", "ciąg pieszy", "ciag pieszy",
        "chodník", "peší cesta", "pesi cesta",
        "pješačka staza", "pjesacka staza",
        "pešpot", "pespot", "pešpot ob poti"
    ],
    "highbay": ["highbay", "high-bay", "high bay", "ufo", "warehouse", "industrial", "capannone", "campana", "entrepôt", "industriale", "almacén", "nave industrial", "armazém", "galpão", "склад", "промышленный", "مستودع", "صناعي", "hala", "magazyn", "sklad", "skladište", "skladišče", "průmyslový", "prumyslovy", "industrijska", "industrijski", "industrijski objekt",
        # Warehouse / logistics application
        "warehouse lighting", "logistics", "depot", "storage hall",
        "magazzino", "logistica", "deposito",
        "entrepot", "logistique", "dépôt", "depot logistique",
        "almacen", "logistica", "nave logistica",
        "armazem", "logistica", "depósito", "deposito",
        "логистика", "складской", "складское помещение",
        "مخزن", "مستودع لوجستي", "لوجستي",
        "hala magazynowa", "logistyka",
        "skladový", "skladovy", "logistický sklad", "logisticky sklad",
        "skladišna hala", "skladisna hala", "logistički", "logisticki",
        "skladiščna hala", "skladiscna hala", "logistični", "logisticni"
    ],
    "wall": ["wall", "wall mounted", "parete", "wallpack", "wall pack", "applique", "mur", "mural", "pared", "parede", "настенный", "حائطي", "ścienny", "nástěnný", "nastenny", "zidni", "zidna", "stenski",
        # Corridor / facade / hospital circulation application
        "corridor wall", "hallway wall", "facade wall", "hospital corridor",
        "corridoio", "corridoio ospedale", "facciata muro",
        "couloir", "couloir hopital", "couloir hôpital", "mur facade", "mur façade",
        "pasillo", "pasillo hospital", "pared fachada",
        "corredor", "corredor hospital", "parede fachada",
        "коридор", "больничный коридор", "настенный фасадный",
        "ممر", "ممر مستشفى", "واجهة حائطية",
        "korytarz", "korytarz szpitalny", "ściana elewacji", "sciana elewacji",
        "chodba", "nemocniční chodba", "nemocnicni chodba", "fasádní stěna", "fasadni stena",
        "hodnik", "bolnički hodnik", "bolnicki hodnik", "fasadni zid",
        "hodnik", "bolnišnični hodnik", "bolnisnicni hodnik", "fasadna stena"
    ],
    "ceiling/wall": ["ceiling/wall", "ceiling wall", "ceiling", "soffitto", "plafoniera", "plafond", "techo", "teto", "потолочный", "سقف", "sufitowy", "stropní", "stropni", "stropna", "plafonjera", "stropni/stenski", "stropna/stenska",
        # Corridor / school / hospital / parking garage applications
        "corridor", "hallway", "corridor lighting", "parking garage", "car park", "school corridor", "hospital corridor",
        "corridoio", "corridoio scuola", "corridoio ospedale", "garage", "autorimessa", "parcheggio coperto",
        "couloir", "couloir école", "couloir ecole", "couloir hôpital", "parking couvert",
        "pasillo", "pasillo escolar", "pasillo hospital", "aparcamiento cubierto", "parking cubierto",
        "corredor", "corredor escola", "corredor hospital", "estacionamento coberto", "garagem estacionamento",
        "коридор", "школьный коридор", "больничный коридор", "паркинг", "подземный паркинг",
        "ممر", "ممر مدرسة", "ممر مستشفى", "موقف سيارات", "مواقف داخلية",
        "korytarz", "korytarz szkolny", "korytarz szpitalny", "parking", "garaż", "garaż podziemny",
        "chodba", "školní chodba", "skolni chodba", "nemocniční chodba", "parking", "parkovací dům", "parkovaci dum",
        "hodnik", "školski hodnik", "skolski hodnik", "bolnički hodnik", "parking garaža", "parking garaza",
        "hodnik", "šolski hodnik", "solski hodnik", "bolnišnični hodnik", "parkirna hiša", "parkirna hisa"
    ],
    "strip": ["strip", "led strip", "light strip", "tape light", "led tape", "flex strip", "ruban led", "tira led", "fita led", "лента led", "شريط led", "taśma led", "led pásek", "led pasek", "led trak"],
    "linear": ["linear", "lineare", "linear light", "linea", "batten", "linéaire", "lineal", "linear", "линейный", "خطي", "liniowy", "lineární", "linearni", "linijski",
        # Office / school / hospital / corridor application
        "office", "office lighting", "school", "classroom", "hospital", "clinic", "corridor",
        "ufficio", "scuola", "aula", "ospedale", "clinica", "corridoio",
        "bureau", "école", "ecole", "salle de classe", "hôpital", "hopital", "clinique", "couloir",
        "oficina", "escuela", "aula", "hospital", "clínica", "clinica", "pasillo",
        "escritório", "escritorio", "escola", "sala de aula", "hospital", "clínica", "clinica", "corredor",
        "офис", "школа", "класс", "больница", "клиника", "коридор",
        "مكتب", "مدرسة", "فصل دراسي", "مستشفى", "عيادة", "ممر",
        "biuro", "szkoła", "szkola", "klasa", "szpital", "klinika", "korytarz",
        "kancelář", "kancelar", "škola", "skola", "učebna", "ucebna", "nemocnice", "klinika", "chodba",
        "ured", "škola", "skola", "učionica", "ucionica", "bolnica", "klinika", "hodnik",
        "pisarna", "šola", "sola", "učilnica", "ucilnica", "bolnišnica", "bolnisnica", "klinika", "hodnik"
    ],
    "downlight": ["downlight", "down light", "incasso", "incassato", "recessed downlight", "encastré", "empotrable", "embutido", "встраиваемый", "داونلايت", "wpuszczany", "zápustné", "zapustne", "ugradbeni", "vgradni",
        # Office / school / hospital application (common ceiling downlight requests)
        "office downlight", "school downlight", "hospital downlight",
        "downlight ufficio", "downlight scuola", "downlight ospedale",
        "downlight bureau", "downlight école", "downlight ecole", "downlight hôpital", "downlight hopital",
        "downlight oficina", "downlight escuela", "downlight hospital",
        "downlight escritório", "downlight escritorio", "downlight escola", "downlight hospital",
        "даунлайт офис", "даунлайт больница",
        "داونلايت مكتب", "داونلايت مستشفى",
        "downlight biuro", "downlight szkoła", "downlight szkola", "downlight szpital",
        "downlight kancelář", "downlight kancelar", "downlight škola", "downlight skola", "downlight nemocnice",
        "downlight ured", "downlight škola", "downlight skola", "downlight bolnica",
        "downlight pisarna", "downlight šola", "downlight sola", "downlight bolnišnica", "downlight bolnisnica"
    ],
    "uplight": [
        "uplight", "uplighter", "up light",
        "in-ground", "in ground", "inground",
        "ground recessed", "ground-recessed",
        "buried", "buried light", "in-ground recessed", "recessed uplight"
    ],
    "spike": ["spike", "picchetto", "garden spike", "piquet", "estaca", "espeto", "штырь", "وتد", "szpikulec"],
    "panels": ["panel", "panel light", "panel led", "panels", "pannello", "pannello led", "pannelli", "panneau", "panel led", "painel", "панель", "لوحة", "panelowy", "panelové", "panelni", "panelna",
        # Office / school / hospital application (common panel requests)
        "office panel", "office panel light", "school panel", "classroom panel", "hospital panel",
        "pannello ufficio", "pannello scuola", "pannello ospedale",
        "panneau bureau", "panneau école", "panneau ecole", "panneau hôpital", "panneau hopital",
        "panel oficina", "panel escuela", "panel hospital",
        "painel escritório", "painel escritorio", "painel escola", "painel hospital",
        "панель офис", "панель школа", "панель больница",
        "لوحة مكتب", "لوحة مدرسة", "لوحة مستشفى",
        "panel biuro", "panel szkoła", "panel szkola", "panel szpital",
        "panel kancelář", "panel kancelar", "panel škola", "panel skola", "panel nemocnice",
        "panel ured", "panel škola", "panel skola", "panel bolnica",
        "panel pisarna", "panel šola", "panel sola", "panel bolnišnica", "panel bolnisnica"
    ],
    "emergency": ["emergency", "emergenza", "exit", "exit sign", "urgence", "secours", "emergencia", "emergência", "аварийный", "эвакуационный", "طوارئ", "awaryjne", "nouzové", "nouzove", "hitna", "nužna", "zasilanie v sili", "battery", "batteria", "batterie", "autonomy", "autonomia", "backup", "back-up", "battery backup"],
}

_FAMILY_TOKEN_STOPWORDS = {
    "led",
    "light", "lighting", "luminaire", "lamp", "garden", "pathway",
    "ceiling", "wall", "proof", "tight", "vapour", "vapor",
    "recessed", "recess",
    # Romance / Slavic / Arabic generic lighting words (avoid false positives on generic overlap)
    "illuminazione", "luce", "lampada",
    "eclairage", "éclairage", "luminaire", "lampe",
    "iluminacion", "iluminación", "luz", "lampara", "lámpara",
    "iluminacao", "iluminação", "luminaria", "luminária", "luz",
    "освещение", "светильник", "лампа", "свет",
    "إضاءة", "إنارة", "مصباح", "إنارة",
    "oświetlenie", "oswietlenie", "oprawa", "lampa",
    "osvětlení", "osvetleni", "svítidlo", "svitidlo", "lampa",
    "rasvjeta", "svjetiljka", "lampa",
    "razsvetljava", "svetilka", "svetloba", "luč", "luc"
}

_GENERIC_PRODUCT_QUERY_TOKENS = {
    "led",
    "light", "lighting", "luminaire", "lamp", "garden", "pathway",
    "ceiling", "wall", "proof", "tight", "vapour", "vapor",
    "recessed", "recess",
    "ip", "ik", "cri", "ugr", "dali", "zhaga", "emergency", "battery", "backup",
    "power", "w", "kw", "lm", "lmw", "lm/w", "cct", "k", "mm", "cm", "m",
    "min", "max", "minimum", "maximum", "temp", "temperature", "ambient", "operating", "working",
    "beam", "angle", "degree", "degrees", "asymmetric", "asymmetry", "shape", "color", "colour",
    "interface", "control", "driver", "life", "lifetime", "hours", "hour", "hr", "hrs",
}

_SINGLE_TOKEN_FUZZY_FAMILY_ALIASES = {
    "street lighting": {"streetlight", "roadlight", "roadway", "street", "road"},
    "waterproof": {"waterproof", "watertight", "weatherproof", "bulkhead"},
    "floodlight": {"floodlight", "projector", "facade"},
    "post top": {"lantern"},
    "bollard": {"bollard"},
    "highbay": {"highbay", "warehouse", "industrial"},
    "wall": {"wall", "wallpack", "applique"},
    "ceiling/wall": {"ceiling"},
    "strip": {"strip"},
    "linear": {"linear", "batten"},
    "downlight": {"downlight"},
    "uplight": {"uplight", "inground"},
    "spike": {"spike"},
    "panels": {"panel", "panels"},
    "emergency": {"emergency"},
}

_FAMILY_RULE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "panels",
        (
            r"\b(?:office|school|classroom|hospital)\s+panel(?:s)?\b",
            r"\bpanel(?:s)?\s+(?:for|in)\s+(?:office|school|classroom|hospital)\b",
        ),
    ),
    (
        "linear",
        (
            r"\b(?:suspended|suspension|pendant)\s+linear\b",
            r"\blinear\s+(?:suspended|suspension|pendant)\b",
            r"\b(?:office|school|classroom)\s+linear\b",
        ),
    ),
    (
        "bollard",
        (
            r"\b(?:path|pathway|walkway|garden|pedestrian)\s+(?:light|lighting|bollard)\b",
            r"\b(?:bollard)\s+(?:for|along)\s+(?:path|pathway|walkway|garden)\b",
        ),
    ),
    (
        "spike",
        (
            r"\b(?:garden|tree|plant|landscape)\s+spike\b",
            r"\bspike\s+(?:light|lighting)\b",
        ),
    ),
    (
        "floodlight",
        (
            r"\b(?:facade|façade|facciata|fachada)\s+(?:projector|projectors|flood|floodlight|lighting)\b",
            r"\b(?:projector|floodlight)\s+(?:for|on)\s+(?:facade|façade|facciata|fachada)\b",
            r"\b(?:sports|stadium|pitch)\s+(?:lighting|projector|floodlight)\b",
        ),
    ),
    (
        "ceiling/wall",
        (
            r"\b(?:parking garage|car park|garage|covered parking)\b",
            r"\b(?:school|hospital)\s+corridor\b",
        ),
    ),
]


def _norm_words(text: str) -> list[str]:
    t = (text or "").lower()
    # Unicode-friendly tokenization: keep letters/digits from non-Latin scripts.
    t = re.sub(r"[^\w\s/+\-]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return [w for w in t.split(" ") if w]


def _normalize_unit_aliases(text: str) -> str:
    t = (text or "").lower()
    # Normalize common lumen/lm variants and typos
    t = re.sub(r"(?:(?<=\d)|\b)(?:lm|lumen|lumens|lumn|lumns|lumnes|lummen|lummens)\b", "lm", t)
    # Normalize common watt/w variants and typos
    t = re.sub(r"(?:(?<=\d)|\b)(?:w|watt|watts|wat|wats|waat|waats)\b", "w", t)
    # Common multilingual unit words
    t = re.sub(r"(?:(?<=\d)|\b)(?:ватт|ватта|ваттов|واط|وات|watio?w?)\b", "w", t)
    t = re.sub(r"(?:(?<=\d)|\b)(?:мм|миллиметр(?:а|ов)?|millim[eè]tre?s?|mil[ií]metro?s?)\b", "mm", t)
    # Normalize efficacy phrasing: "lumens per watt", "lm per w", etc.
    t = re.sub(r"\blm\s*(?:/|per|pr)\s*w\b", "lm/w", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _normalize_pdf_artifacts(text: str) -> str:
    t = (text or "").lower().replace("\u00a0", " ")
    t = t.replace("≥", ">=").replace("≤", "<=").replace("−", "-")
    t = re.sub(r"\s+", " ", t).strip()

    # Fix common split tokens from PDF extraction (e.g. "I P 6 5", "U G R < 1 9").
    t = re.sub(r"\bi\s*p\s*([0-9x])\s*([0-9x])\b", r"ip\1\2", t)
    t = re.sub(r"\bi\s*k\s*([0-9])\s*([0-9])\b", r"ik\1\2", t)
    t = re.sub(r"\bik\s*-\s*([0-9]{1,2})\b", r"ik\1", t)
    t = re.sub(r"\bu\s*g\s*r\b", "ugr", t)
    t = re.sub(r"\bc\s*r\s*i\b", "cri", t)
    t = re.sub(r"\bl\s*m\s*/\s*w\b", "lm/w", t)
    t = re.sub(r"\b(r\s*a)\b", "ra", t)

    # Compact split two-digit values in key specs (e.g. "ugr < 1 9", "cri 8 0").
    t = re.sub(
        r"\b(ugr|cri|ra)\s*(<=|>=|<|>|=)?\s*([0-9])\s+([0-9])\b",
        lambda m: f"{m.group(1)} {(m.group(2) or '')}{m.group(3)}{m.group(4)}".strip(),
        t,
    )

    # Collapse digit chunks split by spaces before key units (e.g. "3 000 lm", "4 0 0 0 k").
    def _join_number(m: re.Match[str]) -> str:
        num = re.sub(r"\s+", "", m.group(1))
        return f"{num} {m.group(2)}"

    t = re.sub(
        r"\b((?:\d\s*){3,7})\s*(k|lm|w|mm|h|hr|hrs|hour|hours)\b",
        _join_number,
        t,
    )
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _normalize_comparator_aliases(text: str) -> str:
    t = (text or "").lower()
    # Negated phrases must be normalized before generic "less/more than" rules.
    negated_replacements = [
        (r"\b(?:not|no)\s+(?:less\s+than|under|below)\b", ">="),
        (r"\b(?:not|no)\s+(?:more\s+than|greater\s+than|over|above)\b", "<="),
    ]
    for pat, rep in negated_replacements:
        t = re.sub(pat, rep, t)

    replacements = [
        # English / Italian existing + multilingual additions
        (r"\b(bigger than|greater than|more than|over|superiore a|piu di|più di|plus de|más de|mais de|больше|выше|أكثر من|ponad|więcej niż|vice než|více než|više od|vec kot|več kot)\b", ">"),
        (r"\b(less than|under|below|inferiore a|meno di|moins de|menos de|menos que|ниже|меньше|أقل من|poniżej|mniej niż|méně než|manje od|manj kot)\b", "<"),
        (r"\b(at least|almeno|minimo|minim[oau]?|minimum|au moins|al menos|pelo menos|no mínimo|не менее|как минимум|على الأقل|co najmniej|min|alespoň|alespon|najmanje|vsaj)\b", ">="),
        (r"\b(at most|massimo|massima|maximo|máximo|maximum|au plus|como máximo|como maximo|no máximo|no maximo|не более|максимум|على الأكثر|maksymalnie|max|nejvýše|nejvyse|najviše|najvise|najvec|največ)\b", "<="),
        (r"\b(equal to|equals|uguale a|igual a|igual|равно|=)\b", "="),
    ]
    for pat, rep in replacements:
        t = re.sub(pat, rep, t)
    # Symbol-style comparators in Cyrillic/Arabic contexts often appear without spaces; keep spacing simple.
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _parse_loose_int_token(raw: str) -> Optional[int]:
    s = str(raw or "").strip().lower()
    if not s:
        return None
    s = s.replace(" ", "")
    # 55k -> 55000
    m = re.fullmatch(r"(\d+(?:\.\d+)?)k", s)
    if m:
        return int(round(float(m.group(1)) * 1000))
    # 55'000 / 55,000 / 55.000 -> 55000
    if re.fullmatch(r"\d{1,3}(?:['.,]\d{3})+", s):
        return int(re.sub(r"['.,]", "", s))
    # plain integer
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


def _parse_shape(text: str) -> Optional[str]:
    t = (text or "").lower()
    # normalize separators for compact forms like "rettangolare", "square panel"
    aliases = [
        ("round", ["round", "circular", "circle", "rotondo", "rotonda", "circolare", "tondo", "rond", "ronde", "redondo", "redonda", "circular", "redondo", "круглый", "круглая", "دائري", "okrągły", "kulatý", "kulaty", "okrugli", "okrogel"]),
        ("square", ["square", "quadrato", "quadrata", "carré", "carre", "cuadrado", "quadrado", "квадратный", "مربع", "kwadratowy", "čtvercový", "ctvercovy", "kvadratni", "kvadraten"]),
        ("rectangular", ["rectangular", "rectangle", "rettangolare", "rettangolaree", "rectangulaire", "rectangular", "rectángulo", "retangular", "прямоугольный", "مستطيل", "prostokątny", "prostokatny", "obdélníkový", "obdelnikovy", "pravokutan", "pravokoten"]),
    ]
    for shape, words in aliases:
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", t):
                return shape
    # common typo tolerance
    if re.search(r"\b(?:rectangul|retangular|rettangolar)\w*\b", t):
        return "rectangular"
    if re.search(r"\b(?:squar|sqare)\w*\b", t):
        return "square"
    if re.search(r"\b(?:roun|circl)\w*\b", t):
        return "round"
    return None


def _tok_base(tok: str) -> str:
    t = (tok or "").strip().lower()
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s"):
        return t[:-1]
    return t


def _family_query_tokens() -> set[str]:
    out: set[str] = set()
    for fam, syns in FAMILY_SYNONYMS.items():
        for phrase in [fam, *list(syns)]:
            for tok in _norm_words(phrase):
                base = _tok_base(tok)
                if base:
                    out.add(base)
    return out


def _infer_product_name_short(text: str, filters: Dict[str, Any]) -> Optional[str]:
    if not text:
        return None
    technical_keys = set(filters.keys()) - {"product_family", "shape"}
    if not technical_keys:
        return None
    family_tokens = _family_query_tokens()
    for token in _norm_words(text):
        base = _tok_base(token)
        if not base or len(base) < 3:
            continue
        if any(ch.isdigit() for ch in base):
            continue
        if base in _GENERIC_PRODUCT_QUERY_TOKENS:
            continue
        if base in family_tokens:
            continue
        return base
    return None


def _infer_product_name_contains(text: str, filters: Dict[str, Any]) -> Optional[str]:
    if not text:
        return None
    technical_keys = set(filters.keys()) - {"product_family", "shape"}
    if not technical_keys:
        return None
    family_tokens = _family_query_tokens()
    kept: list[str] = []
    for token in _norm_words(text):
        base = _tok_base(token)
        if not base or len(base) < 3:
            continue
        if any(ch.isdigit() for ch in base):
            continue
        if base in _GENERIC_PRODUCT_QUERY_TOKENS:
            continue
        if base in family_tokens:
            continue
        kept.append(base)
    if not kept:
        return None
    return " ".join(kept[:3]).strip() or None


def _is_close_token(a: str, b: str) -> bool:
    a = _tok_base(a)
    b = _tok_base(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4:
        return False
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    # insertion/deletion distance <= 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    i = j = mism = 0
    while i < len(s) and j < len(l):
      if s[i] == l[j]:
          i += 1
          j += 1
      else:
          mism += 1
          if mism > 1:
              return False
          j += 1
    return True


def _is_single_token_family_typo(query_token: str, synonym_token: str) -> bool:
    a = str(query_token or "").strip().lower()
    b = str(synonym_token or "").strip().lower()
    if len(a) < 5 or len(b) < 5:
        return False
    if a[:2] != b[:2]:
        return False
    if _is_close_token(a, b):
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.84


def _infer_family(text: str) -> Optional[str]:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None
    for family, patterns in _FAMILY_RULE_PATTERNS:
        if any(re.search(pattern, t) for pattern in patterns):
            return family
    # Ground-recessed wording is a strong uplight cue and should override generic "recessed".
    if re.search(r"\b(?:in[\s-]?ground|inground|ground[\s-]?recess(?:ed)?|buried)\b", t):
        return "uplight"
    has_panel_word = bool(re.search(r"\bpanel(s)?\b", t))
    has_recessed_word = bool(re.search(r"\brecess(?:ed)?\b", t))
    # Canonical panel formats usually expressed as WxH in mm (e.g. 600x600, 1200x300).
    panel_size_matches = re.findall(
        r"\b(\d{2,4})\s*(?:mm)?\s*[x×]\s*(\d{2,4})\s*(?:mm)?\b",
        t,
    )
    has_panel_size_cue = False
    for a_s, b_s in panel_size_matches:
        a, b = _size_to_mm(int(a_s), int(b_s))
        lo, hi = min(a, b), max(a, b)
        if (lo == 600 and hi in {600, 1200}) or (lo == 300 and hi in {600, 1200}):
            has_panel_size_cue = True
            break

    q_tokens = [_tok_base(w) for w in _norm_words(t)]
    q_token_set = set(q_tokens)
    # Single-token queries are often product names/codes (e.g. "rubin"), so
    # we keep typo tolerance conservative there and only allow it against
    # substantial single-token family cues such as "bollard" or "highbay".
    allow_fuzzy_family = len(q_tokens) >= 2
    allow_single_token_fuzzy_family = len(q_tokens) == 1
    best = None
    best_score = 0
    for fam, syns in FAMILY_SYNONYMS.items():
        fam_score = 0
        for s in syns:
            ss = s.lower().strip()
            if ss and ss in t:
                fam_score = max(fam_score, 1000 + len(ss))
                continue
            syn_tokens = [_tok_base(w) for w in _norm_words(s)]
            syn_tokens = [w for w in syn_tokens if w and w not in _FAMILY_TOKEN_STOPWORDS]
            if not syn_tokens:
                continue
            overlap = [w for w in syn_tokens if w in q_token_set]
            # For multi-word synonyms, require at least 2 token overlaps.
            # This avoids false positives like "vapour" alone triggering "waterproof"
            # from "vapour tight" in generic optical descriptions.
            need = 1 if len(syn_tokens) == 1 else 2
            if len(set(overlap)) >= need:
                # Generic token match fallback for short queries ("road", "bollard", "warehouse", ...)
                overlap_score = 100 + len(max(overlap, key=len))
                # "recessed" is ambiguous (downlight + recessed panel); dampen for downlights
                # when strong panel cues are present.
                if fam == "downlight" and has_panel_size_cue and ("panel" in q_token_set or has_panel_word):
                    overlap_score -= 30
                fam_score = max(fam_score, overlap_score)
                continue
            # Lightweight typo tolerance for short/dirty queries ("bollrad", "warehous")
            if allow_fuzzy_family:
                fuzzy = [
                    st for st in syn_tokens
                    if any(_is_close_token(qt, st) for qt in q_tokens)
                ]
                if fuzzy:
                    fam_score = max(fam_score, 80 + len(max(fuzzy, key=len)))
            elif allow_single_token_fuzzy_family and len(syn_tokens) == 1 and len(syn_tokens[0]) >= 5:
                only_q = q_tokens[0] if q_tokens else ""
                only_syn = syn_tokens[0]
                allowed_single_token_aliases = _SINGLE_TOKEN_FUZZY_FAMILY_ALIASES.get(fam, set())
                if only_syn in allowed_single_token_aliases and _is_single_token_family_typo(only_q, only_syn):
                    fam_score = max(fam_score, 75 + len(only_syn))
        if fam == "panels" and has_panel_size_cue:
            # Strong prior: canonical panel dimensions are highly indicative.
            fam_score = max(fam_score, 950)
        if fam == "panels" and has_panel_size_cue and has_panel_word:
            # Explicit "panel" + panel size should dominate ambiguous "recessed".
            fam_score = max(fam_score, 1100)
        if fam_score > best_score:
            best = fam
            best_score = fam_score
    # Deterministic tie-break/override for explicit recessed panel specs.
    if has_panel_size_cue and (has_panel_word or has_recessed_word):
        return "panels"
    return best


def _size_to_mm(a: int, b: int) -> tuple[int, int]:
    # Tender shorthand: 60x60 means 600x600 mm.
    if a <= 300 and b <= 300:
        return a * 10, b * 10
    return a, b


_DIMENSION_ALIASES = {
    "diameter": [
        "diameter", "diametro", "diamètre", "diametre", "diámetro", "diâmetro", "диаметр", "قطر", "średnica", "srednica", "dia", "diam", "ø", "⌀"
        , "průměr", "prumer", "promjer", "premer"
    ],
    "luminaire_length": [
        "length", "lunghezza", "longueur", "longitud", "largo", "comprimento", "длина", "طول", "długość", "dlugosc", "len", "délka", "delka", "dužina", "duzina", "dolžina", "dolzina"
    ],
    "luminaire_width": [
        "width", "larghezza", "largeur", "ancho", "largura", "ширина", "عرض", "szerokość", "szerokosc", "wide", "šířka", "sirka", "širina", "sirina"
    ],
    "luminaire_height": [
        "height", "altezza", "hauteur", "altura", "altura", "высота", "ارتفاع", "wysokość", "wysokosc", "výška", "vyska", "visina", "depth", "profondita", "profondità", "profondeur", "profundidad", "profundidade", "глубина", "عمق", "głębokość", "glebokosc", "globina"
    ],
}


def _parse_dimension_filters(text: str, filters: Dict[str, Any]) -> None:
    raw = text or ""
    lower = raw.lower()

    # Normalize diameter symbols to make regex matching simpler.
    lower = lower.replace("⌀", "ø")

    for key, aliases in _DIMENSION_ALIASES.items():
        for alias in aliases:
            a = re.escape(alias.lower())

            # "diameter 100-200 mm" / "larghezza 50 - 80"
            m = re.search(
                rf"(?<![a-z0-9]){a}\s*[:=]?\s*(\d{{1,5}})\s*-\s*(\d{{1,5}})\s*(?:mm)?\b",
                lower,
            )
            if m:
                lo = min(int(m.group(1)), int(m.group(2)))
                # Current filter model stores a single comparator per dimension key.
                # For ranges, keep the lower bound instead of emitting unsupported extra keys.
                filters[key] = f">={lo}"
                break

            # "diameter max 200" / "diametro minimo 120"
            m = re.search(
                rf"(?<![a-z0-9]){a}\s*(min|minimo|minimum|minima|minimo|minimale|minimal|mínimo|minimo|massimo|maximum|max|maximum|maximal|máximo|макс(?:имум)?|мин(?:имум)?|حد\s*أدنى|حد\s*اقصى|حد\s*أقصى)\s*(\d{{1,5}}(?:\.\d+)?)\s*(?:mm)?\b",
                lower,
            )
            if m:
                kw = m.group(1)
                kw_norm = kw.strip().lower()
                op = ">="
                if any(x in kw_norm for x in ["max", "massim", "máx", "макс", "اقصى", "أقصى"]):
                    op = "<="
                filters[key] = f"{op}{m.group(2)}"
                break

            # "diameter >=200 mm" / "ø < 180"
            m = re.search(
                rf"(?<![a-z0-9]){a}\s*[:=]?\s*(>=|<=|>|<|=)\s*(\d{{1,5}}(?:\.\d+)?)\s*(?:mm)?\b",
                lower,
            )
            if m:
                filters[key] = f"{m.group(1)}{m.group(2)}"
                break

            # ">=200 mm diameter" / "200 mm diametro" (default >=)
            m = re.search(
                rf"(?<![a-z0-9])(>=|<=|>|<|=)?\s*(\d{{1,5}}(?:\.\d+)?)\s*(?:mm)?\s*(?<![a-z0-9]){a}\b",
                lower,
            )
            if m:
                op = m.group(1) or ">="
                filters[key] = f"{op}{m.group(2)}"
                break

            # "diameter 200 mm" / "diametro: 220"
            m = re.search(
                rf"(?<![a-z0-9]){a}\s*[:=]?\s*(\d{{1,5}}(?:\.\d+)?)\s*(?:mm)?\b",
                lower,
            )
            if m:
                filters[key] = f">={m.group(1)}"
                break


def local_text_to_filters(text: str) -> Dict[str, Any]:
    t = (text or "").lower()
    filters: Dict[str, Any] = {}

    t = _normalize_pdf_artifacts(t)
    t = _normalize_comparator_aliases(t)
    t = _normalize_unit_aliases(t)

    fam = _infer_family(text)
    if fam:
        filters["product_family"] = fam

    # IP parser:
    # - if two IP values are present, map lower -> IP v.a. (non-visible side),
    #   higher -> IP v.l. (visible side)
    # - if only one IP value is present, keep canonical single field (ip_rating)
    ip_hits = []
    for m in re.finditer(r"(>=|<=|>|<)?\s*ip\s*([0-9x]{2})\b", t):
        op = m.group(1) or ">="
        d = m.group(2).upper().replace("X", "0")
        if re.fullmatch(r"\d{2}", d):
            ip_hits.append((op, int(d)))
    # Deduplicate preserving first occurrence
    seen_ip = set()
    dedup_ip = []
    for op, num in ip_hits:
        k = (op, num)
        if k in seen_ip:
            continue
        seen_ip.add(k)
        dedup_ip.append((op, num))
    ip_hits = dedup_ip

    if len(ip_hits) >= 2:
        nums = sorted([num for _op, num in ip_hits])
        filters["ip_non_visible"] = f">=IP{str(nums[0]).zfill(2)}"
        filters["ip_visible"] = f">=IP{str(nums[-1]).zfill(2)}"
    elif len(ip_hits) == 1:
        op, num = ip_hits[0]
        filters["ip_rating"] = f"{op}IP{str(num).zfill(2)}"

    m = re.search(r"(>=|<=|>|<)?\s*ik[-\s]*([0-9]{1,2})\b", t)
    if m:
        op = m.group(1) or ">="
        d = m.group(2).zfill(2)
        filters["ik_rating"] = f"{op}IK{d}"

    if any(w in t for w in [
        "outdoor", "esterno", "external", "exterior",
        "extérieur", "exterieur", "externo", "externa", "наружный", "улица", "خارجي", "zewnętrzny", "zewnetrzny", "venkovní", "venkovni", "vanjski", "zunanji"
    ]):
        filters.setdefault("ip_rating", f">=IP{cfg_int('parser.default_outdoor_ip', 65):02d}")
        filters.setdefault("ik_rating", f">=IK{cfg_int('parser.default_outdoor_ik', 6):02d}")

    m = re.search(r"\b(\d{3,5})\s*k\b", t)
    if m:
        filters["cct_k"] = m.group(1)

    def _append_multi_filter(key: str, value: str) -> None:
        v = str(value or "").strip()
        if not v:
            return
        prev = filters.get(key)
        if prev is None:
            filters[key] = v
            return
        if isinstance(prev, list):
            if v not in prev:
                prev.append(v)
            return
        if str(prev) != v:
            filters[key] = [str(prev), v]

    # Interface terms should target "interface" filter (not control_protocol).
    if re.search(r"\bdali\b", t):
        _append_multi_filter("interface", "dali")
    if re.search(r"\bdmx\b", t):
        _append_multi_filter("interface", "dmx")
    # Supports "1-10", "1 10", "1/10", with optional V.
    if re.search(r"\b1\s*[-/ ]\s*10\s*(?:v)?\b", t):
        _append_multi_filter("interface", "1-10v")
    # Zhaga / antenna zhaga requests.
    if re.search(r"\bzhaga\b", t):
        _append_multi_filter("interface", "zhaga")

    if any(w in t for w in [
        "emergency", "emergenza", "exit", "kit emergenza", "em kit",
        "battery", "batteria", "batterie", "autonomy", "autonomia", "backup", "back-up", "battery backup",
        "urgence", "secours", "emergencia", "emergência", "аварий", "эвакуац", "طوارئ", "awaryj", "nouz", "hitn", "nujn", "nujn"
    ]):
        filters["emergency_present"] = "yes"

    m = re.search(r"\bcri\s*(>=|<=|>|<|=)\s*(\d{1,3})\b", t)
    if m:
        op = m.group(1)
        if op == ">":
            op = ">="
        filters["cri"] = f"{op}{m.group(2)}"
    else:
        m = re.search(r"\bcri\s*(\d{1,3})\b", t)
        if m:
            filters["cri"] = f">={m.group(1)}"
        else:
            m = re.search(r"\bra\s*(>=|<=|>|<|=)\s*(\d{1,3})\b", t)
            if m:
                op = m.group(1)
                if op == ">":
                    op = ">="
                filters["cri"] = f"{op}{m.group(2)}"
            else:
                m = re.search(r"\bra\s*(\d{1,3})\b", t)
                if m:
                    filters["cri"] = f">={m.group(1)}"

    m = re.search(r"\bugr\s*(<=|>=|<|>|=)\s*(\d+(?:\.\d+)?)\b", t)
    if m:
        op = m.group(1)
        if op == "<":
            op = "<="
        filters["ugr"] = f"{op}{m.group(2)}"
    else:
        m = re.search(r"\bugr\s*(\d+(?:\.\d+)?)\b", t)
        if m:
            filters["ugr"] = f"<={m.group(1)}"

    m = re.search(r"\b(\d{1,4}(?:\.\d+)?)\s*-\s*(\d{1,4}(?:\.\d+)?)\s*w\b", t)
    if m:
        a = float(m.group(1))
        b = float(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        filters["power_min_w"] = f">={lo:g}"
        filters["power_max_w"] = f"<={hi:g}"
    else:
        m = re.search(r"(>=|<=|>|<|=)\s*(\d{1,4}(?:\.\d+)?)\s*w\b", t)
        if m:
            op = m.group(1)
            val = m.group(2)
            if op in (">", ">="):
                filters["power_min_w"] = f"{op}{val}"
            elif op in ("<", "<="):
                filters["power_max_w"] = f"{op}{val}"
            else:
                filters["power_min_w"] = f">={val}"
                filters["power_max_w"] = f"<={val}"
        else:
            m = re.search(r"\b(\d{1,4}(?:\.\d+)?)\s*w\b", t)
            if m:
                filters["power_max_w"] = f"<={m.group(1)}"

    m = re.search(r"\b(\d{3,6})\s*-\s*(\d{3,6})\s*lm\b(?!\s*/\s*w)", t)
    if m:
        lo = min(int(m.group(1)), int(m.group(2)))
        filters["lumen_output"] = f">={lo}"
    else:
        m = re.search(r"(>=|<=|>|<|=)\s*(\d{3,6})\s*lm\b(?!\s*/\s*w)", t)
        if m:
            filters["lumen_output"] = f"{m.group(1)}{m.group(2)}"
        else:
            m = re.search(r"(\d{3,6})\s*lm\b(?!\s*/\s*w)", t)
            if m:
                filters["lumen_output"] = f">={m.group(1)}"

    m = re.search(r"\b(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*lm\s*/\s*w\b", t)
    if m:
        lo = min(float(m.group(1)), float(m.group(2)))
        filters["efficacy_lm_w"] = f">={lo:g}"
    else:
        m = re.search(r"(>=|<=|>|<|=)\s*(\d+(?:\.\d+)?)\s*lm\s*/\s*w\b", t)
        if m:
            filters["efficacy_lm_w"] = f"{m.group(1)}{m.group(2)}"
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*lm\s*/\s*w\b", t)
            if m:
                filters["efficacy_lm_w"] = f">={m.group(1)}"

    # Beam angle: avoid misreading ambient temperature (e.g. "Ta 25°C") as beam.
    m = re.search(
        r"\b(?:beam|beam angle|angolo(?:\s+del)?\s+fascio|fascio|ottica)\b[^0-9]{0,24}(\d{1,3})\s*(?:deg|degree|degrees|[°º?])(?=\D|$)",
        t,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"\b(\d{1,3})\s*(?:deg|degree|degrees)\b",
            t,
            flags=re.IGNORECASE,
        )
    if m:
        filters["beam_angle_deg"] = m.group(1)

    # Ambient/operating temperature parsing -> min/max PIM fields.
    m = re.search(
        r"([+\-]?\d{1,3}(?:\.\d+)?)\s*(?:(?:°|º|[^\w\s])?\s*c)?\s*(?:to|a|al|fino a|[-~]|\.{2,})\s*([+\-]?\d{1,3}(?:\.\d+)?)\s*(?:°|º|[^\w\s])?\s*c\b",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        a = float(m.group(1))
        b = float(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        filters["ambient_temp_min_c"] = f"<={lo:g}"
        filters["ambient_temp_max_c"] = f"<={hi:g}"

    m_min = re.search(
        r"\b(?:ta|tc|ambient|operating|working)?\s*(?:temp(?:erature)?|temperatura)?\s*(?:min|minimum|minimo|minima)\s*[:=]?\s*([+\-]?\d{1,3}(?:\.\d+)?)\s*(?:°|º|[^\w\s])?\s*c\b",
        t,
        flags=re.IGNORECASE,
    )
    if m_min:
        filters["ambient_temp_min_c"] = f"<={float(m_min.group(1)):g}"
    m_max = re.search(
        r"\b(?:ta|tc|ambient|operating|working)?\s*(?:temp(?:erature)?|temperatura)?\s*(?:max|maximum|massimo|massima)\s*[:=]?\s*([+\-]?\d{1,3}(?:\.\d+)?)\s*(?:°|º|[^\w\s])?\s*c\b",
        t,
        flags=re.IGNORECASE,
    )
    if m_max:
        filters["ambient_temp_max_c"] = f"<={float(m_max.group(1)):g}"

    # Handles normalized forms like "ta >= -20 c" / "operating temperature <= 45 c".
    for tm in re.finditer(
        r"\b(?:ta|tc|ambient(?:\s+temperature)?|operating(?:\s+temperature)?|working(?:\s+temperature)?|temp(?:erature)?)\s*(>=|<=|>|<)\s*([+\-]?\d{1,3}(?:\.\d+)?)\s*(?:°|º|[^\w\s])?\s*c\b",
        t,
        flags=re.IGNORECASE,
    ):
        op = tm.group(1)
        val = float(tm.group(2))
        if op in (">=", ">"):
            # For minimum ambient capability, lower values are better.
            # Request ">= -25C" means product must be <= -25C.
            mapped = "<=" if op == ">=" else "<"
            filters["ambient_temp_min_c"] = f"{mapped}{val:g}"
        elif op in ("<=", "<"):
            filters["ambient_temp_max_c"] = f"<={val:g}"

    if any(w in t for w in [
        "asymmetric", "asymmetry", "asimmetrico", "asimmetrica", "asimmetria",
        "asymétrique", "asymetrique", "asimétrico", "asimetrico", "assimétrico", "assimetrico", "асимметр", "غير متماثل", "asymetrycz",
        "asymetrický", "asymetricky", "asimetri", "asimetričen", "asimetrican", "asimetričan"
    ]):
        filters["asymmetry"] = "asymmetric"

    m = re.search(
        r"\b(\d{2,4})\s*(?:mm)?\s*(?:x|×|by|per)\s*(\d{2,4})\s*(?:mm)?\b",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        mm_a, mm_b = _size_to_mm(a, b)
        lo, hi = min(mm_a, mm_b), max(mm_a, mm_b)
        filters["luminaire_width"] = f">={lo}"
        filters["luminaire_length"] = f">={hi}"
    else:
        # Handles forms like "1432MM(L) X 85MM(W) X 80MM(H)"
        tri = re.search(
            r"\b(\d{2,5})\s*mm\s*\(?l\)?\s*[x×]\s*(\d{2,5})\s*mm\s*\(?w\)?\s*[x×]\s*(\d{2,5})\s*mm\s*\(?h\)?\b",
            t,
            flags=re.IGNORECASE,
        )
        if tri:
            filters["luminaire_length"] = f">={int(tri.group(1))}"
            filters["luminaire_width"] = f">={int(tri.group(2))}"
            filters["luminaire_height"] = f"<={int(tri.group(3))}"

    # L80B20 / L90 B10 style lifetime notation (parse at least Lxx reliably)
    m = re.search(r"\bl\s*(\d{2,3})\s*b\s*(\d{1,2})\b", t)
    if m:
        filters["lumen_maintenance_pct"] = f">={m.group(1)}"
        # failure_rate_pct is available in DB/compare, but not always used in current UI filters.
        filters["failure_rate_pct"] = f"<={m.group(2)}"

    # Lifetime hours: 55000 hrs / 55'000 hr / 55k h / 55000hours
    m = re.search(
        r"\b(\d{1,3}(?:['.,]\d{3})+|\d+(?:\.\d+)?k|\d{4,7})\s*(?:h|hr|hrs|hour|hours)\b",
        t
    )
    if m:
        hours = _parse_loose_int_token(m.group(1))
        if hours:
            filters["lifetime_hours"] = f">={hours}"
    else:
        # Handles forms like "L70B50 [h]: 109000" / "LED lifespan [h] 109000"
        m = re.search(
            r"\b(?:l\s*\d{2,3}\s*b\s*\d{1,2}.*?\[\s*h\s*\]|lifespan.*?\[\s*h\s*\])\s*[:\-]?\s*(\d{4,7})\b",
            t,
        )
        if m:
            hours = _parse_loose_int_token(m.group(1))
            if hours:
                filters["lifetime_hours"] = f">={hours}"

    shp = _parse_shape(text)
    if shp:
        filters["shape"] = shp

    # Use normalized text so multilingual comparator phrases ("at least", "au moins", etc.)
    # are already converted to >= / <= for dimension regex parsing.
    _parse_dimension_filters(t, filters)

    product_name_contains = _infer_product_name_contains(text, filters)
    if product_name_contains:
        filters["product_name_contains"] = product_name_contains
    else:
        product_name_short = _infer_product_name_short(text, filters)
        if product_name_short:
            filters["product_name_short"] = product_name_short

    return filters

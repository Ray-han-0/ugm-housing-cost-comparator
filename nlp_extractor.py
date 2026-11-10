"""
nlp_extractor.py - Rule-based NLP Information Extraction for Indonesian Kos Listings
Extracts rent, electricity policies, hidden utility charges, deposits, facilities, and curfew.
"""

import re
from typing import Dict, Any, Optional

try:
    from .models import KosListing
except ImportError:
    from models import KosListing

# Known geospatial anchor coordinates in Sleman/Yogyakarta near UGM
NEIGHBORHOOD_COORDINATES = {
    "pogung": (-7.7592, 110.3731),
    "pogung dalangan": (-7.7585, 110.3742),
    "pogung baru": (-7.7610, 110.3755),
    "sendowo": (-7.7698, 110.3712),
    "sekip": (-7.7680, 110.3745),
    "karangmalang": (-7.7735, 110.3850),
    "klebengan": (-7.7692, 110.3872),
    "pandega": (-7.7550, 110.3770),
    "kaliurang km 5": (-7.7570, 110.3800),
    "blimbingsari": (-7.7710, 110.3680),
}


def clean_number(num_str: str) -> float:
    if not num_str:
        return 0.0
    s = str(num_str).replace("Rp", "").replace("rp", "").strip().replace(" ", "")
    if "." in s and "," in s:
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_comma > last_dot:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        if len(parts[-1]) <= 2:
            s = "".join(parts[:-1]) + "." + parts[-1]
        else:
            s = s.replace(".", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) <= 2:
            s = "".join(parts[:-1]) + "." + parts[-1]
        else:
            s = s.replace(",", "")

    try:
        cleaned_str = re.sub(r"[^\d\.-]", "", s)
        return float(cleaned_str) if cleaned_str else 0.0
    except ValueError:
        return 0.0


def extract_kos_attributes_from_text(raw_text: str, kos_id: str = "KOS-01") -> KosListing:
    """
    Parses unstructured Indonesian kos listing description into a structured KosListing.
    """
    text_lower = raw_text.lower()
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    title = lines[0] if lines else "Kost Mahasiswa Jogja"
    if len(title) > 50:
        title = title[:50]

    # 1. Base Rent Price Extraction
    # Matches patterns like '1.200.000 / bulan', '1,5 jt per bln', 'Rp 15.000.000 / tahun', '850.000/bln'
    base_rent = 1000000.0
    period = "bulan"

    rent_patterns = [
        re.compile(r"(?:harga|sewa|tarif|biaya)?\s*(?:rp\.?\s*)?([\d\.,]+)\s*(?:jt|juta)?\s*/?\s*(?:per\s*)?(bulan|bln|thn|tahun|semester)", re.IGNORECASE),
        re.compile(r"(?:rp\.?\s*)?([\d\.,]+)\s*(?:jt|juta)?\s*(?:/|\bper\b)\s*(bulan|bln|thn|tahun|semester)", re.IGNORECASE),
        re.compile(r"(?:rp\.?\s*)?([\d\.,]{6,})", re.IGNORECASE)
    ]

    matched_rent = False
    for pat in rent_patterns:
        m = pat.search(raw_text)
        if m:
            val_raw = m.group(1)
            raw_period = m.group(2).lower() if len(m.groups()) >= 2 and m.group(2) else "bulan"

            if "jt" in m.group(0).lower() or "juta" in m.group(0).lower():
                val = float(val_raw.replace(",", ".")) * 1000000.0
            else:
                val = clean_number(val_raw)

            if val > 100000:
                if "thn" in raw_period or "tahun" in raw_period:
                    base_rent = val / 12.0
                    period = "tahun"
                elif "semester" in raw_period:
                    base_rent = val / 6.0
                    period = "semester"
                else:
                    base_rent = val
                    period = "bulan"
                matched_rent = True
                break

    # 2. Electricity System Extraction
    # Token vs Include
    electricity_system = "token"
    if any(k in text_lower for k in ["listrik gratis", "bebas listrik", "include listrik", "termasuk listrik", "free listrik"]):
        electricity_system = "gratis"
    elif any(k in text_lower for k in ["token", "listrik pulsa", "bayar sendiri", "exclude listrik", "tidak termasuk listrik"]):
        electricity_system = "token"

    # 3. Water, Trash & Security Fees
    water_fee = 0.0
    trash_fee = 0.0
    wifi_fee = 0.0

    water_match = re.search(r"(?:air|pdam)\s*(?:rp\.?\s*)?([\d\.,]{4,})", text_lower)
    if water_match:
        water_fee = clean_number(water_match.group(1))

    trash_match = re.search(r"(?:sampah|kebersihan|keamanan|iuran)\s*(?:rp\.?\s*)?([\d\.,]{4,})", text_lower)
    if trash_match:
        trash_fee = clean_number(trash_match.group(1))

    wifi_fee_match = re.search(r"(?:wifi|internet)\s*(?:rp\.?\s*)?([\d\.,]{4,})", text_lower)
    if wifi_fee_match and "gratis" not in wifi_fee_match.group(0) and "free" not in wifi_fee_match.group(0):
        wifi_fee = clean_number(wifi_fee_match.group(1))

    # 4. Deposit Extraction
    deposit_amount = 0.0
    deposit_match = re.search(r"(?:deposit|jaminan)\s*(?:rp\.?\s*)?([\d\.,]{5,})", text_lower)
    if deposit_match:
        deposit_amount = clean_number(deposit_match.group(1))
    elif "deposit 1 bulan" in text_lower:
        deposit_amount = base_rent

    # 5. Minimum Contract Period
    min_contract_months = 12 if period == "tahun" else 1
    contract_match = re.search(r"minimal\s*(\d+)\s*(bulan|thn|tahun)", text_lower)
    if contract_match:
        c_val = int(contract_match.group(1))
        c_unit = contract_match.group(2)
        min_contract_months = c_val * 12 if "thn" in c_unit or "tahun" in c_unit else c_val

    # 6. Curfew (Jam Malam)
    curfew = "24 Jam"
    if any(k in text_lower for k in ["24 jam", "bebas", "bawa kunci sendiri", "akses 24 jam"]):
        curfew = "24 Jam"
    elif "jam 22" in text_lower or "22.00" in text_lower or "22:00" in text_lower:
        curfew = "22:00 WIB"
    elif "jam 23" in text_lower or "23.00" in text_lower or "23:00" in text_lower:
        curfew = "23:00 WIB"

    # 7. Facilities Detection
    has_ac = bool(re.search(r"\bac\b|air\s*conditioner", text_lower))
    has_km_dalam = bool(re.search(r"km\s*dalam|kamar\s*mandi\s*dalam|k\.mandi\s*dalam", text_lower))
    has_water_heater = bool(re.search(r"water\s*heater|air\s*panas", text_lower))
    has_wifi = bool(re.search(r"wifi|wi-fi|internet", text_lower))
    has_furnished = bool(re.search(r"kasur|lemari|meja|furnished|lengkap", text_lower))
    has_refrigerator = bool(re.search(r"kulkas", text_lower))

    # 8. Location Anchor Coordinates Guessing
    lat, lon = -7.7592, 110.3731 # Default Pogung
    address_hint = "Pogung, Sleman"
    for neighborhood, coords in NEIGHBORHOOD_COORDINATES.items():
        if neighborhood in text_lower:
            lat, lon = coords
            address_hint = neighborhood.title() + ", Sleman/Yogyakarta"
            break

    return KosListing(
        kos_id=kos_id,
        name=title,
        raw_text=raw_text,
        base_rent_monthly=round(base_rent, 2),
        rent_period=period,
        electricity_system=electricity_system,
        water_fee_monthly=water_fee,
        trash_security_fee_monthly=trash_fee,
        wifi_fee_monthly=wifi_fee,
        deposit_amount=deposit_amount,
        min_contract_months=max(1, min_contract_months),
        curfew=curfew,
        has_ac=has_ac,
        has_private_bathroom=has_km_dalam,
        has_water_heater=has_water_heater,
        has_wifi=has_wifi,
        has_furnished=has_furnished,
        has_refrigerator=has_refrigerator,
        latitude=lat,
        longitude=lon,
        address_hint=address_hint
    )


def extract_kos_from_url_or_text(input_source: str, kos_id: str = "KOS-01") -> KosListing:
    """
    Ingests boarding house listing from either a web URL (public ad link) or raw copied text.
    Strips HTML markup if URL is fetched and executes rule-based NLP extraction.
    """
    cleaned_input = input_source.strip()
    if cleaned_input.startswith("http://") or cleaned_input.startswith("https://"):
        import requests
        try:
            resp = requests.get(cleaned_input, timeout=3.0, headers={"User-Agent": "UGM-HousingComparator/1.0"})
            if resp.status_code == 200:
                raw_html = resp.text
                clean_text = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
                clean_text = re.sub(r"<style.*?</style>", " ", clean_text, flags=re.DOTALL | re.IGNORECASE)
                clean_text = re.sub(r"<[^>]+>", "\n", clean_text)
                clean_text = re.sub(r"\n\s*\n+", "\n", clean_text).strip()
                return extract_kos_attributes_from_text(clean_text, kos_id=kos_id)
        except Exception:
            pass
        return extract_kos_attributes_from_text(cleaned_input, kos_id=kos_id)

    return extract_kos_attributes_from_text(cleaned_input, kos_id=kos_id)


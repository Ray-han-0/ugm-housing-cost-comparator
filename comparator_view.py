"""
comparator_view.py - Side-by-side comparison matrix and interactive Leaflet map generator
"""

import os
import json
from typing import List, Dict, Any
try:
    from .models import KosListing, TrueCostBreakdown
    from .routing_engine import UGM_CAMPUS_CLUSTERS
except ImportError:
    from models import KosListing, TrueCostBreakdown
    from routing_engine import UGM_CAMPUS_CLUSTERS


def format_side_by_side_comparison(listings: List[KosListing],
                                   costs: List[TrueCostBreakdown],
                                   scores_info: List[Dict[str, Any]]) -> str:
    """
    Renders an ASCII side-by-side comparison table of boarding house listings.
    """
    if not listings:
        return "Tidak ada data hunian untuk dibandingkan."

    col_w = 26
    num_cols = len(listings)
    header_col_w = 28

    total_width = header_col_w + (col_w + 3) * num_cols + 2

    lines = []
    lines.append("=" * total_width)
    lines.append(f" MATRIKS KOMPARASI BIAYA RIIL & KELAYAKAN KOS MAHASISWA JOGJA ({len(listings)} Hunian)")
    lines.append("=" * total_width)

    # Header Row
    headers = [f"{'Atribut Evaluasi':<{header_col_w}}"]
    for l in listings:
        short_name = l.name[:col_w]
        headers.append(f"{short_name:<{col_w}}")
    lines.append(" | ".join(headers))
    lines.append("-" * total_width)

    # Attributes to compare
    def format_row(label, values):
        row = [f"{label:<{header_col_w}}"]
        for v in values:
            v_str = str(v)[:col_w]
            row.append(f"{v_str:<{col_w}}")
        return " | ".join(row)

    lines.append(format_row("Lokasi / Area", [l.address_hint.split(",")[0] for l in listings]))
    lines.append(format_row("Sewa Dasar Iklan", [f"Rp {l.base_rent_monthly:,.0f}/bln".replace(",", ".") for l in listings]))
    lines.append(format_row("Sistem Listrik", [l.electricity_system.title() for l in listings]))
    lines.append(format_row("Estimasi Beban Listrik", [f"Rp {c.estimated_electricity:,.0f}".replace(",", ".") for c in costs]))
    lines.append(format_row("Iuran Air + Sampah", [f"Rp {c.utility_fees:,.0f}".replace(",", ".") for c in costs]))
    lines.append(format_row("Amortisasi Deposit", [f"Rp {c.amortized_deposit:,.0f}".replace(",", ".") for c in costs]))
    lines.append("-" * total_width)
    lines.append(format_row("BIAYA RIIL (TRUE COST)", [f"Rp {c.true_monthly_cost:,.0f}/bln".replace(",", ".") for c in costs]))
    lines.append(format_row("Biaya Tersembunyi (Rp)", [f"+Rp {c.hidden_cost_monthly:,.0f}".replace(",", ".") for c in costs]))
    lines.append(format_row("Biaya Tersembunyi (%)", [f"+{c.hidden_cost_percentage:.1f}%" for c in costs]))
    lines.append("-" * total_width)
    lines.append(format_row("Fasilitas AC", ["Ya" if l.has_ac else "Tidak" for l in listings]))
    lines.append(format_row("Kamar Mandi Dalam", ["Ya" if l.has_private_bathroom else "Luar" for l in listings]))
    lines.append(format_row("Water Heater", ["Ya" if l.has_water_heater else "Tidak" for l in listings]))
    lines.append(format_row("Akses Jam Malam", [l.curfew for l in listings]))
    lines.append(format_row("Jarak ke Klaster UGM", [f"{s.get('distance_km', 0.0):.2f} km" for s in scores_info]))
    lines.append(format_row("Waktu Motor / Jalan", [f"{s.get('moto_min', 0)} m / {s.get('walk_min', 0)} m" for s in scores_info]))
    lines.append("-" * total_width)
    lines.append(format_row("SKOR KELAYAKAN (0-100)", [f"{s.get('livability_score', 0):.1f} poin" for s in scores_info]))
    lines.append("=" * total_width)

    return "\n".join(lines)


def generate_interactive_map_html(listings: List[KosListing],
                                  costs: List[TrueCostBreakdown],
                                  scores_info: List[Dict[str, Any]],
                                  output_filepath: str) -> str:
    """
    Builds a standalone interactive OpenStreetMap HTML map using Leaflet.js.
    Renders markers for all kos listings and UGM campus cluster gates.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

    kos_markers = []
    for l, c, s in zip(listings, costs, scores_info):
        score = s.get("livability_score", 75.0)
        color = "#2E7D32" if score >= 80.0 else ("#0284C7" if score >= 65.0 else "#D97706")
        popup_html = (
            f"<b>{l.name}</b><br/>"
            f"Alamat: {l.address_hint}<br/>"
            f"Sewa Iklan: Rp {l.base_rent_monthly:,.0f}/bln<br/>"
            f"<b>Biaya Riil: Rp {c.true_monthly_cost:,.0f}/bln</b> (+{c.hidden_cost_percentage}%)<br/>"
            f"Fasilitas: {'AC, ' if l.has_ac else ''}{'KM Dalam, ' if l.has_private_bathroom else ''}{'Wifi' if l.has_wifi else ''}<br/>"
            f"Jarak ke Kampus: {s.get('distance_km', 1.0):.2f} km<br/>"
            f"<b>Skor Kelayakan: {score:.1f}%</b>"
        ).replace(",", ".")

        kos_markers.append({
            "name": l.name,
            "lat": l.latitude,
            "lon": l.longitude,
            "color": color,
            "score": score,
            "popup": popup_html
        })

    cluster_markers = []
    for c_key, c_val in UGM_CAMPUS_CLUSTERS.items():
        cluster_markers.append({
            "name": c_val.name,
            "lat": c_val.latitude,
            "lon": c_val.longitude,
            "desc": c_val.description
        })

    html_template = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Peta Interaktif Kelayakan Hunian Mahasiswa UGM</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    #header {{ background: #0B2545; color: #FFFFFF; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }}
    #header h1 {{ margin: 0; font-size: 18px; font-weight: 600; }}
    #header p {{ margin: 4px 0 0; font-size: 12px; color: #B8860B; }}
    #map {{ height: calc(100vh - 65px); width: 100%; }}
    .legend {{ background: white; padding: 10px 14px; line-height: 20px; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); font-size: 12px; }}
    .legend-dot {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; }}
  </style>
</head>
<body>
  <div id="header">
    <div>
      <h1>Peta Interaktif Titik Kelayakan Kos Mahasiswa Jogja</h1>
      <p>Departemen Ilmu Komputer dan Elektronika FMIPA UGM | True Housing Cost & OSRM Routing</p>
    </div>
    <div style="font-size: 13px;">Total Evaluasi: {len(listings)} Kos</div>
  </div>
  <div id="map"></div>

  <script>
    var map = L.map('map').setView([-7.768, 110.378], 14);

    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> kontributor'
    }}).addTo(map);

    var clusters = {json.dumps(cluster_markers)};
    clusters.forEach(function(c) {{
      var marker = L.circleMarker([c.lat, c.lon], {{
        radius: 9,
        fillColor: '#0B2545',
        color: '#B8860B',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.95
      }}).addTo(map);
      marker.bindPopup("<b>" + c.name + "</b><br/>" + c.desc);
    }});

    var kosList = {json.dumps(kos_markers)};
    kosList.forEach(function(k) {{
      var marker = L.circleMarker([k.lat, k.lon], {{
        radius: 11,
        fillColor: k.color,
        color: '#FFFFFF',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      }}).addTo(map);
      marker.bindPopup(k.popup);
    }});

    var legend = L.control({{ position: 'bottomright' }});
    legend.onAdd = function (map) {{
      var div = L.DomUtil.create('div', 'legend');
      div.innerHTML += '<b>Legenda Titik:</b><br/>';
      div.innerHTML += '<span class="legend-dot" style="background:#0B2545; border: 1px solid #B8860B;"></span> Gerbang Klaster UGM<br/>';
      div.innerHTML += '<span class="legend-dot" style="background:#2E7D32;"></span> Sangat Layak (&ge; 80%)<br/>';
      div.innerHTML += '<span class="legend-dot" style="background:#0284C7;"></span> Cukup Layak (65-79%)<br/>';
      div.innerHTML += '<span class="legend-dot" style="background:#D97706;"></span> Kurang Efisien (&lt; 65%)<br/>';
      return div;
    }};
    legend.addTo(map);
  </script>
</body>
</html>"""

    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write(html_template)

    return output_filepath

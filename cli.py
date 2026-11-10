"""
cli.py - Command Line User Interface for Housing Comparator
Compares multiple boarding house ads/links and generates side-by-side matrices and interactive maps.
"""

import argparse
import os
import sys

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if CURR_DIR not in sys.path:
    sys.path.insert(0, CURR_DIR)

from nlp_extractor import extract_kos_from_url_or_text
from cost_calculator import calculate_true_monthly_cost, evaluate_livability_index
from routing_engine import calculate_route_to_ugm_cluster
from comparator_view import format_side_by_side_comparison, generate_interactive_map_html


def get_demo_listings():
    return [
        {
            "name": "Kost Putri Pogung Dalangan",
            "cluster": "Teknik",
            "text": (
                "KOST PUTRI POGUNG DALANGAN SLEMAN\n"
                "Harga sewa Rp 1.300.000 / bulan.\n"
                "Fasilitas kamar: AC, kamar mandi dalam, water heater, kasur, lemari.\n"
                "Listrik sistem token (bayar sendiri per kamar).\n"
                "Iuran air Rp 50.000 per bulan, sampah dan keamanan Rp 30.000.\n"
                "Uang jaminan / deposit Rp 600.000 di awal sewa (minimal 6 bulan).\n"
                "Akses bebas 24 jam bawa kunci gerbang sendiri.\n"
            )
        },
        {
            "name": "Kost Mahasiswa Sekip Unit",
            "cluster": "Vokasi",
            "text": (
                "KOS PUTRA SEKIP UGM\n"
                "Tarif 850.000 per bulan sudah termasuk listrik dan air (free wifi).\n"
                "Kamar mandi luar bersih, kasur busa, meja belajar, lemari pakaian.\n"
                "Tanpa uang deposit, minimal 1 bulan.\n"
                "Jam malam pukul 23:00 WIB demi keamanan.\n"
            )
        },
        {
            "name": "Kost Paviliun Karangmalang",
            "cluster": "FEB",
            "text": (
                "PAVILIUN MAHASISWA KARANGMALANG\n"
                "Biaya 1.500.000 / bln.\n"
                "Fasilitas lengkap: AC, KM Dalam, Kulkas mini di kamar, Kasur springbed.\n"
                "Listrik token pulsa mandiri. Iuran sampah dan wifi Rp 50.000.\n"
                "Deposit Rp 500.000 kontrak minimal 6 bulan.\n"
                "Bebas jam malam 24 jam.\n"
            )
        },
    ]


def main():
    parser = argparse.ArgumentParser(description="Agregator & Komparator Biaya Riil Kos Mahasiswa UGM")
    parser.add_argument("--cluster", "-c", type=str, default="Teknik", choices=["Teknik", "Vokasi", "FEB", "MIPA_Biologi"], help="Klaster fakultas tujuan mahasiswa UGM")
    parser.add_argument("--export-map", "-m", type=str, default="housing_map.html", help="Jalur simpan berkas peta interaktif Leaflet HTML")
    args = parser.parse_args()

    print("[*] Mode Demo: Mengingest 3 iklan kos di sekitar Pogung, Sekip, dan Karangmalang...")
    demos = get_demo_listings()

    listings = []
    costs = []
    scores_info = []

    for idx, d in enumerate(demos, start=1):
        listing = extract_kos_from_url_or_text(d["text"], kos_id=f"KOS-{idx:02d}")
        cost = calculate_true_monthly_cost(listing)
        dist_km, walk_min, moto_min, src = calculate_route_to_ugm_cluster(
            listing.latitude, listing.longitude, cluster_key=args.cluster, use_osrm_online=False
        )
        score, breakdown = evaluate_livability_index(listing, cost, distance_km=dist_km)

        listings.append(listing)
        costs.append(cost)
        scores_info.append({
            "distance_km": dist_km,
            "walk_min": walk_min,
            "moto_min": moto_min,
            "livability_score": score,
            "breakdown": breakdown
        })

    print("\n" + format_side_by_side_comparison(listings, costs, scores_info))

    map_path = os.path.abspath(args.export_map)
    generate_interactive_map_html(listings, costs, scores_info, map_path)
    print(f"\n[+] Peta interaktif Leaflet OpenStreetMap berhasil diterbitkan di: {map_path}")


if __name__ == "__main__":
    main()

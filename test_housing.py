"""
test_housing.py - Comprehensive Unit & Integration Tests for Housing Comparator
Tests NLP extraction, True Cost formula, OSRM geospatial routing, and livability ranking.
"""

import unittest
import os
import sys

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if CURR_DIR not in sys.path:
    sys.path.insert(0, CURR_DIR)

from models import KosListing, TrueCostBreakdown, KosComparisonResult
from nlp_extractor import extract_kos_attributes_from_text, extract_kos_from_url_or_text, clean_number
from cost_calculator import calculate_true_monthly_cost, evaluate_livability_index
from routing_engine import calculate_route_to_ugm_cluster, haversine_distance_km
from comparator_view import format_side_by_side_comparison, generate_interactive_map_html



class TestHousingComparator(unittest.TestCase):
    def test_nlp_extraction_annual_with_hidden_costs(self):
        sample_ad = (
            "KOST PUTRI POGUNG DALANGAN SLEMAN\n"
            "Harga sewa Rp 15.000.000 / tahun (minimal 1 tahun).\n"
            "Fasilitas kamar: AC, kamar mandi dalam, water heater, kasur springbed, lemari.\n"
            "Listrik sistem token (bayar sendiri per kamar).\n"
            "Iuran air Rp 50.000 per bulan, sampah dan keamanan Rp 30.000.\n"
            "Uang jaminan / deposit Rp 1.000.000 di awal sewa.\n"
            "Akses bebas 24 jam bawa kunci gerbang sendiri.\n"
        )
        listing = extract_kos_attributes_from_text(sample_ad, "KOS-01")

        # Annual Rp 15M / 12 = Rp 1,250,000 / month
        self.assertEqual(listing.base_rent_monthly, 1250000.0)
        self.assertEqual(listing.rent_period, "tahun")
        self.assertEqual(listing.electricity_system, "token")
        self.assertEqual(listing.water_fee_monthly, 50000.0)
        self.assertEqual(listing.trash_security_fee_monthly, 30000.0)
        self.assertEqual(listing.deposit_amount, 1000000.0)
        self.assertEqual(listing.min_contract_months, 12)
        self.assertTrue(listing.has_ac)
        self.assertTrue(listing.has_private_bathroom)
        self.assertTrue(listing.has_water_heater)
        self.assertEqual(listing.curfew, "24 Jam")

    def test_true_cost_formula_calculation(self):
        sample_ad = (
            "KOST POGUNG BARU AC\n"
            "Sewa 1.200.000 / bulan.\n"
            "Listrik token pulsa sendiri. Ada AC dan KM dalam.\n"
            "Iuran sampah 25.000.\n"
            "Deposit 600.000 (kontrak minimal 6 bulan).\n"
        )
        listing = extract_kos_attributes_from_text(sample_ad, "KOS-02")
        cost = calculate_true_monthly_cost(listing)

        # Base: 1,200,000
        # Electricity: Base (24) + AC (75.6) = 99.6 kWh * 1444.70 = ~Rp 143,892.12
        # Utility: 25,000
        # Amortized deposit: 600,000 / 6 = 100,000
        # True cost: 1,200,000 + 143,892 + 25,000 + 100,000 = ~1,468,892
        self.assertGreater(cost.true_monthly_cost, listing.base_rent_monthly)
        self.assertEqual(cost.amortized_deposit, 100000.0)
        self.assertAlmostEqual(cost.hidden_cost_monthly, cost.true_monthly_cost - listing.base_rent_monthly, places=2)
        self.assertGreater(cost.hidden_cost_percentage, 15.0)

    def test_geospatial_routing_to_ugm_clusters(self):
        # Pogung coordinates to Klaster Teknik
        pogung_lat, pogung_lon = -7.7592, 110.3731
        dist_km, walk_min, moto_min, src = calculate_route_to_ugm_cluster(
            pogung_lat, pogung_lon, "Teknik", use_osrm_online=False
        )

        self.assertGreater(dist_km, 0.5)
        self.assertLess(dist_km, 3.0)
        self.assertGreater(walk_min, 5.0)
        self.assertGreater(moto_min, 1.0)

    def test_livability_index_scoring(self):
        sample_ad = (
            "KOST EKSLUSIF SENDOWO UGM\n"
            "Harga 1.800.000 per bulan include listrik, wifi gratis.\n"
            "Fasilitas lengkap: AC, KM dalam, water heater, kasur, lemari.\n"
            "Bebas 24 jam.\n"
        )
        listing = extract_kos_attributes_from_text(sample_ad, "KOS-03")
        cost = calculate_true_monthly_cost(listing)
        score, breakdown = evaluate_livability_index(listing, cost, distance_km=0.6)

        self.assertGreaterEqual(score, 70.0)
        self.assertLessEqual(score, 100.0)
        self.assertIn("affordability_score", breakdown)
        self.assertIn("proximity_score", breakdown)
        self.assertIn("facilities_score", breakdown)

    def test_extract_kos_from_url_or_text(self):
        text_ad = "KOST POGUNG BARU Harga 1.000.000 / bln token listrik"
        listing = extract_kos_from_url_or_text(text_ad, "KOS-URL-01")
        self.assertEqual(listing.base_rent_monthly, 1000000.0)
        self.assertEqual(listing.electricity_system, "token")

    def test_side_by_side_comparison_matrix(self):
        sample_1 = extract_kos_attributes_from_text("KOS POGUNG 1.200.000 / bln AC token listrik", "KOS-01")
        sample_2 = extract_kos_attributes_from_text("KOS SEKIP 800.000 / bln include listrik", "KOS-02")
        cost_1 = calculate_true_monthly_cost(sample_1)
        cost_2 = calculate_true_monthly_cost(sample_2)
        scores_info = [
            {"distance_km": 0.8, "walk_min": 10.0, "moto_min": 3.0, "livability_score": 85.0},
            {"distance_km": 1.5, "walk_min": 18.0, "moto_min": 5.0, "livability_score": 75.0}
        ]

        matrix_str = format_side_by_side_comparison([sample_1, sample_2], [cost_1, cost_2], scores_info)
        self.assertIn("MATRIKS KOMPARASI BIAYA RIIL", matrix_str)
        self.assertIn("BIAYA RIIL (TRUE COST)", matrix_str)
        self.assertIn("SKOR KELAYAKAN", matrix_str)

    def test_generate_interactive_map_html(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
            temp_html = tf.name

        try:
            sample = extract_kos_attributes_from_text("KOS POGUNG 1.200.000 / bln AC", "KOS-01")
            cost = calculate_true_monthly_cost(sample)
            scores = [{"distance_km": 0.8, "livability_score": 85.0}]
            map_file = generate_interactive_map_html([sample], [cost], scores, temp_html)
            self.assertTrue(os.path.exists(map_file))

            with open(map_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("leaflet.js", content)
            self.assertIn("Peta Interaktif", content)
            self.assertIn("Klaster", content)
        finally:
            if os.path.exists(temp_html):
                os.remove(temp_pdf if 'temp_pdf' in locals() else temp_html)

    def test_routing_cluster_alias_and_coordinate_fallback(self):
        """
        Tests cluster aliases ('mipa', 'vokasi', 'ft') and boundary fallback
        when invalid or zero coordinates are supplied.
        """
        # Alias 'mipa' should route to Klaster MIPA & Biologi
        dist_mipa, walk_m, moto_m, src_m = calculate_route_to_ugm_cluster(
            -7.7592, 110.3731, cluster_key="mipa", use_osrm_online=False
        )
        self.assertGreater(dist_mipa, 0.2)
        self.assertIn("Local Haversine", src_m)

        # Invalid (0.0, 0.0) coordinates should safely fallback to default Jogja Pogung anchor
        dist_fb, walk_fb, moto_fb, src_fb = calculate_route_to_ugm_cluster(
            0.0, 0.0, cluster_key="Teknik", use_osrm_online=False
        )
        self.assertGreater(dist_fb, 0.5)
        self.assertLess(dist_fb, 5.0) # Should be ~1 km, not 10,000 km across the globe!
        self.assertIn("Default Jogja Anchor", src_fb)

    def test_clean_number_formats(self):
        self.assertEqual(clean_number("1.500.000"), 1500000.0)
        self.assertEqual(clean_number("50.000"), 50000.0)
        self.assertEqual(clean_number("50000.00"), 50000.0)
        self.assertEqual(clean_number("25,000.50"), 25000.5)
        self.assertEqual(clean_number("25.000,50"), 25000.5)
        self.assertEqual(clean_number(""), 0.0)


if __name__ == "__main__":
    unittest.main()



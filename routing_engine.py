"""
routing_engine.py - Open Geospatial Routing to UGM Campus Clusters
Calculates real road distance and travel durations to UGM faculty gates
using OpenStreetMap (OSRM public router) with local Haversine-Manhattan fallback.
"""

import math
import requests
from typing import Dict, Tuple, Optional
try:
    from .models import CampusCluster
except ImportError:
    from models import CampusCluster

# Official UGM Campus Cluster Gate Coordinates
UGM_CAMPUS_CLUSTERS = {
    "Teknik": CampusCluster(
        name="Klaster Teknik",
        latitude=-7.7667,
        longitude=110.3725,
        description="Fakultas Teknik UGM (Jl. Grafika No. 2)"
    ),
    "Vokasi": CampusCluster(
        name="Klaster Vokasi",
        latitude=-7.7745,
        longitude=110.3745,
        description="Sekolah Vokasi UGM (Sekip Unit II)"
    ),
    "FEB": CampusCluster(
        name="Klaster FEB",
        latitude=-7.7712,
        longitude=110.3789,
        description="Fakultas Ekonomika dan Bisnis UGM (Jl. Sosio Humaniora)"
    ),
    "MIPA_Biologi": CampusCluster(
        name="Klaster MIPA & Biologi",
        latitude=-7.7685,
        longitude=110.3752,
        description="FMIPA dan Fakultas Biologi UGM (Sekip Utara)"
    )
}

CLUSTER_ALIASES = {
    "teknik": "Teknik",
    "klaster teknik": "Teknik",
    "fakultas teknik": "Teknik",
    "ft": "Teknik",
    "vokasi": "Vokasi",
    "klaster vokasi": "Vokasi",
    "sekolah vokasi": "Vokasi",
    "sv": "Vokasi",
    "feb": "FEB",
    "klaster feb": "FEB",
    "ekonomi": "FEB",
    "mipa": "MIPA_Biologi",
    "fmipa": "MIPA_Biologi",
    "biologi": "MIPA_Biologi",
    "klaster mipa": "MIPA_Biologi",
    "klaster mipa & biologi": "MIPA_Biologi",
    "mipa_biologi": "MIPA_Biologi",
    "sekip": "MIPA_Biologi"
}

_ROUTING_CACHE: Dict[Tuple[float, float, str], Tuple[float, float, float, str]] = {}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates on Earth.
    """
    R = 6371.0 # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def calculate_route_to_ugm_cluster(kos_lat: float,
                                   kos_lon: float,
                                   cluster_key: str = "Teknik",
                                   use_osrm_online: bool = True) -> Tuple[float, float, float, str]:
    """
    Calculates road distance and travel times:
    Returns (distance_km, duration_walking_min, duration_motorcycle_min, routing_source)
    Safely handles cluster aliases, invalid coordinates, OSRM network timeouts, and local fallback.
    """
    # 1. Normalize cluster key
    norm_key = CLUSTER_ALIASES.get(cluster_key.lower().strip().replace(" ", "_"), cluster_key)
    if norm_key not in UGM_CAMPUS_CLUSTERS:
        norm_key = CLUSTER_ALIASES.get(cluster_key.lower().strip(), "Teknik")
    cluster = UGM_CAMPUS_CLUSTERS.get(norm_key, UGM_CAMPUS_CLUSTERS["Teknik"])

    # 2. Defensive coordinate boundary validation for Yogyakarta region
    orig_lat = kos_lat if kos_lat is not None else 0.0
    orig_lon = kos_lon if kos_lon is not None else 0.0

    is_valid_coords = (
        kos_lat is not None and kos_lon is not None and
        -8.5 <= kos_lat <= -7.0 and 109.5 <= kos_lon <= 111.5 and
        not (abs(kos_lat) < 0.001 and abs(kos_lon) < 0.001)
    )
    if not is_valid_coords:
        # Fallback to default Pogung anchor
        kos_lat, kos_lon = -7.7592, 110.3731
        coord_fallback_note = " (Default Jogja Anchor)"
    else:
        coord_fallback_note = ""

    cache_key = (round(orig_lat, 4), round(orig_lon, 4), norm_key, is_valid_coords)
    if cache_key in _ROUTING_CACHE:
        return _ROUTING_CACHE[cache_key]

    # 3. Try public OpenStreetMap OSRM routing API (HTTPS) if enabled
    if use_osrm_online:
        url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{kos_lon},{kos_lat};{cluster.longitude},{cluster.latitude}"
            f"?overview=false"
        )
        headers = {"User-Agent": "UGM-HousingComparator/1.0 (academic; capstone)"}
        try:
            resp = requests.get(url, headers=headers, timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                if "routes" in data and len(data["routes"]) > 0:
                    route = data["routes"][0]
                    dist_km = round(route["distance"] / 1000.0, 2)
                    if dist_km > 0.0:
                        motorcycle_min = round(max(2.0, (route["duration"] / 60.0) * 0.8), 1)
                        walking_min = round((dist_km / 4.5) * 60.0, 1)
                        res = (dist_km, walking_min, motorcycle_min, f"OpenStreetMap OSRM{coord_fallback_note}")
                        _ROUTING_CACHE[cache_key] = res
                        return res
        except Exception:
            pass

    # 4. Deterministic Local Fallback:
    # Haversine distance multiplied by 1.25 winding road coefficient for Jogja residential streets (gang-gang Pogung/Sekip)
    straight_km = haversine_distance_km(kos_lat, kos_lon, cluster.latitude, cluster.longitude)
    road_km = round(straight_km * 1.25, 2)

    walking_min = round((road_km / 4.5) * 60.0, 1)
    motorcycle_min = round((road_km / 25.0) * 60.0 + 1.5, 1) # 25 km/h motorcycle + 1.5 min intersection delay

    res = (road_km, walking_min, motorcycle_min, f"Local Haversine-Street Topology{coord_fallback_note}")
    _ROUTING_CACHE[cache_key] = res
    return res

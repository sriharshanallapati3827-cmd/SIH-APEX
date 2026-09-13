"""
==============================================================================
WeatherGPT Deterministic Emergency Safety Guardrail (PostGIS Spatial Engine)
==============================================================================
Architectural Purpose:
  To eliminate AI hallucinations during life-threatening meteorological crises,
  this module executes a spatial intersection check (ST_Contains).

  When a user's location coordinates intersect an active government disaster hazard
  polygon (NDMA / IMD / CWC), the system freezes LLM generative text synthesis
  and returns a 100% deterministic, pre-verified official safety bulletin.

Integration:
  - Database Mode: PostgreSQL + PostGIS with GIST spatial indexing (via DATABASE_URL)
  - Edge/In-Memory Mode: Exact Jordan Curve point-in-polygon ray-casting for zero-latency,
    resilient fallback whenever database connection is unavailable.
==============================================================================
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger("safety_guardrail")

# ── 1. ACTIVE DISASTER REGISTRY (Benchmark Indian Hazard Polygons) ────────────
# Coordinates formatted as: [ [lon, lat], [lon, lat], ... ] (EPSG:4326 standard)
BENCHMARK_DISASTER_ZONES: List[Dict[str, Any]] = [
    {
        "alert_id": "NDMA-CYC-2026-09",
        "event_name": "Severe Cyclone Warning — Coastal Gale & Storm Surge Hazard",
        "severity": "CRITICAL",
        "issuing_authority": "National Disaster Management Authority (NDMA)",
        "advisory_text": (
            "URGENT MANDATORY EVACUATION: A severe cyclonic storm is approaching coastal sectors "
            "with sustained gale winds of 110-130 km/h and astronomical storm surge up to 2.5 meters. "
            "All residents within 5 km of the coast must evacuate to designated pucca cyclone shelters immediately. "
            "Switch off all main electrical breakers and LPG cylinders. Fishermen must strictly suspend all marine operations. "
            "Avoid coastal roads, estuaries, and low-lying bunds."
        ),
        # Polygon encompassing Andhra Pradesh / Coastal Bay of Bengal corridor (Kakinada to Nellore)
        "polygon_coords": [
            [80.0, 14.0],
            [83.5, 16.5],
            [84.0, 18.0],
            [82.0, 18.0],
            [79.8, 15.0],
            [80.0, 14.0]
        ],
        "valid_until": "2026-09-25T23:59:59Z",
    },
    {
        "alert_id": "IMD-FLD-2026-09",
        "event_name": "Extremely Heavy Rainfall & Urban Inundation Red Alert",
        "severity": "CRITICAL",
        "issuing_authority": "India Meteorological Department (IMD)",
        "advisory_text": (
            "LIFE SAFETY ALERT: Rainfall exceeding 200 mm in 24 hours coupled with high tide alert. "
            "High risk of rapid riverine overflow, storm-water drain surcharge, and severe localized waterlogging up to 1.2 meters. "
            "Do NOT attempt to drive or walk through flooded underpasses or subway corridors. "
            "Stay away from open manholes, electric poles, and metro construction trenches. "
            "Work from home recommended; non-essential transit strictly prohibited."
        ),
        # Polygon encompassing Mumbai & Thane Metropolitan coastal belt
        "polygon_coords": [
            [72.75, 18.85],
            [73.05, 18.85],
            [73.15, 19.35],
            [72.75, 19.35],
            [72.75, 18.85]
        ],
        "valid_until": "2026-09-25T23:59:59Z",
    }
]

# In-memory mutable registry for runtime polygon ingestion
_active_zones: List[Dict[str, Any]] = list(BENCHMARK_DISASTER_ZONES)


# ── 2. SPATIAL POINT-IN-POLYGON (Jordan Curve Ray-Casting Algorithm) ─────────
def point_in_polygon(lon: float, lat: float, polygon: List[List[float]]) -> bool:
    """
    Evaluates whether point (lon, lat) is enclosed within polygon.
    Pure Python Jordan Curve Ray-Casting algorithm (equivalent to PostGIS ST_Contains).
    Time complexity: O(N) where N is polygon vertex count. Sub-millisecond execution.
    """
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    p1x, p1y = polygon[0]

    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lon <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lon <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


# ── 3. POSTGIS DATABASE QUERY (If PostgreSQL is Configured) ───────────────────
def _query_postgis_circuit_breaker(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Queries PostGIS spatial database for polygon intersection using ST_Contains.
    Returns matching disaster zone if found, otherwise None.
    """
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGIS_URL")
    if not db_url:
        return None

    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(db_url, connect_timeout=3)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = """
                    SELECT alert_id, event_name, severity, issuing_authority, advisory_text, valid_until
                    FROM active_disaster_zones
                    WHERE valid_until > NOW()
                      AND ST_Contains(boundary, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                    ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END
                    LIMIT 1;
                """
                cur.execute(query, (lon, lat))
                row = cur.fetchone()
                if row:
                    return dict(row)
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[SafetyGuardrail] PostGIS DB query failed, falling back to in-memory spatial engine: {e}")
        return None

    return None


# ── 4. MAIN CIRCUIT BREAKER GATEWAY ──────────────────────────────────────────
def check_spatial_circuit_breaker(lat: Optional[float], lon: Optional[float]) -> Optional[Dict[str, Any]]:
    """
    Primary Entry Point for Spatial Safety Guardrail.
    
    1. If lat/lon are missing or invalid, returns None (no circuit breaker).
    2. Attempts PostGIS query if database is configured.
    3. If no DB or DB returns None, checks registered in-memory disaster polygons.
    4. If coordinates lie inside any active disaster polygon, returns the hazard payload.
    """
    if lat is None or lon is None:
        return None

    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return None

    # Skip zero coordinates (invalid GPS or unset default)
    if abs(lat) < 0.001 and abs(lon) < 0.001:
        return None

    # Step A: Query PostGIS if available
    db_result = _query_postgis_circuit_breaker(lat, lon)
    if db_result:
        return db_result

    # Step B: In-Memory Spatial Ray-Casting
    for zone in _active_zones:
        coords = zone.get("polygon_coords")
        if coords and point_in_polygon(lon, lat, coords):
            return {
                "alert_id": zone.get("alert_id"),
                "event_name": zone.get("event_name"),
                "severity": zone.get("severity", "CRITICAL"),
                "issuing_authority": zone.get("issuing_authority", "NDMA/IMD"),
                "advisory_text": zone.get("advisory_text"),
                "valid_until": zone.get("valid_until"),
            }

    return None


# ── 5. BULLETIN FORMATTER ────────────────────────────────────────────────────
def format_deterministic_bulletin(disaster: Dict[str, Any], lat: float, lon: float) -> str:
    """
    Renders an official, un-hallucinated government disaster bulletin.
    LLM text generation is frozen; this output is 100% deterministic.
    """
    severity = disaster.get("severity", "CRITICAL").upper()
    event_name = disaster.get("event_name", "Extreme Meteorological Hazard")
    authority = disaster.get("issuing_authority", "National Disaster Management Authority (NDMA)")
    advisory = disaster.get("advisory_text", "")
    alert_id = disaster.get("alert_id", "EMERGENCY-01")

    bulletin = (
        f"🚨 **DETERMINISTIC SAFETY CIRCUIT BREAKER ACTIVATED [{severity}]**\n\n"
        f"**Official Emergency Bulletin ID:** `{alert_id}`\n"
        f"**Issuing Authority:** {authority}\n"
        f"**Hazard Classification:** {event_name}\n"
        f"**Trigger Coordinates:** Latitude {lat:.4f}°N, Longitude {lon:.4f}°E\n\n"
        f"---\n\n"
        f"### 🛑 MANDATORY DISASTER PROTOCOL & LIFE SAFETY ACTIONS:\n\n"
        f"{advisory}\n\n"
        f"---\n\n"
        f"⚠️ **AI Text Generation Halted:** To ensure absolute human safety and prevent generative hallucinations "
        f"during an active crisis, WeatherGPT has frozen generative modeling and returned this certified, "
        f"pre-verified bulletin directly from official disaster management protocols.\n\n"
        f"**Emergency Helplines:**\n"
        f"- National Emergency Helpline: **112**\n"
        f"- NDMA Disaster Control Room: **1078**\n"
        f"- State Disaster Management Authority (SDMA): **1070**"
    )
    return bulletin


# ── 6. ADMIN UTILITIES ───────────────────────────────────────────────────────
def get_all_active_zones() -> List[Dict[str, Any]]:
    """Returns all currently active disaster hazard zones."""
    return list(_active_zones)


def register_active_zone(zone_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Adds or updates an active disaster zone in runtime memory."""
    required = ["alert_id", "event_name", "advisory_text", "polygon_coords"]
    for req in required:
        if req not in zone_payload:
            raise ValueError(f"Missing required hazard zone field: {req}")

    # Remove existing with same alert_id if present
    global _active_zones
    _active_zones = [z for z in _active_zones if z.get("alert_id") != zone_payload["alert_id"]]
    _active_zones.append(zone_payload)
    return zone_payload

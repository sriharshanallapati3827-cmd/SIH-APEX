-- ==============================================================================
-- WeatherGPT Spatial Safety Guardrail Migration
-- PostGIS Setup for Deterministic Disaster Circuit Breaker Checks
-- ==============================================================================

-- 1. Enable PostGIS extension for spatial computing
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Create Active Disaster Hazard Zones table
CREATE TABLE IF NOT EXISTS active_disaster_zones (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(50) UNIQUE NOT NULL,
    event_name VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('CRITICAL', 'WARNING', 'WATCH', 'ADVISORY')),
    issuing_authority VARCHAR(50) NOT NULL DEFAULT 'NDMA/IMD',
    advisory_text TEXT NOT NULL,
    boundary GEOMETRY(Polygon, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL
);

-- 3. GIST Spatial Index for sub-millisecond point-in-polygon checks
CREATE INDEX IF NOT EXISTS idx_disaster_boundary 
ON active_disaster_zones USING GIST (boundary);

-- 4. Circuit Breaker Spatial Intersection Query:
-- SELECT alert_id, event_name, severity, issuing_authority, advisory_text
-- FROM active_disaster_zones
-- WHERE valid_until > NOW()
--   AND ST_Contains(boundary, ST_SetSRID(ST_MakePoint(:user_lon, :user_lat), 4326))
-- ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END
-- LIMIT 1;

-- 5. Seed Benchmark Indian Disaster Hazard Polygons (Active for testing)
-- Zone A: Coastal Cyclone High-Hazard Zone (Bay of Bengal / Kakinada-Machilipatnam-Nellore corridor)
INSERT INTO active_disaster_zones (alert_id, event_name, severity, issuing_authority, advisory_text, boundary, valid_until)
VALUES (
    'NDMA-CYC-2026-09',
    'Severe Cyclone Warning — Coastal Gale & Storm Surge Hazard',
    'CRITICAL',
    'National Disaster Management Authority (NDMA)',
    'URGENT MANDATORY EVACUATION: A severe cyclonic storm is approaching coastal sectors with sustained gale winds of 110-130 km/h and astronomical storm surge up to 2.5 meters. All residents within 5 km of the coast must evacuate to designated pucca cyclone shelters immediately. Switch off all main electrical breakers and LPG cylinders. Fishermen must suspend all operations. Strictly avoid sea walls, estuaries, and low-lying coastal bunds.',
    ST_GeomFromText('POLYGON((80.0 14.0, 83.5 16.5, 84.0 18.0, 82.0 18.0, 79.8 15.0, 80.0 14.0))', 4326),
    NOW() + INTERVAL '7 days'
) ON CONFLICT (alert_id) DO UPDATE 
SET advisory_text = EXCLUDED.advisory_text, valid_until = EXCLUDED.valid_until;

-- Zone B: Extreme Flash Flood & Monsoon Deluge Inundation Zone (Konkan / Mumbai Metropolitan Region)
INSERT INTO active_disaster_zones (alert_id, event_name, severity, issuing_authority, advisory_text, boundary, valid_until)
VALUES (
    'IMD-FLD-2026-09',
    'Extremely Heavy Rainfall & Urban Inundation Red Alert',
    'CRITICAL',
    'India Meteorological Department (IMD)',
    'LIFE SAFETY ALERT: Rainfall exceeding 200 mm in 24 hours coupled with high tide alert. High risk of rapid riverine overflow, storm-water drain surcharge, and severe localized waterlogging up to 1.2 meters. Do NOT attempt to drive or walk through flooded underpasses or subway corridors. Stay away from open manholes, electric poles, and metro construction trenches. Work from home recommended; non-essential transit strictly prohibited.',
    ST_GeomFromText('POLYGON((72.75 18.85, 73.05 18.85, 73.15 19.35, 72.75 19.35, 72.75 18.85))', 4326),
    NOW() + INTERVAL '7 days'
) ON CONFLICT (alert_id) DO UPDATE 
SET advisory_text = EXCLUDED.advisory_text, valid_until = EXCLUDED.valid_until;

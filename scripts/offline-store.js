/**
 * ==============================================================================
 * WeatherGPT Edge Storage Engine (IndexedDB)
 * ==============================================================================
 * Provides zero-friction client-side offline persistence:
 *   1. weather_telemetry: Caches latest weather telemetry and recommendations
 *   2. emergency_guidelines: Pre-verified government & disaster SOPs (offline accessible)
 *   3. chat_history: Offline persistent conversation memory
 * ==============================================================================
 */

(function () {
  const DB_NAME = 'WeatherGPT_EdgeDB';
  const DB_VERSION = 1;

  const EMERGENCY_SOPS = [
    {
      hazard_id: 'cyclone',
      title: 'Cyclone & Extreme Gale Wind Safety SOP (NDMA)',
      keywords: ['cyclone', 'storm', 'hurricane', 'gale', 'typhoon', 'windstorm'],
      severity: 'CRITICAL',
      guidelines: [
        'Disconnect all electrical appliances and switch off main gas valve.',
        'Stay indoors in the strongest part of your home, away from windows and glass doors.',
        'Keep emergency supplies ready: torch, dry batteries, essential medicines, drinking water (3-day supply).',
        'Do not venture outside during the eye of the cyclone; ferocious winds resume suddenly from the opposite direction.',
        'Fishermen: strictly suspend all inshore and offshore marine operations; secure boats above high-tide line.'
      ]
    },
    {
      hazard_id: 'flood',
      title: 'Flash Flood & Inundation Emergency SOP (IMD/CWC)',
      keywords: ['flood', 'inundation', 'waterlogging', 'overflow', 'deluge', 'drowning'],
      severity: 'CRITICAL',
      guidelines: [
        'Move immediately to designated higher ground or upper floor; never wait for water levels to rise.',
        'Do NOT walk, swim, or drive through moving floodwaters (15 cm of moving water can knock you down, 30 cm sweeps away vehicles).',
        'Stay clear of electric poles, fallen wires, and submerged transformers to prevent electrocution.',
        'Boil all drinking water or use water purification tablets before consumption.'
      ]
    },
    {
      hazard_id: 'heatwave',
      title: 'Severe Heatwave & Sunstroke Emergency SOP (NDMA)',
      keywords: ['heat', 'heatwave', 'loo', 'hot', 'sunstroke', 'dehydration', 'temperature'],
      severity: 'WARNING',
      guidelines: [
        'Avoid direct sun exposure between 12:00 PM and 3:30 PM.',
        'Drink ORS, homemade lemon water, lassi, buttermilk, or coconut water frequently, even if not thirsty.',
        'Wear lightweight, light-colored, loose, and porous cotton clothes.',
        'Farmers/Laborers: shift heavy outdoor fieldwork to early morning (05:30 - 09:30 AM) and late afternoon.',
        'Provide shade and ample clean drinking water for cattle and livestock.'
      ]
    },
    {
      hazard_id: 'lightning',
      title: 'Thunderstorm & Lightning Safety SOP (Damini/IMD)',
      keywords: ['lightning', 'thunder', 'thunderstorm', 'bijli', 'strike'],
      severity: 'CRITICAL',
      guidelines: [
        'Follow the 30-30 Rule: If time between lightning flash and thunder is <30 seconds, seek indoor shelter immediately.',
        'Never take shelter under tall or isolated trees or near metal tin sheds in open fields.',
        'If caught in an open field with no shelter: crouch low on balls of feet with feet together, head tucked, hands over ears (minimize ground contact). Never lie flat.',
        'Avoid contact with corded electrical appliances, plumbing pipes, and metal faucets during active lightning.'
      ]
    },
    {
      hazard_id: 'farmer_crop',
      title: 'Agro-Meteorological Extreme Weather Protocol (ICAR/KVK)',
      keywords: ['crop', 'farmer', 'harvest', 'pesticide', 'irrigation', 'fertilizer', 'sowing', 'hail'],
      severity: 'ADVISORY',
      guidelines: [
        'Heavy Rainfall Warning: Suspend all irrigation, pesticide spraying, and top-dressing of fertilizer immediately.',
        'Drain excess standing water from fields of pulses, cotton, and vegetables to prevent root asphyxiation.',
        'Matured Crops: Expedite harvesting and store harvested produce immediately on elevated platforms under waterproof tarpaulins.',
        'Hailstorm Risk: Erect protective anti-hail nets over vulnerable orchards and high-value vegetable nurseries.'
      ]
    }
  ];

  let dbPromise = null;

  function openDB() {
    if (dbPromise) return dbPromise;

    dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = function (event) {
        const db = event.target.result;

        // Store 1: Weather Telemetry cache
        if (!db.objectStoreNames.contains('weather_telemetry')) {
          const telemetryStore = db.createObjectStore('weather_telemetry', { keyPath: 'id' });
          telemetryStore.createIndex('timestamp', 'timestamp', { unique: false });
        }

        // Store 2: Emergency Guidelines
        if (!db.objectStoreNames.contains('emergency_guidelines')) {
          const sopsStore = db.createObjectStore('emergency_guidelines', { keyPath: 'hazard_id' });
          // Pre-populate with verified SOPs
          sopsStore.transaction.oncomplete = function () {
            const tx = db.transaction('emergency_guidelines', 'readwrite');
            const store = tx.objectStore('emergency_guidelines');
            EMERGENCY_SOPS.forEach((sop) => store.put(sop));
          };
        }

        // Store 3: Chat History
        if (!db.objectStoreNames.contains('chat_history')) {
          const chatStore = db.createObjectStore('chat_history', { keyPath: 'id', autoIncrement: true });
          chatStore.createIndex('timestamp', 'timestamp', { unique: false });
        }
      };

      request.onsuccess = function (event) {
        resolve(event.target.result);
      };

      request.onerror = function (event) {
        console.warn('[OfflineStore] IndexedDB failed to open:', event.target.error);
        reject(event.target.error);
      };
    });

    return dbPromise;
  }

  // API Methods
  const WeatherOfflineStore = {
    /**
     * Save weather telemetry payload to IndexedDB
     */
    async saveTelemetry(locationKey, payload, answerText) {
      try {
        const db = await openDB();
        const tx = db.transaction('weather_telemetry', 'readwrite');
        const store = tx.objectStore('weather_telemetry');

        const record = {
          id: (locationKey || 'current').toLowerCase().trim(),
          location: locationKey || 'Current Location',
          timestamp: new Date().toISOString(),
          telemetry: payload,
          answer: answerText
        };

        store.put(record);
        // Also save as 'latest' for quick offline default fallback
        store.put({ ...record, id: '__latest__' });
      } catch (err) {
        console.warn('[OfflineStore] saveTelemetry error:', err);
      }
    },

    /**
     * Retrieve latest cached telemetry
     */
    async getLatestTelemetry() {
      try {
        const db = await openDB();
        return new Promise((resolve) => {
          const tx = db.transaction('weather_telemetry', 'readonly');
          const store = tx.objectStore('weather_telemetry');
          const req = store.get('__latest__');
          req.onsuccess = () => resolve(req.result || null);
          req.onerror = () => resolve(null);
        });
      } catch (err) {
        return null;
      }
    },

    /**
     * Look up emergency guideline SOP matching a user query
     */
    async findEmergencyGuideline(query) {
      try {
        const db = await openDB();
        return new Promise((resolve) => {
          const tx = db.transaction('emergency_guidelines', 'readonly');
          const store = tx.objectStore('emergency_guidelines');
          const req = store.getAll();

          req.onsuccess = () => {
            const allSOPs = req.result || EMERGENCY_SOPS;
            const q = query.toLowerCase();

            for (const sop of allSOPs) {
              if (sop.keywords.some((kw) => q.includes(kw))) {
                return resolve(sop);
              }
            }
            resolve(null);
          };
          req.onerror = () => resolve(null);
        });
      } catch (err) {
        return null;
      }
    },

    /**
     * Get all pre-verified emergency guidelines
     */
    async getAllEmergencyGuidelines() {
      try {
        const db = await openDB();
        return new Promise((resolve) => {
          const tx = db.transaction('emergency_guidelines', 'readonly');
          const store = tx.objectStore('emergency_guidelines');
          const req = store.getAll();
          req.onsuccess = () => resolve(req.result || EMERGENCY_SOPS);
          req.onerror = () => resolve(EMERGENCY_SOPS);
        });
      } catch (err) {
        return EMERGENCY_SOPS;
      }
    },

    /**
     * Save message to edge conversation history
     */
    async saveMessage(role, text, cardData = null) {
      try {
        const db = await openDB();
        const tx = db.transaction('chat_history', 'readwrite');
        const store = tx.objectStore('chat_history');
        store.add({
          role: role,
          text: text,
          card: cardData,
          timestamp: new Date().toISOString()
        });
      } catch (err) {
        // non-blocking
      }
    }
  };

  // Expose globally on window
  window.WeatherOfflineStore = WeatherOfflineStore;

  // Initialize DB immediately on load
  openDB().catch(() => {});
})();

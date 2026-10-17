export const karolBaghBurglaryScene = {
  metadata: {
    scene_id: "case_002_karol_bagh_burglary",
    case_reference: "FIR/2024/DL/PSKB/0534",
    location_name: "Flat 302, Rishi Apartments, Ajmal Khan Road, Karol Bagh, New Delhi",
    scene_type: "indoor_crime_scene",
    coordinate_system: "local_cartesian",
    units: "meters",
    date_of_incident: "2024-11-20",
    time_of_incident: "14:20 - 14:52 IST",
  },

  room: {
    length_m: 10.0, // X dimension (Living room + Bedroom span)
    width_m: 7.0,   // Z dimension
    height_m: 2.8,  // Ceiling height
    floor_color: "#18202c",
    wall_color: "#1e293b",
    door_z: 2.5,    // Match entrance door frame at z = 2.5
  },

  roads: [],
  vehicles: [],

  people: [
    {
      id: "accused_ravi",
      name: "Ravi Shankar Yadav (Accused / Former Guard)",
      role: "suspect",
      position: { x: -4.3, y: 0, z: 2.5 },
      rotation: { x: 0, y: 0, z: 0 },
      waypoints: [
        // ========================================================
        // ACT 1: APPROACH & PADLOCK BREACH (t=0.0s - 2.0s)
        // ========================================================
        { time: 0.0, position: { x: -4.8, y: 0, z: 2.5 }, rotation: { x: 0, y: 90, z: 0 } },
        { time: 0.8, position: { x: -4.3, y: 0, z: 2.5 }, rotation: { x: 0, y: 90, z: 0 } },
        // Bends over door latch, uses iron rod
        { time: 1.8, position: { x: -4.2, y: 0, z: 2.5 }, rotation: { x: 0, y: 90, z: 0 } },

        // ========================================================
        // ACT 2: ENTER FLAT & CIRCUMNAVIGATE COFFEE TABLE (t=2.0s - 4.5s)
        // Table is at x = -1.5, z = 0.6. Suspect walks along the open corridor path (z = 1.8)
        // ========================================================
        { time: 2.4, position: { x: -3.5, y: 0, z: 2.3 }, rotation: { x: 0, y: 110, z: 0 } },
        { time: 3.2, position: { x: -2.6, y: 0, z: 1.6 }, rotation: { x: 0, y: 120, z: 0 } },
        // Inspects sofa / table region from open side without colliding
        { time: 3.8, position: { x: -1.5, y: 0, z: 1.4 }, rotation: { x: 0, y: 90, z: 0 } },
        { time: 4.5, position: { x: -0.4, y: 0, z: 1.0 }, rotation: { x: 0, y: 70, z: 0 } },

        // ========================================================
        // ACT 3: WALK THROUGH INTERIOR DOORWAY TO ALMIRAH (t=4.5s - 6.0s)
        // Doorway opening is at x = 0.8, z = 0.2. Almirah is at x = 3.2, z = -2.9.
        // ========================================================
        // Passes cleanly through open doorway
        { time: 5.0, position: { x: 0.8, y: 0, z: 0.2 }, rotation: { x: 0, y: 55, z: 0 } },
        // Walks across master bedroom floor towards north wall almirah
        { time: 5.5, position: { x: 2.0, y: 0, z: -1.2 }, rotation: { x: 0, y: 35, z: 0 } },
        // Stands directly in front of the steel almirah
        { time: 6.0, position: { x: 3.2, y: 0, z: -2.2 }, rotation: { x: 0, y: 0, z: 0 } },

        // ========================================================
        // ACT 4: THE HEIST (t=6.0s - 7.0s)
        // Crowbars Godrej almirah door, grabs gold jewellery and cash box
        // ========================================================
        { time: 6.5, position: { x: 3.2, y: 0, z: -2.2 }, rotation: { x: 0, y: 0, z: 0 } },
        { time: 7.0, position: { x: 3.1, y: 0, z: -2.1 }, rotation: { x: 0, y: 140, z: 0 } },

        // ========================================================
        // ACT 5: REALISTIC 3-SECOND ESCAPE TRANSIT (t=7.0s - 10.0s)
        // Turns around, drops iron rod on bedroom floor, walks through
        // partition door, navigates living room aisle, and exits into corridor
        // ========================================================
        // Step away from almirah into bedroom floor
        { time: 7.6, position: { x: 2.2, y: 0, z: -1.0 }, rotation: { x: 0, y: 215, z: 0 } },
        // Walks cleanly back through bedroom interior doorway (x = 0.8, z = 0.2)
        { time: 8.3, position: { x: 0.8, y: 0, z: 0.2 }, rotation: { x: 0, y: 235, z: 0 } },
        // Strides past living room table corridor (x = -1.5, z = 1.4)
        { time: 9.0, position: { x: -1.6, y: 0, z: 1.4 }, rotation: { x: 0, y: 260, z: 0 } },
        // Approaches and crosses through main entrance doorway (x = -4.2, z = 2.5)
        { time: 9.6, position: { x: -3.8, y: 0, z: 2.4 }, rotation: { x: 0, y: 270, z: 0 } },
        // Fully outside into 3rd floor hallway corridor
        { time: 10.0, position: { x: -5.0, y: 0, z: 2.5 }, rotation: { x: 0, y: 270, z: 0 } },
      ],
    },
  ],

  evidence: [
    {
      id: "ev_padlock",
      type: "broken_padlock",
      description: "EVD-0534-001: Broken Godrej 7-lever brass padlock with sheared shackle",
      position: { x: -4.1, y: 0.02, z: 2.3 },
    },
    {
      id: "ev_iron_rod",
      type: "iron_rod_crowbar",
      description: "EVD-0534-002: 20-inch forged iron rod used to pry open padlock and almirah",
      position: { x: 2.9, y: 0.02, z: -1.6 },
    },
    {
      id: "ev_fingerprints",
      type: "fingerprint_lift",
      description: "EVD-0534-003: 12 latent fingerprint lift cards matching accused right index & thumb",
      position: { x: 2.6, y: 1.1, z: -2.45 },
    },
    {
      id: "ev_footprint",
      type: "footprint_cast",
      description: "EVD-0534-004: Size 9 Chevron tread shoe sole impression lifted from balcony floor",
      position: { x: 4.2, y: 0.01, z: 0.8 },
    },
    {
      id: "ev_cloth_fibres",
      type: "cloth_fibres",
      description: "EVD-0534-015: 3 black rexine fabric fibres snagged on sharp edge of opened almirah",
      position: { x: 2.2, y: 0.85, z: -2.38 },
    },
  ],

  environment_objects: [
    // 1. Flat 302 Main Entrance Doorway (Breached wooden frame)
    {
      id: "env_main_door",
      type: "door_frame",
      description: "Flat 302 wooden entry doorway with broken latch splinters",
      position: { x: -4.2, y: 0, z: 2.5 },
      rotation: { x: 0, y: 90, z: 0 },
    },

    // 2. Living Room 3-Seater Sofa (Ransacked)
    {
      id: "env_sofa",
      type: "sofa_3seater",
      description: "Living room sofa with overturned cushions",
      position: { x: -1.5, y: 0, z: 1.8 },
      rotation: { x: 0, y: 180, z: 0 },
    },

    // 3. Coffee Table
    {
      id: "env_coffee_table",
      type: "coffee_table",
      description: "Wooden coffee table with disturbed paper drawers",
      position: { x: -1.5, y: 0, z: 0.6 },
      rotation: { x: 0, y: 0, z: 0 },
    },

    // 4. Master Bedroom Partition Wall (Dividing living room from bedroom)
    {
      id: "env_bedroom_wall_north",
      type: "wall_partition",
      description: "Drywall dividing living room from master bedroom (North segment)",
      position: { x: 0.8, y: 0, z: -2.0 },
      dimensions: { x: 0.15, y: 2.8, z: 3.0 },
    },
    {
      id: "env_bedroom_wall_south",
      type: "wall_partition",
      description: "Drywall dividing living room from master bedroom (South segment)",
      position: { x: 0.8, y: 0, z: 2.2 },
      dimensions: { x: 0.15, y: 2.8, z: 2.6 },
    },
    {
      id: "env_bedroom_door",
      type: "door_frame",
      description: "Master bedroom interior doorway opening",
      position: { x: 0.8, y: 0, z: 0.2 },
      rotation: { x: 0, y: 90, z: 0 },
    },

    // 5. Godrej 2-Door Steel Almirah (Burgled & Crowbarred)
    {
      id: "env_godrej_almirah",
      type: "steel_almirah",
      description: "Godrej 2-door steel wardrobe against North wall with levered locker",
      position: { x: 3.2, y: 0, z: -2.9 },
      rotation: { x: 0, y: 0, z: 0 },
    },

    // 6. Master Bedroom Double Bed
    {
      id: "env_master_bed",
      type: "double_bed",
      description: "Double bed opposite almirah with rummaged mattress and bedding",
      position: { x: 3.2, y: 0, z: 1.2 },
      rotation: { x: 0, y: 180, z: 0 },
    },

    // 7. Ceiling Light Fixture (Living Room)
    {
      id: "env_lamp_living",
      type: "ceiling_lamp",
      description: "Overhead living room light luminaire",
      position: { x: -2.0, y: 0, z: 0.0 },
      rotation: { x: 0, y: 0, z: 0 },
    },

    // 8. Ceiling Light Fixture (Master Bedroom)
    {
      id: "env_lamp_bedroom",
      type: "ceiling_lamp",
      description: "Overhead bedroom light luminaire",
      position: { x: 3.0, y: 0, z: -0.5 },
      rotation: { x: 0, y: 0, z: 0 },
    },
  ],

  timeline: [
    {
      id: "event_entry",
      event_type: "padlock_breach",
      description: "Accused forces Godrej 7-lever brass padlock hasp using 20-inch iron rod.",
      timestamp: "14:30:00",
      confidence: 0.96,
    },
    {
      id: "event_witness",
      event_type: "witness_encounter",
      description: "Neighbor Sunita Kapoor observes accused at door; accused claims to be plumber.",
      timestamp: "14:30:30",
      confidence: 0.92,
    },
    {
      id: "event_ransack",
      event_type: "living_room_ransack",
      description: "Accused enters Flat 302, rummages credenza and drawers looking for locker keys.",
      timestamp: "14:32:00",
      confidence: 0.88,
    },
    {
      id: "event_almirah",
      event_type: "almirah_forced_open",
      description: "Accused crowbars the steel Godrej almirah door and interior cash locker.",
      timestamp: "14:38:00",
      confidence: 0.98,
    },
    {
      id: "event_exit",
      event_type: "accused_escape",
      description: "Stuffs ₹14.75L jewellery and ₹85K cash into black rexine bag and flees.",
      timestamp: "14:48:00",
      confidence: 0.94,
    },
  ],

  conflicts: [
    {
      id: "conflict_entry_tool",
      field: "breach_instrument",
      hypotheses: [
        { id: "hyp_fsl", value: "20-inch iron rod (Striation match)", source: "FSL Physics Report", confidence: 0.98 },
        { id: "hyp_wit", value: "Heavy wrench / hammer", source: "Neighbor statement", confidence: 0.60 },
      ],
    },
  ],
};


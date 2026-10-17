export const delhiAccidentScene = {
  metadata: {
    scene_id: "case_001_delhi_tpoint",
    location_name: "Shankar Road T-Point, New Delhi",
    scene_type: "road_traffic_collision",
    coordinate_system: "local_cartesian",
    units: "meters",
  },

  roads: [
    {
      id: "road_1",
      name: "Shankar Road",
      width_m: 12.5,
      heading_deg: 0,
      position: { x: 0, y: 0, z: 0 },
    },
    {
      id: "road_2",
      name: "Rajinder Nagar Main Road",
      width_m: 10,
      heading_deg: 90,
      position: { x: 0, y: 0.01, z: 0 },
    },
  ],

  vehicles: [
    {
      id: "vehicle_1",
      registration: "DL2SBP1234",
      make: "Bajaj Auto Ltd.",
      model: "Pulsar 220F",
      type: "two_wheeler",
      asset_path: "/assets/vehicles/bajaj_pulsar_150.glb",
      start_position: { x: -12, y: 0, z: 0 },
      impact_position: { x: -1.35, y: 0, z: 0 },
      final_position: { x: 0.8, y: 0, z: 1.2 },
      rotation: { x: 0, y: 180, z: 0 },
    },
    {
      id: "vehicle_2",
      registration: "DL5SCT5678",
      make: "Honda Motorcycle & Scooter India",
      model: "Activa 6G",
      type: "two_wheeler",
      asset_path: "/assets/vehicles/honda_activa_6g.glb",
      start_position: { x: 0, y: 0, z: -10 },
      impact_position: { x: 0, y: 0, z: 0 },
      final_position: { x: 1.8, y: 0, z: -1.6 },
      rotation: { x: 0, y: 90, z: 0 },
    },
  ],

  people: [
    {
      id: "witness_1",
      name: "Ramesh (Tea Stall)",
      role: "witness",
      position: { x: -6.0, y: 0, z: 6.5 },
      rotation: { x: 0, y: 135, z: 0 },
    },
  ],

  evidence: [
    {
      id: "evidence_skid_1",
      type: "skid_mark",
      description: "4.2m locked-wheel emergency braking skid mark",
      length_m: 4.2,
      position: { x: -2.0, y: 0.03, z: 0 },
      related_vehicle_ids: ["vehicle_1"],
    },
  ],

  environment_objects: [
    {
      id: "env_sidewalk_north",
      type: "sidewalk",
      description: "Raised concrete pedestrian sidewalk along North Shankar Road",
      position: { x: 0, y: 0, z: -7.45 },
      dimensions: { x: 42, y: 0.16, z: 2.4 },
    },
    {
      id: "env_sidewalk_south",
      type: "sidewalk",
      description: "Raised concrete pedestrian sidewalk along South Shankar Road",
      position: { x: 0, y: 0, z: 7.45 },
      dimensions: { x: 42, y: 0.16, z: 2.4 },
    },
    {
      id: "env_building_nw",
      type: "building",
      description: "3-story commercial shopfront block at North-West intersection corner",
      position: { x: -14.0, y: 0, z: -14.5 },
      dimensions: { x: 14, y: 9, z: 12 },
    },
    {
      id: "env_building_ne",
      type: "building",
      description: "4-story commercial building block at North-East intersection corner",
      position: { x: 14.0, y: 0, z: -14.5 },
      dimensions: { x: 14, y: 11, z: 12 },
    },
    {
      id: "env_building_sw",
      type: "building",
      description: "2-story roadside commercial property at South-West corner",
      position: { x: -14.0, y: 0, z: 15.0 },
      dimensions: { x: 14, y: 7.5, z: 12 },
    },
    {
      id: "env_tea_stall",
      type: "tea_stall",
      description: "Ramesh's roadside tea stall vendor booth with awning",
      position: { x: -6.0, y: 0, z: 6.5 },
      rotation: { x: 0, y: 135, z: 0 },
    },
    {
      id: "env_street_lamp_1",
      type: "street_light",
      description: "High-mast sodium streetlight pole illuminating intersection",
      position: { x: 3.5, y: 0, z: -6.8 },
      rotation: { x: 0, y: 180, z: 0 },
    },
    {
      id: "env_street_lamp_2",
      type: "street_light",
      description: "Streetlight pole along West approach",
      position: { x: -9.5, y: 0, z: -6.8 },
      rotation: { x: 0, y: 180, z: 0 },
    },
    {
      id: "env_glass_debris",
      type: "debris_glass",
      description: "Shattered headlight glass debris field at primary impact point",
      position: { x: -0.7, y: 0.015, z: 0 },
    },
  ],

  timeline: [
    {
      id: "approach_1",
      event_type: "approach",
      description: "Vehicle approach detected on CCTV-4 heading Eastbound.",
      timestamp: "18:20:02",
      confidence: 0.9,
    },
    {
      id: "brake_1",
      event_type: "braking",
      description: "Pulsar initiates emergency braking; tire skid trace begins.",
      timestamp: "18:20:05",
      confidence: 0.85,
    },
    {
      id: "impact_1",
      event_type: "collision",
      description: "Lateral perpendicular collision at T-Point intersection center.",
      timestamp: "18:20:07.800",
      confidence: 0.95,
      status: "conflict",
    },
    {
      id: "final_position",
      event_type: "final_rest",
      description: "Vehicles & riders come to rest per Spot Panchanama survey.",
      timestamp: "18:20:10",
      confidence: 0.9,
    },
  ],

  conflicts: [
    {
      id: "conflict_speed_v1",
      field: "vehicle_1_speed",
      hypotheses: [
        { id: "hyp_1", value: 60.0, source: "CCTV-4", confidence: 0.9 },
        { id: "hyp_2", value: 52.4, source: "CCTV-2", confidence: 0.9 },
      ],
    },
  ],
};

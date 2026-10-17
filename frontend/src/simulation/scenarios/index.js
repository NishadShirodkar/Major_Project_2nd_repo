import { delhiAccidentScene } from "./delhiAccidentScene.js";
import { indoorShootingScene } from "./indoorShootingScene.js";
import { karolBaghBurglaryScene } from "./karolBaghBurglaryScene.js";

export const SCENARIO_DELHI_TPOINT = {
  id: "case_001_delhi_tpoint",
  shortId: "case_001",
  name: "Case 001: Delhi T-Point Collision",
  category: "Traffic Collision",
  data: delhiAccidentScene,
};

export const SCENARIO_KAROL_BAGH_BURGLARY = {
  id: "case_002_karol_bagh_burglary",
  shortId: "case_002",
  name: "Case 002: Karol Bagh Flat 302 Burglary",
  category: "House Burglary & Theft",
  data: karolBaghBurglaryScene,
};

export const SCENARIO_INDOOR_SHOOTING = {
  id: "case_003_indoor_shooting",
  shortId: "case_003",
  name: "Case 003: Indoor Shooting / Ballistics",
  category: "Indoor Ballistics / Crime Scene",
  data: indoorShootingScene,
};

export const SCENARIO_LIST = [
  SCENARIO_DELHI_TPOINT,
  SCENARIO_KAROL_BAGH_BURGLARY,
  SCENARIO_INDOOR_SHOOTING,
];

export const SCENARIO_REGISTRY = {
  // Canonical scenario IDs
  case_001_delhi_tpoint: SCENARIO_DELHI_TPOINT,
  case_002_karol_bagh_burglary: SCENARIO_KAROL_BAGH_BURGLARY,
  case_003_indoor_shooting: SCENARIO_INDOOR_SHOOTING,

  // Short ID aliases
  case_001: SCENARIO_DELHI_TPOINT,
  case_002: SCENARIO_KAROL_BAGH_BURGLARY,
  case_003: SCENARIO_INDOOR_SHOOTING,
};

/**
 * Robust scenario resolver for any case identifier
 */
export function getScenario(caseId) {
  if (!caseId) return SCENARIO_DELHI_TPOINT;
  const key = String(caseId).toLowerCase().trim();
  if (SCENARIO_REGISTRY[key]) return SCENARIO_REGISTRY[key];

  if (key.includes("delhi") || key.includes("tpoint") || key.includes("001")) {
    return SCENARIO_DELHI_TPOINT;
  }
  if (key.includes("burglary") || key.includes("karol") || key.includes("002")) {
    return SCENARIO_KAROL_BAGH_BURGLARY;
  }
  if (key.includes("shooting") || key.includes("rohini") || key.includes("indoor") || key.includes("003")) {
    return SCENARIO_INDOOR_SHOOTING;
  }

  return SCENARIO_DELHI_TPOINT;
}

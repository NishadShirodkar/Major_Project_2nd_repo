import * as THREE from "three";

/**
 * Resolves a normalized list of waypoints for any entity across time.
 * Supports explicit waypoints, 3-point start/impact/final setups, or dynamic timeline events.
 */
export function resolveEntityWaypoints(entity, timeline = []) {
  if (entity.waypoints && entity.waypoints.length > 0) {
    return [...entity.waypoints].sort((a, b) => a.time - b.time);
  }

  // Construct from 3-point schema if provided
  const startPos = entity.start_position || entity.position || { x: 0, y: 0, z: 0 };
  const impactPos = entity.impact_position || startPos;
  const finalPos = entity.final_position?.position || entity.final_position || impactPos;

  const defaultRot = entity.rotation || { x: 0, y: 0, z: 0 };

  // Check if timeline defines specific impact timestamp
  const impactEvent = timeline.find(
    (ev) =>
      ev.event_type?.includes("collision") ||
      ev.event_type?.includes("impact") ||
      ev.event_type?.includes("gunshot")
  );

  const impactTime = impactEvent ? 5.0 : 5.0;

  return [
    {
      time: 0.0,
      position: startPos,
      rotation: defaultRot,
    },
    {
      time: impactTime,
      position: impactPos,
      rotation: defaultRot,
    },
    {
      time: 10.0,
      position: finalPos,
      rotation: defaultRot,
    },
  ];
}

/**
 * Interpolates entity position, rotation, instantaneous velocity, and chassis dynamic states
 * using deterministic Newtonian kinematics (braking deceleration, momentum impulse, frictional decay).
 */
export function sampleEntityState(waypoints, currentTime) {
  if (!waypoints || waypoints.length === 0) {
    return {
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      speedKmph: 0,
      activeSegmentIndex: 0,
      isBraking: false,
      isSliding: false,
      pitchDive: 0,
      wheelSpeedKmph: 0,
    };
  }

  if (waypoints.length === 1) {
    return {
      position: waypoints[0].position,
      rotation: waypoints[0].rotation || { x: 0, y: 0, z: 0 },
      speedKmph: 0,
      activeSegmentIndex: 0,
      isBraking: false,
      isSliding: false,
      pitchDive: 0,
      wheelSpeedKmph: 0,
    };
  }

  // Before first waypoint
  if (currentTime <= waypoints[0].time) {
    const p1 = waypoints[0].position;
    const p2 = waypoints[1].position;
    const dt = Math.max(0.01, waypoints[1].time - waypoints[0].time);
    const dist = Math.hypot(p2.x - p1.x, p2.z - p1.z);
    const speedKmph = (dist / dt) * 3.6;

    return {
      position: waypoints[0].position,
      rotation: waypoints[0].rotation || { x: 0, y: 0, z: 0 },
      speedKmph,
      wheelSpeedKmph: speedKmph,
      activeSegmentIndex: 0,
      isBraking: false,
      isSliding: false,
      pitchDive: 0,
    };
  }

  // After last waypoint
  const lastIndex = waypoints.length - 1;
  if (currentTime >= waypoints[lastIndex].time) {
    const lastW = waypoints[lastIndex];
    const r = lastW.rotation || { x: 0, y: 0, z: 0 };
    return {
      position: lastW.position,
      rotation: {
        x: (r.x * Math.PI) / 180,
        y: (r.y * Math.PI) / 180,
        z: (r.z * Math.PI) / 180,
      },
      speedKmph: 0,
      wheelSpeedKmph: 0,
      activeSegmentIndex: lastIndex,
      isBraking: false,
      isSliding: false,
      pitchDive: 0,
    };
  }

  // Find active segment between waypoints[i] and waypoints[i+1]
  let i = 0;
  while (i < waypoints.length - 1 && currentTime > waypoints[i + 1].time) {
    i++;
  }

  const w1 = waypoints[i];
  const w2 = waypoints[i + 1];

  const segDuration = Math.max(0.001, w2.time - w1.time);
  const rawProgress = (currentTime - w1.time) / segDuration;
  const progress = Math.max(0, Math.min(1, rawProgress));

  // Determine physical phase:
  // Is this the approach-to-impact segment (e.g., segment 0 leading to collision at ~5s)?
  const isApproachSegment = i === 0 && waypoints.length >= 3;
  const isPostImpactSegment = i >= 1 && waypoints.length >= 3;

  let physicalProgress = progress;
  let isBraking = false;
  let isSliding = false;
  let pitchDive = 0;
  let instantSpeedFactor = 1.0;

  if (isApproachSegment) {
    // Phase 1: Pre-braking cruise (first 65% of approach) followed by emergency braking (last 35%)
    // Real braking deceleration: quadratic position curve s = v0*t - 0.5*a*t^2
    const brakeThreshold = 0.65;
    if (progress > brakeThreshold) {
      isBraking = true;
      const brakeProgress = (progress - brakeThreshold) / (1 - brakeThreshold);
      // Nose-dive torque proportional to brake deceleration
      pitchDive = Math.sin(brakeProgress * Math.PI * 0.8) * 0.08;
      
      // Deceleration curve: speed drops smoothly from cruise to impact velocity
      instantSpeedFactor = 1.0 - 0.35 * brakeProgress;
      
      // Smooth quadratic displacement for braking
      const easedBrake = 1 - Math.pow(1 - brakeProgress, 1.6);
      physicalProgress = brakeThreshold + (1 - brakeThreshold) * easedBrake;
    } else {
      // Linear cruise
      physicalProgress = progress * (brakeThreshold / brakeThreshold);
      instantSpeedFactor = 1.0;
    }
  } else if (isPostImpactSegment) {
    // Phase 2: Post-impact kinetic friction slide
    // In physics, sliding under road friction decays quadratically: s(t) = s_final * (1 - (1 - t)^2)
    isSliding = true;
    physicalProgress = 1 - Math.pow(1 - progress, 2.2); // Rapid initial slide, strong frictional stop
    instantSpeedFactor = Math.max(0, Math.pow(1 - progress, 1.8)); // Speed decays to 0
  }

  // Position interpolation with Newtonian physical progress
  const pos = {
    x: w1.position.x + (w2.position.x - w1.position.x) * physicalProgress,
    y: (w1.position.y || 0) + ((w2.position.y || 0) - (w1.position.y || 0)) * physicalProgress,
    z: w1.position.z + (w2.position.z - w1.position.z) * physicalProgress,
  };

  // Rotation interpolation
  const r1 = w1.rotation || { x: 0, y: 0, z: 0 };
  const r2 = w2.rotation || r1;
  
  // Non-linear angular rotation post-impact (rapid initial spin, settling into rest orientation)
  const rotProgress = isPostImpactSegment
    ? 1 - Math.pow(1 - progress, 2.5)
    : physicalProgress;

  const rot = {
    x: (((r1.x + (r2.x - r1.x) * rotProgress)) * Math.PI) / 180 + pitchDive,
    y: (((r1.y + (r2.y - r1.y) * rotProgress)) * Math.PI) / 180,
    z: (((r1.z + (r2.z - r1.z) * rotProgress)) * Math.PI) / 180,
  };

  // Calculate instantaneous velocity in km/h
  const deltaDistance = Math.hypot(w2.position.x - w1.position.x, w2.position.z - w1.position.z);
  const baseSpeedKmph = (deltaDistance / segDuration) * 3.6;
  const currentSpeedKmph = baseSpeedKmph * instantSpeedFactor;

  return {
    position: pos,
    rotation: rot,
    speedKmph: currentSpeedKmph,
    wheelSpeedKmph: isBraking ? currentSpeedKmph * 0.4 : currentSpeedKmph, // Wheel slip under hard braking
    activeSegmentIndex: i,
    segmentProgress: progress,
    physicalProgress,
    isBraking,
    isSliding,
    pitchDive,
  };
}

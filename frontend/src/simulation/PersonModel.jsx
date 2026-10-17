import React, { useMemo } from "react";
import * as THREE from "three";
import { resolveEntityWaypoints, sampleEntityState } from "./kinematics";

/**
 * High-Detail Forensic Character Model.
 * Formed with realistic anatomical proportions, layered clothing, shoes, tactical vest/shirt,
 * detailed head, facial profile, hair, and multi-joint articulated collapse dynamics.
 */
export default function PersonModel({
  person,
  timeline = [],
  currentTime = 0,
  isSelected = false,
  onSelect,
}) {
  const waypoints = useMemo(() => resolveEntityWaypoints(person, timeline), [person, timeline]);
  const sampledState = useMemo(
    () => sampleEntityState(waypoints, currentTime),
    [waypoints, currentTime]
  );
  const { position, rotation } = sampledState;

  const role = (person.role || "person").toLowerCase();
  const isVictim = role.includes("victim") || role.includes("casualty");
  const isSuspect = role.includes("suspect") || role.includes("accused") || role.includes("shooter");
  const roleColor = isVictim ? "#ff0055" : isSuspect ? "#ffb700" : "#00f0ff";

  // Realistic Character PBR Materials
  const skinMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#c68a64", // Warm South-Asian skin tone
        roughness: 0.72,
        metalness: 0.05,
      }),
    []
  );

  const hairMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#1a1614", // Dark hair
        roughness: 0.9,
        metalness: 0.1,
      }),
    []
  );

  const shirtMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: isVictim ? "#2c3e50" : isSuspect ? "#1c1917" : "#0f766e",
        roughness: 0.75,
        metalness: 0.1,
      }),
    [isVictim, isSuspect]
  );

  const pantsMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#1e293b", // Dark denim/chinos
        roughness: 0.8,
        metalness: 0.05,
      }),
    []
  );

  const shoeMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#0f172a", // Dark leather/boots
        roughness: 0.5,
        metalness: 0.3,
      }),
    []
  );

  const accentMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: roleColor,
      }),
    [roleColor]
  );

  // Biomechanical Articulation Kinematics
  const isFallen = isVictim && currentTime >= 5.0;
  const dtFall = isFallen ? currentTime - 5.0 : 0.0;
  const fallProgress = isFallen ? Math.min(1.0, Math.pow(dtFall / 0.85, 1.4)) : 0.0;

  // 1. Natural Procedural Locomotion Gait Cycle
  // Calculate movement speed and walking phase
  const speed = (sampledState.speedKmph || 0) / 3.6; // m/s
  const isMoving = speed > 0.1 && !isFallen;
  const walkPhase = isMoving ? currentTime * Math.max(4.0, speed * 3.8) : 0;
  const strideAmp = isMoving ? Math.min(0.65, 0.25 + speed * 0.25) : 0;

  // Normal standing pelvis vs walking bounce
  const walkBounce = isMoving ? Math.abs(Math.sin(walkPhase)) * 0.04 : 0;
  const pelvisY = isFallen
    ? (1 - fallProgress) * 0.85 + 0.12
    : 0.85 - walkBounce;

  // 2. Suspect Action Posing (Burglary Actions)
  // At door (t=1.0 - 2.2): Bending over lock
  const isBendingAtDoor = isSuspect && currentTime >= 1.0 && currentTime <= 2.2;
  // At almirah (t=6.0 - 7.2): Reaching out into cabinet
  const isPryingAlmirah = isSuspect && currentTime >= 6.0 && currentTime <= 7.2;

  // 3. Torso Pitch & Posture
  let torsoPitch = 0;
  let torsoRoll = 0;
  let torsoYaw = 0;

  if (isFallen) {
    torsoPitch = fallProgress * (Math.PI / 2.15); // ~84 deg backward tilt
    torsoRoll = fallProgress * 0.22;
    torsoYaw = fallProgress * 0.15;
  } else if (isBendingAtDoor) {
    torsoPitch = 0.45; // Leaning forward into door lock
  } else if (isPryingAlmirah) {
    torsoPitch = 0.25; // Leaning into wardrobe
  } else if (isMoving) {
    torsoPitch = 0.08; // Slight forward lean when walking
  }

  // 4. Head Angles
  const whiplashShock = dtFall > 0 && dtFall < 0.4 ? Math.sin((dtFall / 0.4) * Math.PI) * 0.4 : 0;
  const headPitch = isFallen
    ? torsoPitch * 0.65 - whiplashShock
    : isBendingAtDoor
    ? 0.35
    : 0;

  // 5. Articulated Leg Walking (Opposing sinusoids)
  let leftThighPitch = 0;
  let rightThighPitch = 0;
  let leftShinPitch = 0;
  let rightShinPitch = 0;

  if (isFallen) {
    leftThighPitch = fallProgress * 0.55;
    rightThighPitch = fallProgress * 0.55 * 0.9;
    leftShinPitch = -fallProgress * 1.1;
    rightShinPitch = -fallProgress * 1.1 * 0.85;
  } else if (isMoving) {
    leftThighPitch = Math.sin(walkPhase) * strideAmp;
    rightThighPitch = -Math.sin(walkPhase) * strideAmp;
    leftShinPitch = Math.max(0, -Math.sin(walkPhase)) * strideAmp * 1.2;
    rightShinPitch = Math.max(0, Math.sin(walkPhase)) * strideAmp * 1.2;
  }

  // 6. Arm Swing in Opposition to Legs
  let leftArmPitch = 0;
  let rightArmPitch = 0;
  let leftArmRoll = 0;
  let rightArmRoll = 0;

  if (isFallen) {
    const armFlail = Math.sin(Math.min(1.0, dtFall / 0.5) * Math.PI) * 0.35;
    leftArmRoll = fallProgress * 0.7 + armFlail;
    rightArmRoll = -fallProgress * 0.65 - armFlail;
  } else if (isBendingAtDoor || isPryingAlmirah) {
    // Both arms raised forward holding iron tool
    leftArmPitch = -0.75;
    rightArmPitch = -0.75;
    leftArmRoll = 0.2;
    rightArmRoll = -0.2;
  } else if (isMoving) {
    // Natural counter-balancing arm swing
    leftArmPitch = -Math.sin(walkPhase) * strideAmp * 0.85;
    rightArmPitch = Math.sin(walkPhase) * strideAmp * 0.85;
  }

  return (
    <group
      position={[position.x, Math.max(0.04, position.y), position.z]}
      rotation={[rotation.x, rotation.y, rotation.z]}
      onClick={(e) => {
        e.stopPropagation();
        if (onSelect) onSelect(person.id);
      }}
    >
      {/* ============================================================ */}
      {/* ARTICULATED BIOMECHANICAL CHARACTER HIERARCHY                */}
      {/* ============================================================ */}

      {/* 1. PELVIS / WAIST ROOT NODE */}
      <group position={[0, pelvisY, 0]}>
        {/* Belt & Waistband */}
        <mesh material={pantsMaterial}>
          <boxGeometry args={[0.28, 0.14, 0.2]} />
        </mesh>
        <mesh position={[0, 0.04, 0.105]}>
          <boxGeometry args={[0.08, 0.04, 0.01]} />
          <meshStandardMaterial color="#d4d4d8" metalness={0.8} roughness={0.3} />
        </mesh>

        {/* 2. TORSO & CHEST (Child of Pelvis) */}
        <group position={[0, 0.08, 0]} rotation={[torsoPitch, torsoYaw, torsoRoll]}>
          {/* Main Shirt / Jacket Chest */}
          <mesh position={[0, 0.18, 0]} material={shirtMaterial}>
            <boxGeometry args={[0.32, 0.36, 0.22]} />
          </mesh>
          {/* Collar & Neck Base */}
          <mesh position={[0, 0.38, 0]} material={skinMaterial}>
            <cylinderGeometry args={[0.055, 0.065, 0.1, 12]} />
          </mesh>

          {/* Forensic Tactical Identification Role Patch */}
          <mesh position={[0, 0.25, 0.115]} material={accentMaterial}>
            <planeGeometry args={[0.14, 0.045]} />
          </mesh>

          {/* Forensic Ballistic Impact Wound Marker (if victim post-impact) */}
          {isVictim && currentTime >= 5.0 && (
            <group position={[0.06, 0.26, 0.116]}>
              <mesh>
                <circleGeometry args={[0.024, 16]} />
                <meshBasicMaterial color="#991b1b" side={THREE.DoubleSide} />
              </mesh>
              <mesh position={[0, 0, 0.002]}>
                <ringGeometry args={[0.024, 0.048, 16]} />
                <meshBasicMaterial color="#ef4444" transparent opacity={0.65} side={THREE.DoubleSide} />
              </mesh>
            </group>
          )}

          {/* 3. DETAILED HEAD & FACE (Child of Torso) */}
          <group position={[0, 0.44, 0]} rotation={[headPitch, 0, 0]}>
            {/* Cranium / Face */}
            <mesh position={[0, 0.09, 0]} material={skinMaterial}>
              <sphereGeometry args={[0.115, 20, 20]} />
            </mesh>
            {/* Hair Cap */}
            <mesh position={[0, 0.13, -0.015]} material={hairMaterial}>
              <sphereGeometry args={[0.118, 16, 16]} />
            </mesh>
            {/* Nose Profile */}
            <mesh position={[0, 0.08, 0.11]} material={skinMaterial}>
              <coneGeometry args={[0.022, 0.045, 8]} />
            </mesh>
            {/* Tactical Eyewear / Eyes */}
            <mesh position={[0, 0.11, 0.095]}>
              <boxGeometry args={[0.12, 0.03, 0.04]} />
              <meshStandardMaterial color="#090d16" roughness={0.2} metalness={0.8} />
            </mesh>
          </group>

          {/* 4. LEFT SHOULDER & ARM */}
          <group position={[-0.2, 0.32, 0]} rotation={[leftArmPitch, 0, leftArmRoll]}>
            {/* Shoulder Sleeve */}
            <mesh position={[0, -0.08, 0]} material={shirtMaterial}>
              <cylinderGeometry args={[0.05, 0.045, 0.18, 10]} />
            </mesh>
            {/* Forearm & Hand */}
            <group position={[0, -0.17, 0]} rotation={[0, 0, 0.15]}>
              <mesh position={[0, -0.08, 0]} material={skinMaterial}>
                <cylinderGeometry args={[0.04, 0.032, 0.18, 10]} />
              </mesh>
              {/* Hand */}
              <mesh position={[0, -0.18, 0]} material={skinMaterial}>
                <sphereGeometry args={[0.035, 10, 10]} />
              </mesh>
            </group>
          </group>

          {/* 5. RIGHT SHOULDER & ARM */}
          <group position={[0.2, 0.32, 0]} rotation={[rightArmPitch, 0, rightArmRoll]}>
            {/* Shoulder Sleeve */}
            <mesh position={[0, -0.08, 0]} material={shirtMaterial}>
              <cylinderGeometry args={[0.05, 0.045, 0.18, 10]} />
            </mesh>
            {/* Forearm & Hand */}
            <group position={[0, -0.17, 0]} rotation={[0, 0, -0.15]}>
              <mesh position={[0, -0.08, 0]} material={skinMaterial}>
                <cylinderGeometry args={[0.04, 0.032, 0.18, 10]} />
              </mesh>
              {/* Hand */}
              <mesh position={[0, -0.18, 0]} material={skinMaterial}>
                <sphereGeometry args={[0.035, 10, 10]} />
              </mesh>
            </group>
          </group>
        </group>

        {/* 6. LEFT LEG (Thigh -> Knee -> Calf -> Boot) */}
        <group position={[-0.09, -0.06, 0]} rotation={[leftThighPitch, 0, 0]}>
          {/* Upper Thigh */}
          <mesh position={[0, -0.16, 0]} material={pantsMaterial}>
            <cylinderGeometry args={[0.055, 0.048, 0.32, 10]} />
          </mesh>
          {/* Knee & Calf */}
          <group position={[0, -0.32, 0]} rotation={[leftShinPitch, 0, 0]}>
            <mesh position={[0, -0.16, 0]} material={pantsMaterial}>
              <cylinderGeometry args={[0.046, 0.04, 0.32, 10]} />
            </mesh>
            {/* Shoe / Boot */}
            <mesh position={[0, -0.32, 0.04]} material={shoeMaterial}>
              <boxGeometry args={[0.085, 0.07, 0.17]} />
            </mesh>
          </group>
        </group>

        {/* 7. RIGHT LEG (Thigh -> Knee -> Calf -> Boot) */}
        <group position={[0.09, -0.06, 0]} rotation={[rightThighPitch, 0, 0]}>
          {/* Upper Thigh */}
          <mesh position={[0, -0.16, 0]} material={pantsMaterial}>
            <cylinderGeometry args={[0.055, 0.048, 0.32, 10]} />
          </mesh>
          {/* Knee & Calf */}
          <group position={[0, -0.32, 0]} rotation={[rightShinPitch, 0, 0]}>
            <mesh position={[0, -0.16, 0]} material={pantsMaterial}>
              <cylinderGeometry args={[0.046, 0.04, 0.32, 10]} />
            </mesh>
            {/* Shoe / Boot */}
            <mesh position={[0, -0.32, 0.04]} material={shoeMaterial}>
              <boxGeometry args={[0.085, 0.07, 0.17]} />
            </mesh>
          </group>
        </group>
      </group>

      {/* Target Reticle Halo */}
      <mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.42, 0.5, 28]} />
        <meshBasicMaterial
          color={isSelected ? "#00f0ff" : roleColor}
          transparent
          opacity={isSelected ? 0.95 : 0.45}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Floating Tactical Role Marker Pin */}
      <mesh position={[0, 1.9, 0]}>
        <sphereGeometry args={[0.05, 12, 12]} />
        <meshBasicMaterial color={roleColor} />
      </mesh>
    </group>
  );
}

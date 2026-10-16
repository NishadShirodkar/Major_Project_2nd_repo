import React, { useMemo, useRef } from "react";
import * as THREE from "three";
import RiderAvatar from "./RiderAvatar";
import { resolveEntityWaypoints, sampleEntityState } from "./kinematics";

// =======================================================================
// PROCEDURAL HIGH-FIDELITY FORENSIC VEHICLES (NO MISSING GLB DEPENDENCIES)
// =======================================================================

function MotorcycleMesh({ accentColor = "#00f0ff", isSelected = false }) {
  const bodyMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#18202c",
        metalness: 0.85,
        roughness: 0.25,
      }),
    []
  );

  const frameMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#10141a",
        metalness: 0.5,
        roughness: 0.6,
      }),
    []
  );

  const chromeMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#c0c8d4",
        metalness: 0.95,
        roughness: 0.1,
      }),
    []
  );

  const tireMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#0a0c10",
        roughness: 0.9,
        metalness: 0.1,
      }),
    []
  );

  const seatMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#121418",
        roughness: 0.8,
        metalness: 0.05,
      }),
    []
  );

  const accentMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: accentColor,
      }),
    [accentColor]
  );

  const headlightMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: "#e0f8ff",
      }),
    []
  );

  const taillightMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: "#ff0033",
      }),
    []
  );

  return (
    <group>
      {/* 1. Wheels */}
      {/* Front Wheel */}
      <group position={[0, 0.32, 0.72]}>
        {/* Tire */}
        <mesh rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
          <torusGeometry args={[0.3, 0.065, 16, 28]} />
        </mesh>
        {/* Rim & Disc */}
        <mesh rotation={[0, 0, Math.PI / 2]} material={chromeMaterial}>
          <cylinderGeometry args={[0.22, 0.22, 0.04, 16]} />
        </mesh>
        <mesh rotation={[0, 0, Math.PI / 2]} material={accentMaterial}>
          <ringGeometry args={[0.18, 0.21, 16]} />
        </mesh>
      </group>

      {/* Rear Wheel */}
      <group position={[0, 0.32, -0.68]}>
        <mesh rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
          <torusGeometry args={[0.3, 0.075, 16, 28]} />
        </mesh>
        <mesh rotation={[0, 0, Math.PI / 2]} material={chromeMaterial}>
          <cylinderGeometry args={[0.22, 0.22, 0.05, 16]} />
        </mesh>
        <mesh rotation={[0, 0, Math.PI / 2]} material={accentMaterial}>
          <ringGeometry args={[0.18, 0.21, 16]} />
        </mesh>
      </group>

      {/* 2. Chassis Frame & Swingarm */}
      <mesh position={[0, 0.38, -0.32]} material={frameMaterial}>
        <boxGeometry args={[0.16, 0.08, 0.65]} />
      </mesh>

      {/* Front Telescopic Forks */}
      <group position={[0, 0.55, 0.6]} rotation={[-0.32, 0, 0]}>
        <mesh position={[-0.09, 0, 0]} material={chromeMaterial}>
          <cylinderGeometry args={[0.02, 0.02, 0.65, 8]} />
        </mesh>
        <mesh position={[0.09, 0, 0]} material={chromeMaterial}>
          <cylinderGeometry args={[0.02, 0.02, 0.65, 8]} />
        </mesh>
      </group>

      {/* 3. Engine Block & Transmission */}
      <mesh position={[0, 0.38, 0.02]} material={frameMaterial}>
        <boxGeometry args={[0.26, 0.28, 0.38]} />
      </mesh>
      {/* Engine Cooling Fins */}
      <mesh position={[0, 0.44, 0.05]} material={chromeMaterial}>
        <boxGeometry args={[0.24, 0.12, 0.28]} />
      </mesh>

      {/* 4. Sculpted Fuel Tank */}
      <mesh position={[0, 0.66, 0.22]} material={bodyMaterial}>
        <boxGeometry args={[0.28, 0.22, 0.44]} />
      </mesh>
      {/* Tank Racing Accent Strips */}
      <mesh position={[0, 0.76, 0.22]} material={accentMaterial}>
        <boxGeometry args={[0.05, 0.03, 0.4]} />
      </mesh>

      {/* 5. Aerodynamic Front Cowl & Headlight */}
      <group position={[0, 0.78, 0.58]} rotation={[-0.1, 0, 0]}>
        <mesh material={bodyMaterial}>
          <boxGeometry args={[0.24, 0.2, 0.22]} />
        </mesh>
        {/* Headlamp */}
        <mesh position={[0, 0, 0.11]} material={headlightMaterial}>
          <planeGeometry args={[0.18, 0.1]} />
        </mesh>
        {/* Cyan Accent Bezel */}
        <mesh position={[0, -0.06, 0.112]} material={accentMaterial}>
          <planeGeometry args={[0.2, 0.02]} />
        </mesh>
      </group>

      {/* 6. Handlebars */}
      <group position={[0, 0.88, 0.48]}>
        <mesh rotation={[0, 0, Math.PI / 2]} material={chromeMaterial}>
          <cylinderGeometry args={[0.015, 0.015, 0.52, 8]} />
        </mesh>
        {/* Left & Right Grips */}
        <mesh position={[-0.24, 0, 0]} rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
          <cylinderGeometry args={[0.02, 0.02, 0.08, 8]} />
        </mesh>
        <mesh position={[0.24, 0, 0]} rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
          <cylinderGeometry args={[0.02, 0.02, 0.08, 8]} />
        </mesh>
      </group>

      {/* 7. Contoured Sport Seat */}
      <mesh position={[0, 0.62, -0.15]} material={seatMaterial}>
        <boxGeometry args={[0.22, 0.1, 0.48]} />
      </mesh>
      {/* Pillion Seat Step */}
      <mesh position={[0, 0.68, -0.42]} material={seatMaterial}>
        <boxGeometry args={[0.19, 0.12, 0.26]} />
      </mesh>

      {/* 8. Tail Section & Taillight */}
      <mesh position={[0, 0.65, -0.62]} material={bodyMaterial}>
        <boxGeometry args={[0.18, 0.12, 0.22]} />
      </mesh>
      <mesh position={[0, 0.66, -0.74]} material={taillightMaterial}>
        <boxGeometry args={[0.14, 0.04, 0.02]} />
      </mesh>

      {/* 9. Chrome Exhaust System */}
      <group position={[0.16, 0.28, -0.22]} rotation={[0.08, 0, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} material={chromeMaterial}>
          <cylinderGeometry args={[0.04, 0.045, 0.68, 12]} />
        </mesh>
      </group>
    </group>
  );
}

function ScooterMesh({ accentColor = "#ffb700", isSelected = false }) {
  const bodyMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#222a36",
        metalness: 0.6,
        roughness: 0.35,
      }),
    []
  );

  const innerPanelMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#12161f",
        metalness: 0.2,
        roughness: 0.8,
      }),
    []
  );

  const tireMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#0a0c10",
        roughness: 0.9,
        metalness: 0.1,
      }),
    []
  );

  const seatMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#101216",
        roughness: 0.85,
        metalness: 0.05,
      }),
    []
  );

  const accentMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: accentColor,
      }),
    [accentColor]
  );

  const chromeMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#c0c8d4",
        metalness: 0.95,
        roughness: 0.1,
      }),
    []
  );

  const headlightMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: "#fff8e8",
      }),
    []
  );

  const taillightMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: "#ff0033",
      }),
    []
  );

  return (
    <group>
      {/* 1. Scooter Wheels (Smaller radius than motorcycle) */}
      {/* Front Wheel */}
      <group position={[0, 0.24, 0.62]}>
        <mesh rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
          <torusGeometry args={[0.22, 0.065, 14, 24]} />
        </mesh>
        <mesh rotation={[0, 0, Math.PI / 2]} material={chromeMaterial}>
          <cylinderGeometry args={[0.15, 0.15, 0.04, 12]} />
        </mesh>
      </group>

      {/* Rear Wheel (partially recessed) */}
      <group position={[0, 0.24, -0.52]}>
        <mesh rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
          <torusGeometry args={[0.22, 0.065, 14, 24]} />
        </mesh>
      </group>

      {/* 2. Flat Footboard */}
      <mesh position={[0, 0.24, 0.08]} material={innerPanelMaterial}>
        <boxGeometry args={[0.38, 0.06, 0.44]} />
      </mesh>

      {/* 3. Curved Front Apron / Leg Shield */}
      <group position={[0, 0.52, 0.42]} rotation={[-0.2, 0, 0]}>
        <mesh material={bodyMaterial}>
          <boxGeometry args={[0.42, 0.48, 0.12]} />
        </mesh>
        {/* Accent Strip */}
        <mesh position={[0, 0, 0.065]} material={accentMaterial}>
          <planeGeometry args={[0.06, 0.38]} />
        </mesh>
      </group>

      {/* 4. Handlebar Fairing with Integrated Headlamp */}
      <group position={[0, 0.86, 0.36]}>
        <mesh material={bodyMaterial}>
          <boxGeometry args={[0.46, 0.14, 0.16]} />
        </mesh>
        {/* Headlamp */}
        <mesh position={[0, 0.02, 0.085]} material={headlightMaterial}>
          <planeGeometry args={[0.16, 0.08]} />
        </mesh>
        {/* Handlebar Grips */}
        <mesh position={[-0.26, 0, 0]} rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
          <cylinderGeometry args={[0.02, 0.02, 0.08, 8]} />
        </mesh>
        <mesh position={[0.26, 0, 0]} rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
          <cylinderGeometry args={[0.02, 0.02, 0.08, 8]} />
        </mesh>
      </group>

      {/* 5. Bulbous Rear Engine Body (Activa style) */}
      <group position={[0, 0.46, -0.32]}>
        <mesh material={bodyMaterial}>
          <boxGeometry args={[0.44, 0.38, 0.58]} />
        </mesh>
        {/* Side Accent Trim */}
        <mesh position={[-0.225, 0.04, 0]} rotation={[0, -Math.PI / 2, 0]} material={accentMaterial}>
          <planeGeometry args={[0.4, 0.03]} />
        </mesh>
        <mesh position={[0.225, 0.04, 0]} rotation={[0, Math.PI / 2, 0]} material={accentMaterial}>
          <planeGeometry args={[0.4, 0.03]} />
        </mesh>
      </group>

      {/* 6. Wide Dual Seat */}
      <mesh position={[0, 0.68, -0.16]} material={seatMaterial}>
        <boxGeometry args={[0.32, 0.1, 0.58]} />
      </mesh>

      {/* 7. Rear Taillight Cluster */}
      <mesh position={[0, 0.56, -0.62]} material={taillightMaterial}>
        <boxGeometry args={[0.24, 0.08, 0.03]} />
      </mesh>

      {/* 8. Scooter Exhaust */}
      <group position={[0.18, 0.22, -0.32]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} material={innerPanelMaterial}>
          <cylinderGeometry args={[0.045, 0.05, 0.45, 8]} />
        </mesh>
      </group>
    </group>
  );
}

function CarMesh({ accentColor = "#00f0ff", isSelected = false }) {
  const bodyMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#1c2230",
        metalness: 0.8,
        roughness: 0.3,
      }),
    []
  );

  const glassMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#0a1824",
        metalness: 0.9,
        roughness: 0.1,
        transparent: true,
        opacity: 0.75,
      }),
    []
  );

  const tireMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#0a0c10",
        roughness: 0.9,
        metalness: 0.1,
      }),
    []
  );

  return (
    <group position={[0, 0, 0]}>
      {/* Lower Chassis */}
      <mesh position={[0, 0.35, 0]} material={bodyMaterial}>
        <boxGeometry args={[1.7, 0.45, 3.8]} />
      </mesh>
      {/* Cabin Roof */}
      <mesh position={[0, 0.78, -0.2]} material={glassMaterial}>
        <boxGeometry args={[1.4, 0.46, 2.0]} />
      </mesh>
      {/* 4 Wheels */}
      {[-0.8, 0.8].map((x) =>
        [-1.1, 1.1].map((z) => (
          <group key={`${x}_${z}`} position={[x, 0.3, z]}>
            <mesh rotation={[0, 0, Math.PI / 2]} material={tireMaterial}>
              <cylinderGeometry args={[0.3, 0.3, 0.18, 16]} />
            </mesh>
          </group>
        ))
      )}
    </group>
  );
}

// =======================================================================
// MAIN VEHICLE MODEL COMPONENT
// =======================================================================

export default function VehicleModel({
  vehicle,
  timeline = [],
  currentTime = 0,
  isSelected = false,
  onSelect,
}) {
  const waypoints = useMemo(() => resolveEntityWaypoints(vehicle, timeline), [vehicle, timeline]);
  const isVehicle1 = vehicle.id === "vehicle_1";

  // Dynamic Waypoint Kinematics & Post-Impact Simulation
  const { position, rotation } = useMemo(() => {
    const sampled = sampleEntityState(waypoints, currentTime);
    let rot = { ...sampled.rotation };
    let pos = { ...sampled.position };

    // Post-impact shock & tilt dynamics
    if (currentTime > 5.0) {
      const dt = currentTime - 5.0;
      const progress = Math.min(1, dt / 5.0);
      const slideProgress = 1 - Math.pow(1 - progress, 2);

      // 1. High-Frequency Contact Shock & Wobble
      if (dt <= 1.2) {
        const envelope = Math.exp(-4.5 * dt);
        const freq = 28;
        const wobbleYaw = Math.sin(freq * dt) * 0.12 * envelope;
        const wobbleRoll = Math.cos(freq * dt * 0.8) * 0.15 * envelope;

        rot.y += isVehicle1 ? wobbleYaw : -wobbleYaw;
        rot.z += wobbleRoll;
      }

      // 2. Progressive Chassis Deflection & Resting Tilt
      let tiltAmount = 0;
      if (isVehicle1) {
        tiltAmount = slideProgress * 0.55;
        rot.z += tiltAmount;
        rot.y += slideProgress * 0.2;
      } else {
        tiltAmount = slideProgress * 1.2;
        rot.x += tiltAmount;
        rot.y += slideProgress * 0.35;
      }

      // 3. Ground Plane Clamping
      const bikeHeightOffset = Math.sin(Math.abs(tiltAmount)) * 0.35;
      pos.y = Math.max(0.04, bikeHeightOffset);
    }

    return { position: pos, rotation: rot, activeSegmentIndex: sampled.activeSegmentIndex };
  }, [waypoints, currentTime, isVehicle1]);

  const modelName = (vehicle.model || vehicle.make || "").toLowerCase();
  const isTwoWheeler =
    vehicle.type === "two_wheeler" ||
    !vehicle.type ||
    modelName.includes("pulsar") ||
    modelName.includes("bike") ||
    modelName.includes("activa") ||
    modelName.includes("scooter");

  const isScooter =
    !isVehicle1 &&
    (modelName.includes("activa") ||
      vehicle.asset_path?.includes("vespa") ||
      modelName.includes("scooter"));

  const isCar = vehicle.type === "four_wheeler" || modelName.includes("car");

  const riderColor = isVehicle1 ? "#00f0ff" : "#ffb700";
  const riderRotationY = isVehicle1 ? -Math.PI / 2 : 0;
  const seatOffset = isVehicle1 ? [0, 0.62, 0] : [0, 0.68, -0.05];
  const fallProgress = currentTime <= 5.0 ? 0 : Math.min(1, (currentTime - 5.0) / 4.0);

  return (
    <group
      onClick={(e) => {
        e.stopPropagation();
        if (onSelect) onSelect(vehicle.id);
      }}
    >
      {/* 3D Vehicle & Mounted Rider Group */}
      <group position={[position.x, position.y, position.z]}>
        {/* Scaled & Centered 3D Procedural Model with Ground Clamped Rotation */}
        <group rotation={[rotation.x, rotation.y, rotation.z]}>
          {isCar ? (
            <CarMesh accentColor={riderColor} isSelected={isSelected} />
          ) : isScooter ? (
            <ScooterMesh accentColor={riderColor} isSelected={isSelected} />
          ) : (
            <MotorcycleMesh accentColor={riderColor} isSelected={isSelected} />
          )}
        </group>

        {/* Mount Rider Avatar only on Two-Wheelers */}
        {isTwoWheeler && (
          <RiderAvatar
            color={riderColor}
            isScooter={isScooter}
            vehicleRotation={rotation}
            riderRotationY={riderRotationY}
            seatOffset={seatOffset}
            fallProgress={fallProgress}
            isVictim={!isVehicle1}
          />
        )}
      </group>

      {/* Detective HUD Vehicle Target Reticle / Highlight Halo */}
      <mesh
        position={[position.x, 0.05, position.z]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <ringGeometry args={[0.9, 0.98, 32]} />
        <meshBasicMaterial
          color={isSelected ? "#00f0ff" : "#ffb700"}
          transparent
          opacity={isSelected ? 0.9 : 0.4}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Floating Target ID Tag */}
      <mesh position={[position.x, 1.8, position.z]}>
        <sphereGeometry args={[0.06, 12, 12]} />
        <meshBasicMaterial color={isSelected ? "#00f0ff" : "#ffb700"} />
      </mesh>
    </group>
  );
}
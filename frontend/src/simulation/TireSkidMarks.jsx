import React, { useMemo } from "react";
import * as THREE from "three";

/**
 * Procedural Forensic Tire Skid Marks & Metallic Chassis Scrape Decals.
 * In forensic investigation, skid marks measure pre-impact braking distance to determine initial speed.
 */
export default function TireSkidMarks({ currentTime = 0, isIndoor = false }) {
  if (isIndoor) return null;

  // Skid timeline:
  // Pre-impact braking occurs between 3.2s and 5.0s
  // Post-impact chassis gouge occurs between 5.0s and 8.0s
  const brakeProgress = Math.min(1.0, Math.max(0.0, (currentTime - 3.2) / 1.8));
  const gougeProgress = Math.min(1.0, Math.max(0.0, (currentTime - 5.0) / 3.0));

  const rubberMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: "#0a0c10",
        transparent: true,
        opacity: 0.82,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    []
  );

  const metallicScrapeMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: "#4a5568",
        transparent: true,
        opacity: 0.65,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    []
  );

  return (
    <group position={[0, 0.015, 0]}>
      {/* ============================================================ */}
      {/* 1. VEHICLE 1 (PULSAR 150) EMERGENCY BRAKING SKID (WEST TO EAST) */}
      {/* Skid starts at X = -14.0, ends at impact point X = -0.6 (13.4m)*/}
      {/* ============================================================ */}
      {brakeProgress > 0 && (
        <group>
          {/* Rear Locked Tire Rubber Track (Primary Black Line) */}
          <mesh
            position={[
              -14.0 + (13.4 * brakeProgress) / 2,
              0,
              -1.75,
            ]}
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <planeGeometry args={[13.4 * brakeProgress, 0.18]} />
            <primitive object={rubberMaterial} attach="material" />
          </mesh>

          {/* Front Tire Secondary Yaw Scrub Line */}
          <mesh
            position={[
              -12.0 + (11.4 * brakeProgress) / 2,
              0,
              -1.68,
            ]}
            rotation={[-Math.PI / 2, 0, 0.02]}
          >
            <planeGeometry args={[11.4 * brakeProgress, 0.12]} />
            <meshBasicMaterial
              color="#111827"
              transparent
              opacity={0.65 * brakeProgress}
              depthWrite={false}
              side={THREE.DoubleSide}
            />
          </mesh>

          {/* Forensic Skid Distance HUD Measurement Ribbon */}
          {brakeProgress >= 0.8 && (
            <group position={[-7.3, 0.05, -2.1]}>
              <mesh rotation={[-Math.PI / 2, 0, 0]}>
                <planeGeometry args={[13.4, 0.02]} />
                <meshBasicMaterial color="#00f0ff" transparent opacity={0.6} />
              </mesh>
            </group>
          )}
        </group>
      )}

      {/* ============================================================ */}
      {/* 2. VEHICLE 2 (ACTIVA) BRAKING SKID (NORTH TO SOUTH)           */}
      {/* Skid starts at Z = -11.0, ends at impact point Z = -0.5 (10.5m)*/}
      {/* ============================================================ */}
      {brakeProgress > 0 && (
        <group>
          {/* Locked Scooter Wheels Skid Path */}
          <mesh
            position={[
              0.0,
              0,
              -11.0 + (10.5 * brakeProgress) / 2,
            ]}
            rotation={[-Math.PI / 2, 0, Math.PI / 2]}
          >
            <planeGeometry args={[10.5 * brakeProgress, 0.16]} />
            <primitive object={rubberMaterial} attach="material" />
          </mesh>
        </group>
      )}

      {/* ============================================================ */}
      {/* 3. POST-IMPACT METALLIC CHASSIS SCRAPE & ASPHALT GOUGE MARK  */}
      {/* Frame scratches across road from impact (-0.6, 0) to rest (7.2, 2.4)*/}
      {/* ============================================================ */}
      {gougeProgress > 0 && (
        <group>
          {/* Main Scrape Arc */}
          <mesh
            position={[
              -0.6 + (7.8 * gougeProgress) / 2,
              0,
              0.0 + (2.4 * gougeProgress) / 2,
            ]}
            rotation={[-Math.PI / 2, 0, Math.atan2(2.4, 7.8)]}
          >
            <planeGeometry args={[Math.hypot(7.8, 2.4) * gougeProgress, 0.22]} />
            <primitive object={metallicScrapeMaterial} attach="material" />
          </mesh>

          {/* Deep Asphalt Gouge Groove at Epicenter */}
          <mesh position={[-0.4, 0, 0.1]} rotation={[-Math.PI / 2, 0, 0.4]}>
            <planeGeometry args={[1.2 * gougeProgress, 0.08]} />
            <meshBasicMaterial color="#000000" transparent opacity={0.9} depthWrite={false} />
          </mesh>
        </group>
      )}
    </group>
  );
}

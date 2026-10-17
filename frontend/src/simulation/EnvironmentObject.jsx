import React, { useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";

function GLBProp({ assetPath, targetDimensions = { x: 1, y: 1, z: 1 }, positionOffset = [0, 0, 0], rotationOffset = [0, 0, 0] }) {
  const { scene } = useGLTF(assetPath);
  const { cloned, scale } = useMemo(() => {
    const clone = scene.clone();
    const box = new THREE.Box3().setFromObject(clone);
    const center = new THREE.Vector3();
    box.getCenter(center);
    const size = new THREE.Vector3();
    box.getSize(size);

    // Center on floor (y=0)
    clone.position.x = -center.x + positionOffset[0];
    clone.position.y = -box.min.y + positionOffset[1];
    clone.position.z = -center.z + positionOffset[2];
    clone.rotation.x += rotationOffset[0];
    clone.rotation.y += rotationOffset[1];
    clone.rotation.z += rotationOffset[2];

    // Compute metric scale ratio against target metric dimensions
    const maxMeshDim = Math.max(size.x, size.y, size.z);
    const maxTargetDim = Math.max(targetDimensions.x, targetDimensions.y, targetDimensions.z);
    const calculatedScale = maxMeshDim > 0 ? maxTargetDim / maxMeshDim : 1.0;

    return { cloned: clone, scale: calculatedScale };
  }, [scene, targetDimensions, positionOffset, rotationOffset]);

  return <primitive object={cloned} scale={scale} />;
}

/**
 * Renders authentic, forensically grounded 3D architectural fixtures and environment props
 * based on Scene IR environment_objects.
 */
export default function EnvironmentObject({ object, currentTime = 0 }) {
  const { type, position = { x: 0, y: 0, z: 0 }, rotation = { x: 0, y: 0, z: 0 } } = object;


  const rotRad = useMemo(
    () => [
      ((rotation.x || 0) * Math.PI) / 180,
      ((rotation.y || 0) * Math.PI) / 180,
      ((rotation.z || 0) * Math.PI) / 180,
    ],
    [rotation]
  );

  // Common Forensic Materials
  const woodMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#5c3a21",
        roughness: 0.7,
        metalness: 0.1,
      }),
    []
  );

  const darkWoodMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#2a1c14",
        roughness: 0.6,
        metalness: 0.15,
      }),
    []
  );

  const fabricMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: object.color || "#243346",
        roughness: 0.85,
        metalness: 0.05,
      }),
    [object.color]
  );

  const cushionMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#1c2738",
        roughness: 0.9,
        metalness: 0.05,
      }),
    []
  );

  const glassMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#a0e0ff",
        transparent: true,
        opacity: 0.45,
        roughness: 0.1,
        metalness: 0.8,
      }),
    []
  );

  const concreteMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#2d3748",
        roughness: 0.9,
        metalness: 0.1,
      }),
    []
  );

  const metalMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#4a5568",
        roughness: 0.4,
        metalness: 0.8,
      }),
    []
  );

  return (
    <group position={[position.x, position.y, position.z]} rotation={rotRad}>
      {/* ============================================================ */}
      {/* 1. BREACHED ENTRANCE DOORWAY (FLAT 302 HOMICIDE)              */}
      {/* ============================================================ */}
      {type === "door_frame" && (
        <group>
          {/* Outer Door Frame Posts */}
          <mesh position={[-0.45, 1.1, 0]} material={darkWoodMaterial}>
            <boxGeometry args={[0.08, 2.2, 0.14]} />
          </mesh>
          <mesh position={[0.45, 1.1, 0]} material={darkWoodMaterial}>
            <boxGeometry args={[0.08, 2.2, 0.14]} />
          </mesh>
          {/* Header Beam */}
          <mesh position={[0, 2.16, 0]} material={darkWoodMaterial}>
            <boxGeometry args={[0.98, 0.08, 0.14]} />
          </mesh>

          {/* Dynamic Door Panel: Closed at t < 2.0s, swings open inward at t >= 2.0s */}
          {(() => {
            const isBreached = currentTime >= 2.0;
            const doorOpenProgress = isBreached ? Math.min(1.0, (currentTime - 2.0) / 0.8) : 0;
            const doorAngle = -doorOpenProgress * 1.35; // Swings from 0 deg to ~78 deg open
            return (
              <group position={[-0.41, 0, 0]} rotation={[0, doorAngle, 0]}>
                <mesh position={[0.41, 1.05, 0.02]} material={woodMaterial}>
                  <boxGeometry args={[0.82, 2.1, 0.05]} />
                </mesh>
                {/* Brass Door Handle & Lock Plate */}
                <mesh position={[0.74, 1.0, 0.05]} material={metalMaterial}>
                  <boxGeometry args={[0.04, 0.14, 0.02]} />
                </mesh>
                <mesh position={[0.76, 1.0, 0.08]} material={metalMaterial}>
                  <cylinderGeometry args={[0.012, 0.012, 0.08, 8]} />
                </mesh>
                {/* Splinter / Fracture Crack Decal */}
                {isBreached && (
                  <mesh position={[0.74, 1.0, 0.055]}>
                    <planeGeometry args={[0.08, 0.22]} />
                    <meshBasicMaterial color="#1a0f08" />
                  </mesh>
                )}
              </group>
            );
          })()}

          {/* Wood Splinters Scattered on Floor */}
          <mesh position={[0.2, 0.01, 0.35]} material={woodMaterial}>
            <boxGeometry args={[0.18, 0.01, 0.04]} />
          </mesh>
          <mesh position={[-0.1, 0.01, 0.28]} rotation={[0, 0.8, 0]} material={woodMaterial}>
            <boxGeometry args={[0.12, 0.01, 0.03]} />
          </mesh>
          <mesh position={[0.35, 0.01, 0.5]} rotation={[0, -0.4, 0]} material={woodMaterial}>
            <boxGeometry args={[0.09, 0.01, 0.025]} />
          </mesh>
        </group>
      )}

      {/* ============================================================ */}
      {/* 2. LIVING ROOM 3-SEATER SOFA                                 */}
      {/* ============================================================ */}
      {type === "sofa_3seater" && (
        <group>
          {/* Real sofa: ~2.2m length x 0.85m height x 0.9m depth */}
          <GLBProp assetPath="/assets/props/sofa_3seater.glb" targetDimensions={{ x: 2.2, y: 0.85, z: 0.9 }} />
        </group>
      )}

      {/* ============================================================ */}
      {/* 3. CENTER COFFEE TABLE (WITH GLASS TOP & TEA CUPS)          */}
      {/* ============================================================ */}
      {type === "coffee_table" && (
        <group>
          {/* Wooden Perimeter Frame */}
          <mesh position={[0, 0.38, 0]} material={darkWoodMaterial}>
            <boxGeometry args={[1.2, 0.05, 0.7]} />
          </mesh>
          {/* Tempered Glass Inset Top */}
          <mesh position={[0, 0.41, 0]} material={glassMaterial}>
            <boxGeometry args={[1.12, 0.015, 0.62]} />
          </mesh>
          {/* 4 Table Legs */}
          {[-0.52, 0.52].map((x, i) =>
            [-0.28, 0.28].map((z, j) => (
              <mesh key={`table_leg_${i}_${j}`} position={[x, 0.19, z]} material={darkWoodMaterial}>
                <boxGeometry args={[0.05, 0.38, 0.05]} />
              </mesh>
            ))
          )}
          {/* Bottom Magazine Shelf */}
          <mesh position={[0, 0.12, 0]} material={woodMaterial}>
            <boxGeometry args={[1.05, 0.02, 0.55]} />
          </mesh>
          {/* Tea Cup Evidence Prop on Table */}
          <mesh position={[-0.2, 0.44, 0.1]}>
            <cylinderGeometry args={[0.035, 0.025, 0.06, 12]} />
            <meshStandardMaterial color="#f0ede6" roughness={0.3} />
          </mesh>
          <mesh position={[-0.2, 0.415, 0.1]}>
            <cylinderGeometry args={[0.055, 0.055, 0.008, 12]} />
            <meshStandardMaterial color="#f0ede6" roughness={0.3} />
          </mesh>
        </group>
      )}

      {/* ============================================================ */}
      {/* 4. ENTERTAINMENT / TV CONSOLE UNIT                           */}
      {/* ============================================================ */}
      {type === "tv_unit" && (
        <group>
          {/* Low Media Credenza */}
          <mesh position={[0, 0.28, 0]} material={darkWoodMaterial}>
            <boxGeometry args={[2.0, 0.45, 0.4]} />
          </mesh>
          {/* Cabinet Door Grooves */}
          <mesh position={[-0.5, 0.28, 0.205]}>
            <planeGeometry args={[0.9, 0.38]} />
            <meshStandardMaterial color="#1f140e" />
          </mesh>
          <mesh position={[0.5, 0.28, 0.205]}>
            <planeGeometry args={[0.9, 0.38]} />
            <meshStandardMaterial color="#1f140e" />
          </mesh>
          {/* Wall-Mounted Flat-Panel TV */}
          <group position={[0, 1.25, 0.15]}>
            {/* TV Bezel */}
            <mesh material={metalMaterial}>
              <boxGeometry args={[1.4, 0.8, 0.04]} />
            </mesh>
            {/* Glossy Black Display Screen */}
            <mesh position={[0, 0, 0.025]}>
              <planeGeometry args={[1.34, 0.74]} />
              <meshStandardMaterial color="#05080c" roughness={0.1} metalness={0.9} />
            </mesh>
          </group>
        </group>
      )}

      {/* ============================================================ */}
      {/* 5. CEILING PENDANT LAMP WITH WARM INTERIOR ILLUMINATION     */}
      {/* ============================================================ */}
      {type === "ceiling_lamp" && (
        <group>
          {/* Cable */}
          <mesh position={[0, 0.2, 0]} material={metalMaterial}>
            <cylinderGeometry args={[0.006, 0.006, 0.4, 8]} />
          </mesh>
          {/* Lamp Shade */}
          <mesh position={[0, -0.05, 0]}>
            <coneGeometry args={[0.22, 0.18, 16, 1, true]} />
            <meshStandardMaterial color="#0f172a" roughness={0.4} metalness={0.8} side={THREE.DoubleSide} />
          </mesh>
          {/* Glowing Bulb */}
          <mesh position={[0, -0.06, 0]}>
            <sphereGeometry args={[0.05, 12, 12]} />
            <meshBasicMaterial color="#ffe8b3" />
          </mesh>
          {/* Warm Interior Ambient PointLight */}
          <pointLight position={[0, -0.15, 0]} intensity={1.8} distance={10} color="#ffdfa0" decay={2} castShadow />
        </group>
      )}

      {/* ============================================================ */}
      {/* 6. CONCRETE PEDESTRIAN SIDEWALK & CURB (OUTDOOR ROAD)       */}
      {/* ============================================================ */}
      {type === "sidewalk" && (
        <group>
          {/* Raised Sidewalk Slab */}
          <mesh position={[0, 0.08, 0]} material={concreteMaterial}>
            <boxGeometry args={[object.dimensions?.x || 30, 0.16, object.dimensions?.z || 2.4]} />
          </mesh>
          {/* High-Contrast Beveled Curb Stone Trim */}
          <mesh position={[0, 0.085, (object.dimensions?.z || 2.4) / 2 - 0.08]}>
            <boxGeometry args={[object.dimensions?.x || 30, 0.18, 0.16]} />
            <meshStandardMaterial color="#475569" roughness={0.8} />
          </mesh>
        </group>
      )}

      {/* ============================================================ */}
      {/* 7. ROADSIDE COMMERCIAL BUILDING / FACADE (OUTDOOR T-POINT)  */}
      {/* ============================================================ */}
      {type === "building" && (
        <group>
          {/* Building Main Concrete Massing */}
          <mesh position={[0, (object.dimensions?.y || 9) / 2, 0]}>
            <boxGeometry args={[object.dimensions?.x || 14, object.dimensions?.y || 9, object.dimensions?.z || 12]} />
            <meshStandardMaterial color="#1e293b" roughness={0.85} metalness={0.15} />
          </mesh>

          {/* Ground Floor Storefront Recess */}
          <mesh position={[0, 1.6, (object.dimensions?.z || 12) / 2 + 0.02]}>
            <boxGeometry args={[(object.dimensions?.x || 14) * 0.85, 3.0, 0.08]} />
            <meshStandardMaterial color="#0f172a" roughness={0.2} metalness={0.8} />
          </mesh>

          {/* Faint Window Lighting Grid on Upper Floors */}
          {[-1, 1].map((floor, fi) =>
            [-3.5, 0, 3.5].map((wx, wi) => (
              <mesh
                key={`win_${fi}_${wi}`}
                position={[wx, 5.0 + floor * 2.2, (object.dimensions?.z || 12) / 2 + 0.04]}
              >
                <planeGeometry args={[1.6, 1.2]} />
                <meshStandardMaterial
                  color={(fi + wi) % 2 === 0 ? "#ffd580" : "#1e293b"}
                  emissive={(fi + wi) % 2 === 0 ? "#ffd580" : "#000000"}
                  emissiveIntensity={(fi + wi) % 2 === 0 ? 0.35 : 0}
                  roughness={0.2}
                />
              </mesh>
            ))
          )}

          {/* Roof Parapet Trim */}
          <mesh position={[0, (object.dimensions?.y || 9) + 0.15, 0]}>
            <boxGeometry args={[(object.dimensions?.x || 14) + 0.2, 0.3, (object.dimensions?.z || 12) + 0.2]} />
            <meshStandardMaterial color="#334155" roughness={0.7} />
          </mesh>
        </group>
      )}

      {/* ============================================================ */}
      {/* 8. RAMESH'S ROADSIDE TEA STALL KIOSK (DELHI T-POINT)        */}
      {/* ============================================================ */}
      {type === "tea_stall" && (
        <group>
          {/* Wooden Vendor Booth */}
          <mesh position={[0, 1.1, 0]} material={woodMaterial}>
            <boxGeometry args={[2.4, 2.2, 1.8]} />
          </mesh>
          {/* Service Counter Opening */}
          <mesh position={[0, 1.0, 0.92]}>
            <boxGeometry args={[1.8, 0.8, 0.2]} />
            <meshStandardMaterial color="#1a110b" />
          </mesh>
          {/* Blue/White Slanted Weather Awning */}
          <group position={[0, 2.2, 0.6]} rotation={[0.3, 0, 0]}>
            <mesh>
              <boxGeometry args={[2.6, 0.04, 1.4]} />
              <meshStandardMaterial color="#0284c7" roughness={0.6} />
            </mesh>
          </group>
          {/* Eyewitness Position Indicator Halo */}
          <mesh position={[0, 0.02, 1.3]} rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.4, 0.55, 24]} />
            <meshBasicMaterial color="#00f0ff" transparent opacity={0.6} side={THREE.DoubleSide} />
          </mesh>
        </group>
      )}

      {/* ============================================================ */}
      {/* 9. STREET LIGHT POLE WITH STREETLIGHT POOL CONE             */}
      {/* ============================================================ */}
      {type === "street_light" && (
        <group>
          {/* Vertical Pole */}
          <mesh position={[0, 3.2, 0]} material={metalMaterial}>
            <cylinderGeometry args={[0.07, 0.1, 6.4, 12]} />
          </mesh>
          {/* Overhanging Arm toward road */}
          <group position={[0, 6.3, 0]} rotation={[0, 0, -0.3]}>
            <mesh position={[0.7, 0, 0]} rotation={[0, 0, Math.PI / 2]} material={metalMaterial}>
              <cylinderGeometry args={[0.05, 0.05, 1.5, 8]} />
            </mesh>
            {/* Lamp Luminaire Head */}
            <mesh position={[1.4, -0.05, 0]}>
              <boxGeometry args={[0.35, 0.12, 0.22]} />
              <meshStandardMaterial color="#334155" metalness={0.9} />
            </mesh>
            {/* Glowing Lamp Lens */}
            <mesh position={[1.4, -0.11, 0]}>
              <planeGeometry args={[0.3, 0.18]} />
              <meshBasicMaterial color="#ffea9f" />
            </mesh>
            {/* Downward Streetlight Spotlight */}
            <spotLight
              position={[1.4, -0.15, 0]}
              target-position={[1.4, -6.0, 0]}
              intensity={4.5}
              angle={0.55}
              penumbra={0.6}
              color="#ffe599"
              castShadow
            />
          </group>
        </group>
      )}

      {/* ============================================================ */}
      {/* 10. SHATTERED VEHICLE GLASS DEBRIS SCATTER AT EPICENTER      */}
      {/* ============================================================ */}
      {type === "debris_glass" && (
        <group>
          {/* Subtle localized dark asphalt impact scuff instead of green disc */}
          <mesh position={[0, 0.008, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.55, 16]} />
            <meshBasicMaterial color="#111827" transparent opacity={0.25} />
          </mesh>
          {/* Individual Glinting Glass Shards */}
          {[
            [-0.3, 0.2],
            [0.4, -0.1],
            [-0.1, -0.4],
            [0.2, 0.5],
            [-0.5, -0.2],
            [0.6, 0.3],
            [0.05, -0.15],
            [-0.25, 0.35],
          ].map(([gx, gz], idx) => (
            <mesh key={`shard_${idx}`} position={[gx, 0.015, gz]} rotation={[-Math.PI / 2, 0, idx * 1.1]}>
              <planeGeometry args={[0.05, 0.03]} />
              <meshStandardMaterial color="#e2e8f0" metalness={0.9} roughness={0.1} transparent opacity={0.85} />
            </mesh>
          ))}
        </group>
      )}

      {/* ============================================================ */}
      {/* 11. GODREJ 2-DOOR STEEL ALMIRAH (BURGLARY TARGET)            */}
      {/* ============================================================ */}
      {(type === "almirah" || type === "steel_almirah") && (
        <group>
          {/* Real Godrej 2-door steel wardrobe: 1.2m width x 1.95m height x 0.6m depth */}
          <GLBProp assetPath="/assets/props/steel_almirah.glb" targetDimensions={{ x: 1.2, y: 1.95, z: 0.6 }} />
        </group>
      )}

      {/* ============================================================ */}
      {/* 12. MASTER BEDROOM DOUBLE BED                                */}
      {/* ============================================================ */}
      {(type === "bed" || type === "double_bed") && (
        <group>
          {/* Real double bed: 1.9m width x 0.85m height x 2.1m length */}
          <GLBProp assetPath="/assets/props/double_bed.glb" targetDimensions={{ x: 1.9, y: 0.85, z: 2.1 }} />
        </group>
      )}

      {/* ============================================================ */}
      {/* 13. INTERIOR ROOM DIVIDING PARTITION WALL                   */}
      {/* ============================================================ */}
      {type === "wall_partition" && (
        <group>
          {/* Architectural Cutaway Partition (1.6m height so detective camera has unobstructed line of sight) */}
          <mesh position={[0, 0.8, 0]}>
            <boxGeometry args={[object.dimensions?.x || 0.15, 1.6, object.dimensions?.z || 4.0]} />
            <meshStandardMaterial color="#2d3748" roughness={0.8} metalness={0.1} />
          </mesh>
          {/* Baseboard trim */}
          <mesh position={[0, 0.05, 0]} material={darkWoodMaterial}>
            <boxGeometry args={[(object.dimensions?.x || 0.15) + 0.02, 0.1, object.dimensions?.z || 4.0]} />
          </mesh>
        </group>
      )}
    </group>
  );
}

import React, { useMemo } from "react";
import * as THREE from "three";

/**
 * Procedural Ballistic Debris & Spark Spall Particle Emitter.
 * Generates dynamic high-velocity kinetic sparks and glass/polycarbonate shards upon collision.
 */
export default function CollisionParticles({
  position = [0, 0.4, 0],
  currentTime = 0,
  impactTime = 5.0,
}) {
  const dt = currentTime - impactTime;

  // Render particles only after impact moment (5.0s to 10.0s)
  const isPostImpact = dt >= 0;

  // Generate 45 deterministic pseudo-random particle trajectories based on ballistic math
  const particles = useMemo(() => {
    const list = [];
    const count = 45;

    for (let i = 0; i < count; i++) {
      // Deterministic pseudo-random seed
      const seed = Math.sin(i * 997.3) * 10000;
      const rand1 = seed - Math.floor(seed);
      const seed2 = Math.cos(i * 787.1) * 10000;
      const rand2 = seed2 - Math.floor(seed2);
      const seed3 = Math.sin(i * 311.9) * 10000;
      const rand3 = seed3 - Math.floor(seed3);

      const angle = rand1 * Math.PI * 2;
      const speedH = 1.5 + rand2 * 5.5; // Horizontal velocity (1.5 - 7.0 m/s)
      const speedY = 1.0 + rand3 * 4.2; // Vertical launch velocity (1.0 - 5.2 m/s)

      const isSpark = i % 3 === 0; // 1/3 sparks, 2/3 glass shards
      const size = isSpark ? 0.035 : 0.05 + rand1 * 0.06;

      list.push({
        id: i,
        vx: Math.cos(angle) * speedH,
        vy: speedY,
        vz: Math.sin(angle) * speedH,
        isSpark,
        size,
        bounceRestitution: 0.28,
        settleTime: 1.2 + rand2 * 0.8,
      });
    }
    return list;
  }, []);

  if (!isPostImpact) return null;

  const sparkMaterial = new THREE.MeshBasicMaterial({
    color: "#ffaa00",
    transparent: true,
  });

  const glassMaterial = new THREE.MeshStandardMaterial({
    color: "#a0e0ff",
    roughness: 0.1,
    metalness: 0.9,
    transparent: true,
    opacity: 0.85,
  });

  return (
    <group position={position}>
      {particles.map((p) => {
        // Closed-form ballistic physics with gravity (g = 9.8 m/s^2)
        const g = 9.8;
        const flightTime = Math.min(dt, p.settleTime);

        // Horizontal displacement
        const px = p.vx * flightTime;
        const pz = p.vz * flightTime;

        // Vertical displacement with parabolic gravity arc
        let py = p.vy * flightTime - 0.5 * g * flightTime * flightTime;
        
        // Ground bounce clamp
        if (py < -0.38) {
          py = -0.38; // Rests on road surface
        }

        // Particle fading for sparks
        const sparkOpacity = p.isSpark ? Math.max(0, 1 - dt / 1.5) : 1.0;
        if (p.isSpark && sparkOpacity <= 0.05) return null;

        return (
          <mesh
            key={p.id}
            position={[px, py, pz]}
            rotation={[dt * p.vx * 3, dt * p.vy * 4, dt * p.vz * 2]}
          >
            {p.isSpark ? (
              <sphereGeometry args={[p.size, 8, 8]} />
            ) : (
              <boxGeometry args={[p.size, p.size * 0.3, p.size * 0.8]} />
            )}
            {p.isSpark ? (
              <meshBasicMaterial
                color={dt < 0.6 ? "#ffea75" : "#ff4400"}
                transparent
                opacity={sparkOpacity}
              />
            ) : (
              <primitive object={glassMaterial} attach="material" />
            )}
          </mesh>
        );
      })}
    </group>
  );
}

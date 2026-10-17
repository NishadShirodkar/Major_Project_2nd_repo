import React, { useRef, useEffect, Suspense, Component } from "react";
import { Canvas, useThree, useFrame } from "@react-three/fiber";
import { OrbitControls, Grid, Environment, ContactShadows } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette, ChromaticAberration, ToneMapping } from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import * as THREE from "three";

class CanvasErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("Three.js Canvas Error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <mesh position={[0, 1, 0]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshBasicMaterial color="red" />
        </mesh>
      );
    }
    return this.props.children;
  }
}

import VehicleModel from "./VehicleModel";
import PersonModel from "./PersonModel";
import Road from "./Road";
import RoomEnvironment from "./RoomEnvironment";
import EvidenceMarker from "./EvidenceMarker";
import TrajectoryPath from "./TrajectoryPath";
import ImpactWave from "./ImpactWave";
import EnvironmentObject from "./EnvironmentObject";
import TireSkidMarks from "./TireSkidMarks";
import CollisionParticles from "./CollisionParticles";

/**
 * High-Precision Camera Controller with:
 * 1. Manual OrbitControls (Tactical / Overhead / Impact Focus).
 * 2. 🎬 DIRECTOR (Cinematic Track): Dynamically tracks approaching vehicles, swoops into
 *    slow-motion bullet-time at impact (t=5.0s), and pulls out to forensic overhead rest view.
 * 3. High-frequency camera trauma micro-shake upon impact.
 */
function CameraController({ cameraPreset, isIndoor, currentTime = 0, sceneId = "" }) {
  const { camera } = useThree();
  const controlsRef = useRef();

  useFrame(() => {
    // 1. Cinematic Director Mode
    if (cameraPreset === "director") {
      if (controlsRef.current) {
        controlsRef.current.enabled = false;
      }

      const isBurglary = sceneId.includes("burglary");

      if (isBurglary) {
        // ========================================================
        // CASE 002: KAROL BAGH APARTMENT BURGLARY CINEMATIC CHOREOGRAPHY
        // ========================================================
        if (currentTime < 2.8) {
          // ACT 1 (t=0 - 2.8s): Entrance Breach
          // Low OTS (Over-The-Shoulder) camera positioned behind the corridor looking at door lock
          const t = currentTime / 2.8;
          camera.position.lerp(new THREE.Vector3(-4.8 + t * 0.4, 1.6, 4.4 - t * 0.8), 0.08);
          camera.lookAt(-4.2, 0.9, 2.5);
        } else if (currentTime < 5.8) {
          // ACT 2 (t=2.8 - 5.8s): Living Room Intrusion & Search
          // Smooth glide into living room, tracking suspect as he rummages coffee table and sofa
          const t = (currentTime - 2.8) / 3.0;
          camera.position.lerp(new THREE.Vector3(-3.2 + t * 1.5, 2.2, 3.2 - t * 1.6), 0.07);
          camera.lookAt(-1.2, 0.8, 0.6);
        } else if (currentTime < 8.4) {
          // ACT 3 (t=5.8 - 8.4s): The Almirah Heist (Climax)
          // Tight, dramatic investigative angle inside master bedroom focused on the Godrej almirah
          const t = (currentTime - 5.8) / 2.6;
          camera.position.lerp(new THREE.Vector3(1.2 + t * 0.6, 1.8, 0.4 - t * 1.2), 0.08);
          camera.lookAt(3.0, 1.2, -2.5);
        } else {
          // ACT 4 (t=8.4 - 10.0s): The Escape & Forensic Pan
          // Camera pulls back to high-angle master view, watching suspect flee through doorway and leaving evidence behind
          const t = (currentTime - 8.4) / 1.6;
          camera.position.lerp(new THREE.Vector3(0.0 - t * 2.5, 4.8 + t * 1.2, 4.2 + t * 1.8), 0.06);
          camera.lookAt(-1.0, 0.5, 0.8);
        }
      } else if (isIndoor) {
        // Indoor Shootout Camera Directing:
        // 0.0 - 4.8s: Low-angle tracking from behind shooter near entrance towards living room
        // 4.8 - 5.8s: Dramatic bullet-time close-up on victim and wall impact
        // 5.8 - 10.0s: Slow sweeping forensic investigative orbit
        if (currentTime < 4.8) {
          const t = currentTime / 4.8;
          camera.position.lerp(new THREE.Vector3(-3.2 + t * 1.2, 1.4, 1.8 - t * 0.5), 0.08);
          camera.lookAt(0.6, 1.1, -0.4);
        } else if (currentTime <= 5.8) {
          camera.position.lerp(new THREE.Vector3(1.1, 1.2, 0.9), 0.12);
          camera.lookAt(1.6, 0.8, -0.4);
        } else {
          const t = (currentTime - 5.8) / 4.2;
          const angle = t * Math.PI * 0.45;
          const radius = 5.2;
          camera.position.lerp(
            new THREE.Vector3(Math.sin(angle) * radius, 3.8 + t * 1.2, Math.cos(angle) * radius),
            0.05
          );
          camera.lookAt(0.2, 0.4, -0.3);
        }
      } else {
        // Outdoor Shankar Road Collision Camera Directing:
        if (currentTime < 4.5) {
          const t = currentTime / 4.5;
          const camX = -14.0 + t * 10.5;
          camera.position.lerp(new THREE.Vector3(camX, 2.2, -4.8), 0.08);
          camera.lookAt(camX + 3.0, 0.8, -1.2);
        } else if (currentTime <= 5.6) {
          camera.position.lerp(new THREE.Vector3(2.6, 1.6, 3.2), 0.14);
          camera.lookAt(-0.4, 0.5, 0);
        } else {
          const t = (currentTime - 5.6) / 4.4;
          camera.position.lerp(
            new THREE.Vector3(6.0 - t * 4.0, 11.0 + t * 6.0, 10.0 + t * 4.0),
            0.05
          );
          camera.lookAt(0, 0, 0);
        }
      }
    } else {
      // Manual Presets enable OrbitControls
      if (controlsRef.current) {
        controlsRef.current.enabled = true;
      }
    }

    // 2. Forensic Impact Micro-Jolt (Camera Shake ONLY for collision or gunshot scenes, disabled in burglary)
    if (!sceneId.includes("burglary") && currentTime >= 5.0 && currentTime <= 5.55) {
      const dt = currentTime - 5.0;
      const decay = Math.exp(-10 * dt);
      const shakeX = Math.sin(dt * 45) * 0.12 * decay;
      const shakeY = Math.cos(dt * 35) * 0.08 * decay;
      camera.position.x += shakeX * 0.04;
      camera.position.y += shakeY * 0.04;
    }
  });

  useEffect(() => {
    if (cameraPreset === "overhead") {
      camera.position.set(0, isIndoor ? 14 : 22, 0.1);
      if (controlsRef.current) {
        controlsRef.current.target.set(0, 0, 0);
        controlsRef.current.update();
      }
    } else if (cameraPreset === "impact") {
      camera.position.set(isIndoor ? 2.5 : 4, isIndoor ? 1.8 : 3, isIndoor ? 3 : 5);
      if (controlsRef.current) {
        controlsRef.current.target.set(0, 0, 0);
        controlsRef.current.update();
      }
    } else if (cameraPreset === "tactical") {
      camera.position.set(isIndoor ? 8 : 12, isIndoor ? 6 : 10, isIndoor ? 10 : 15);
      if (controlsRef.current) {
        controlsRef.current.target.set(0, 0, 0);
        controlsRef.current.update();
      }
    }
  }, [cameraPreset, camera, isIndoor]);

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.08}
      enableZoom={true}
      enablePan={true}
      enableRotate={true}
      minDistance={1.2}
      maxDistance={65}
      maxPolarAngle={Math.PI / 2 - 0.02}
    />
  );
}

export default function SceneCanvas({
  scene,
  currentTime = 0,
  selectedTargetId,
  setSelectedTargetId,
  cameraPreset = "director",
}) {
  const isIndoor = scene.metadata?.scene_type === "indoor_crime_scene" || !!scene.room;
  const roads = scene.roads || [];
  const vehicles = scene.vehicles || [];
  const people = scene.people || [];
  const evidence = scene.evidence || [];
  const environmentObjects = scene.environment_objects || [];
  const timeline = scene.timeline || [];
  const ballistics = scene.ballistics || [];

  return (
    <Canvas
      camera={{
        position: [isIndoor ? 8 : 12, isIndoor ? 6 : 10, isIndoor ? 10 : 15],
        fov: 45,
      }}
      gl={{
        antialias: true,
        toneMapping: THREE.ACESFilmicToneMapping,
        toneMappingExposure: 1.15,
      }}
      style={{
        width: "100%",
        height: "100%",
        background: "#04060c",
        touchAction: "none",
      }}
    >
      {/* Volumetric Tactical Fog */}
      <fog attach="fog" args={["#04060c", isIndoor ? 16 : 22, isIndoor ? 45 : 70]} />

      {/* High-Fidelity PBR Forensic Lighting */}
      <ambientLight intensity={0.8} />
      <directionalLight
        position={[18, 24, 12]}
        intensity={2.6}
        color="#e6f6ff"
        castShadow
      />
      <directionalLight
        position={[-12, 12, -12]}
        intensity={1.2}
        color="#00f0ff"
      />
      <directionalLight
        position={[0, -10, 0]}
        intensity={0.2}
        color="#152033"
      />

      <Environment preset="night" />

      {/* Forensic Blueprint Ground Grid */}
      <Grid
        position={[0, -0.015, 0]}
        args={[80, 80]}
        cellSize={1}
        cellColor="#0e1f30"
        sectionSize={5}
        sectionColor="#00d8f0"
        fadeDistance={isIndoor ? 35 : 55}
        fadeStrength={1.6}
      />

      {/* Realistic Soft Contact Shadows Under Vehicles (Outdoor only - prevents indoor floor shadow z-fighting) */}
      {!isIndoor && (
        <ContactShadows
          position={[0, 0.01, 0]}
          opacity={0.85}
          scale={36}
          blur={1.8}
          far={6.0}
          resolution={1024}
          color="#000308"
        />
      )}

      {/* 1. Render Indoor Room Environment if Indoor Case */}
      {isIndoor && scene.room && (
        <RoomEnvironment
          room={scene.room}
          ballistics={ballistics}
          currentTime={currentTime}
        />
      )}

      {/* 2. Render Outdoor Roads if Road Collision Case */}
      {!isIndoor && roads.map((road) => (
        <Road key={road.id} road={road} />
      ))}

      {/* 3. Render Holographic Trajectory Ribbons for Vehicles */}
      {vehicles.map((vehicle, idx) => (
        <TrajectoryPath
          key={`traj_${vehicle.id}`}
          entity={vehicle}
          timeline={timeline}
          color={idx === 0 ? "#00f0ff" : idx === 1 ? "#ffb700" : "#00ff88"}
          currentTime={currentTime}
        />
      ))}

      {/* 4. Render Holographic Trajectory Ribbons for Moving People */}
      {people.map((person, idx) => (
        <TrajectoryPath
          key={`traj_person_${person.id}`}
          entity={person}
          timeline={timeline}
          color="#ff0055"
          currentTime={currentTime}
        />
      ))}

      {/* 5. Render Forensic Tire Skid Marks & Chassis Gouge Marks (Outdoor only) */}
      {!isIndoor && <TireSkidMarks currentTime={currentTime} isIndoor={isIndoor} />}

      {/* 6. Dynamic Ballistic Spall, Glass Shards & Spark Explosion (Disabled for burglary) */}
      {!scene.metadata?.scene_id?.includes("burglary") && (
        <CollisionParticles
          position={isIndoor ? [0.6, 0.8, -0.6] : [-0.6, 0.4, 0]}
          currentTime={currentTime}
          impactTime={5.0}
        />
      )}

      {/* 7. Render Collision Epicenter & Shockwave Beacon (Outdoor only) */}
      {!isIndoor && <ImpactWave position={[0, 0.04, 0]} currentTime={currentTime} />}

      {/* 8. Render Vehicles Dynamically */}
      {vehicles.map((vehicle) => (
        <VehicleModel
          key={vehicle.id}
          vehicle={vehicle}
          timeline={timeline}
          currentTime={currentTime}
          isSelected={selectedTargetId === vehicle.id}
          onSelect={(id) => setSelectedTargetId(id)}
        />
      ))}

      {/* 9. Render Standalone People / Pedestrians / Suspects / Victims */}
      {people.map((person) => (
        <PersonModel
          key={person.id}
          person={person}
          timeline={timeline}
          currentTime={currentTime}
          isSelected={selectedTargetId === person.id}
          onSelect={(id) => setSelectedTargetId(id)}
        />
      ))}

      {/* 10. Render Forensic Environment Objects (Furniture, Breached Doors, Buildings, Sidewalks, Lamps) */}
      <Suspense fallback={null}>
        {environmentObjects.map((obj) => (
          <EnvironmentObject key={obj.id} object={obj} currentTime={currentTime} />
        ))}
      </Suspense>

      {/* 11. Render Forensic Evidence Markers */}
      <Suspense fallback={null}>
        {evidence.map((ev) => (
          <EvidenceMarker
            key={ev.id}
            evidence={ev}
            currentTime={currentTime}
            isSelected={selectedTargetId === ev.id}
            onSelect={(id) => setSelectedTargetId(id)}
          />
        ))}
      </Suspense>

      {/* Post-Processing Effects Pipeline */}
      <EffectComposer disableNormalPass multisampling={4}>
        {/* Subtle cinematic bloom for lasers, streetlights, and headlights */}
        <Bloom
          luminanceThreshold={0.55}
          luminanceSmoothing={0.35}
          intensity={0.65}
          kernelSize={3}
        />
        {/* Cinematic lens vignette */}
        <Vignette
          offset={0.25}
          darkness={0.7}
          blendFunction={BlendFunction.NORMAL}
        />
        {/* Subtle chromatic lens aberration during impact moments */}
        {currentTime >= 4.9 && currentTime <= 5.6 && (
          <ChromaticAberration
            offset={[0.003, 0.002]}
            blendFunction={BlendFunction.NORMAL}
          />
        )}
      </EffectComposer>

      {/* Camera Preset Manager & Controls with Director Mode */}
      <CameraController
        cameraPreset={cameraPreset}
        isIndoor={isIndoor}
        currentTime={currentTime}
        sceneId={scene.metadata?.scene_id || ""}
      />
    </Canvas>
  );
}
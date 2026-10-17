import React, { useState, useEffect, useRef } from "react";
import SceneCanvas from "./SceneCanvas";
import ArkhamHUD from "./ArkhamHUD";
import { SCENARIO_REGISTRY, getScenario } from "./scenarios";

export default function SceneViewer({
  activeCaseId,
  initialCaseId,
  caseId,
  onReturnToWorkspace,
}) {
  const incomingCaseId = activeCaseId || initialCaseId || caseId;
  const initialScenario = getScenario(incomingCaseId);
  const [selectedCaseId, setSelectedCaseId] = useState(initialScenario.id);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [activeHypotheses, setActiveHypotheses] = useState({});
  const [selectedTargetId, setSelectedTargetId] = useState("vehicle_1");
  const [cameraPreset, setCameraPreset] = useState("director");

  const lastFrameTimeRef = useRef(performance.now());

  // Active Scene IR loaded dynamically from Scenario Registry
  const scene = getScenario(selectedCaseId)?.data || SCENARIO_REGISTRY.case_001_delhi_tpoint.data;

  // Reset target selection when switching cases
  const handleSelectCase = (targetCaseId) => {
    const sc = getScenario(targetCaseId);
    setSelectedCaseId(sc.id);
    setCurrentTime(0);
    const newScene = sc?.data;
    if (newScene) {
      if (newScene.vehicles && newScene.vehicles.length > 0) {
        setSelectedTargetId(newScene.vehicles[0].id);
      } else if (newScene.people && newScene.people.length > 0) {
        setSelectedTargetId(newScene.people[0].id);
      }
    }
  };

  // Synchronize when activeCaseId prop changes externally
  useEffect(() => {
    if (incomingCaseId) {
      const resolved = getScenario(incomingCaseId);
      if (resolved && resolved.id !== selectedCaseId) {
        handleSelectCase(resolved.id);
      }
    }
  }, [incomingCaseId]);

  // High-precision animation clock loop
  useEffect(() => {
    let animationFrameId;

    const tick = (now) => {
      const deltaSec = (now - lastFrameTimeRef.current) / 1000;
      lastFrameTimeRef.current = now;

      if (isPlaying) {
        setCurrentTime((prevTime) => {
          const nextTime = prevTime + deltaSec * playbackSpeed;
          if (nextTime >= 10.0) {
            return 0; // Loop seamlessly
          }
          return nextTime;
        });
      }

      animationFrameId = requestAnimationFrame(tick);
    };

    lastFrameTimeRef.current = performance.now();
    animationFrameId = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(animationFrameId);
  }, [isPlaying, playbackSpeed]);

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        background: "#05080f",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 3D Scene Viewport */}
      <SceneCanvas
        scene={scene}
        currentTime={currentTime}
        selectedTargetId={selectedTargetId}
        setSelectedTargetId={setSelectedTargetId}
        cameraPreset={cameraPreset}
      />

      {/* Arkham Detective Mode HUD Overlay */}
      <ArkhamHUD
        currentTime={currentTime}
        setCurrentTime={setCurrentTime}
        isPlaying={isPlaying}
        setIsPlaying={setIsPlaying}
        playbackSpeed={playbackSpeed}
        setPlaybackSpeed={setPlaybackSpeed}
        activeHypotheses={activeHypotheses}
        setActiveHypotheses={setActiveHypotheses}
        selectedTargetId={selectedTargetId}
        setSelectedTargetId={setSelectedTargetId}
        cameraPreset={cameraPreset}
        setCameraPreset={setCameraPreset}
        selectedCaseId={selectedCaseId}
        onSelectCase={handleSelectCase}
        scene={scene}
        onReturnToWorkspace={onReturnToWorkspace}
      />
    </div>
  );
}
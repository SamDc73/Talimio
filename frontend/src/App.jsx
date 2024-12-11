import React, { useRef } from "react"; // Add this import
import "@xyflow/react/dist/style.css";

import { Toaster } from "./components/toaster";
import { OnboardingFlow } from "./features/onboarding";
import RoadmapFlow from "./features/roadmap";
import SettingsMenu from "./components/settings-menu";
import { useAppState } from "./hooks/useAppState";

export default function App() {
  const { showOnboarding, currentRoadmapId, handleOnboardingComplete, handleResetOnboarding } = useAppState();
  const flowRef = useRef(null);

  console.log("App render:", { showOnboarding, currentRoadmapId });

  return (
    <div className="app-container">
      {showOnboarding ? (
        <OnboardingFlow isOpen={true} onComplete={handleOnboardingComplete} />
      ) : (
        <RoadmapFlow ref={flowRef} roadmapId={currentRoadmapId} onError={handleResetOnboarding} />
      )}
      <SettingsMenu onResetOnboarding={handleResetOnboarding} onResetFlow={() => flowRef.current?.resetFlow?.()} />
      <Toaster />
    </div>
  );
}

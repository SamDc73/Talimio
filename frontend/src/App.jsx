import React, { useRef } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import "@xyflow/react/dist/style.css";

import SettingsMenu from "./components/settings-menu";
import { Toaster } from "./components/toaster";
import { OnboardingFlow } from "./features/onboarding";
import RoadmapFlow from "./features/roadmap";
import { useAppState } from "./hooks/useAppState";

function RoadmapPage() {
  const { roadmapId } = useParams();
  const flowRef = useRef(null);
  const { handleResetOnboarding } = useAppState();

  if (!roadmapId) {
    // This case might not be strictly necessary if the route always provides one,
    // but good for robustness.
    console.warn("RoadmapPage rendered without roadmapId, redirecting.");
    return <Navigate to="/" replace />;
  }

  console.log("RoadmapPage render, roadmapId:", roadmapId);

  return (
    <>
      <RoadmapFlow ref={flowRef} roadmapId={roadmapId} onError={handleResetOnboarding} />
      {/* SettingsMenu moved to App level */}
    </>
  );
}

export default function App() {
  const { showOnboarding, currentRoadmapId, handleOnboardingComplete, handleResetOnboarding } = useAppState();
  const flowRef = useRef(null); // Keep ref for potential root-level actions if needed

  console.log("App render:", { showOnboarding, currentRoadmapId });

  // Render routes directly. Onboarding is handled within the root route.
  return (
    <div className="app-container">
      <Routes>
        {/* Route for displaying a specific roadmap */}
        <Route path="/roadmap/:roadmapId" element={<RoadmapPage />} />

        {/* Root route logic */}
        <Route
          path="/"
          element={
            showOnboarding ? (
              // If onboarding is needed (no roadmap in localStorage), show it.
              <OnboardingFlow isOpen={true} onComplete={handleOnboardingComplete} />
            ) : currentRoadmapId ? (
              // If onboarding is done and we have a stored ID, redirect to it.
              <Navigate to={`/roadmap/${currentRoadmapId}`} replace />
            ) : (
              // Fallback if onboarding is done but no ID is stored (should ideally not happen often)
              // Could redirect to onboarding again or show an error/selection page.
              <div>Error: No roadmap selected. Please reset.</div>
            )
          }
        />

        {/* Optional: Catch-all route for invalid paths */}
        <Route path="*" element={<div>404 - Page Not Found</div>} />
      </Routes>
      {/* Keep Toaster and SettingsMenu outside the Routes to be persistent */}
      <SettingsMenu onResetOnboarding={handleResetOnboarding} onResetFlow={() => flowRef.current?.resetFlow?.()} />
      <Toaster />
    </div>
  );
}

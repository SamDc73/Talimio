import React, { useRef } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import "@xyflow/react/dist/style.css";

import { Toaster } from "./components/toaster";
import { OnboardingFlow } from "./features/onboarding";
import RoadmapFlow from "./features/roadmap";
import { SidebarProvider } from "./features/roadmap/SidebarContext";
import Sidebar from "./features/roadmap/sidebar";
import { useOutlineData } from "./features/roadmap/useOutlineData";
import { useAppState } from "./hooks/useAppState";

function RoadmapPage() {
  const { roadmapId } = useParams();
  const flowRef = useRef(null);
  const { handleResetOnboarding } = useAppState();
  const { modules, isLoading } = useOutlineData(roadmapId);

  if (!roadmapId) {
    console.warn("RoadmapPage rendered without roadmapId, redirecting.");
    return <Navigate to="/" replace />;
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <SidebarProvider>
      <div className="h-screen">
        <RoadmapFlow ref={flowRef} roadmapId={roadmapId} onError={handleResetOnboarding} />
      </div>
    </SidebarProvider>
  );
}

export default function App() {
  const { showOnboarding, currentRoadmapId, handleOnboardingComplete } = useAppState();

  return (
    <div className="app-container">
      <Routes>
        <Route path="/roadmap/:roadmapId" element={<RoadmapPage />} />
        <Route
          path="/"
          element={
            showOnboarding ? (
              <OnboardingFlow isOpen={true} onComplete={handleOnboardingComplete} />
            ) : currentRoadmapId ? (
              <Navigate to={`/roadmap/${currentRoadmapId}`} replace />
            ) : (
              <div>No roadmap selected</div>
            )
          }
        />
      </Routes>
      <Toaster />
    </div>
  );
}

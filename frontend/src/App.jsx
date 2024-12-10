import { useRef } from "react";
import "@xyflow/react/dist/style.css";

import { Toaster } from "./components/toaster";
import { OnboardingFlow } from "./features/onboarding/index.jsx";
import RoadmapFlow from "./features/roadmap";
import SettingsMenu from "./components/settings-menu"; // Add this import
import { useToast } from "./hooks/use-toast";
import { useAppState } from "./hooks/useAppState";

export default function App() {
  const { showOnboarding, userPreferences, handleOnboardingComplete, handleResetOnboarding } = useAppState();

  const { toast } = useToast();
  const flowRef = useRef(null);

  const handleResetFlow = () => {
    if (flowRef.current?.resetFlow) {
      flowRef.current.resetFlow();
      toast({
        title: "Flow Reset",
        description: "The flow has been reset to its initial state.",
      });
    }
  };

  return (
    <div className="app-container">
      <RoadmapFlow ref={flowRef} />
      <OnboardingFlow isOpen={showOnboarding} onComplete={handleOnboardingComplete} />
      <SettingsMenu onResetOnboarding={handleResetOnboarding} onResetFlow={handleResetFlow} />
      <Toaster />
    </div>
  );
}

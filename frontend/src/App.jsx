import React, { useRef } from 'react';
import '@xyflow/react/dist/style.css';
import RoadmapFlow from './features/roadmap';
import { OnboardingFlow } from './features/onboarding/index.jsx';
import SettingsMenu from './components/settings-menu';
import { Toaster } from './components/toaster';
import { useToast } from './hooks/use-toast';
import { useAppState } from './hooks/useAppState';

export default function App() {
  const {
    showOnboarding,
    userPreferences,
    handleOnboardingComplete,
    handleResetOnboarding,
  } = useAppState();

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
      <SettingsMenu
        onResetOnboarding={handleResetOnboarding}
        onResetFlow={handleResetFlow}
      />
      <OnboardingFlow
        isOpen={showOnboarding}
        onComplete={handleOnboardingComplete}
      />
      <Toaster />
    </div>
  );
};

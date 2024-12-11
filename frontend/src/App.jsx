import React, { useRef } from "react";
import "@xyflow/react/dist/style.css";

import { Toaster } from "./components/toaster";
import { OnboardingFlow } from "./features/onboarding";
import RoadmapFlow from "./features/roadmap";
import SettingsMenu from "./components/settings-menu";
import { useAppState } from "./hooks/useAppState";

// Custom Error Boundary Component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <h2 className="text-lg font-semibold">Something went wrong</h2>
            <pre className="text-sm text-red-500">{this.state.error?.message}</pre>
            <button
              className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              onClick={() => this.setState({ hasError: false })}
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Main App Component
export default function App() {
  const { showOnboarding, userPreferences, currentRoadmapId, handleOnboardingComplete, handleResetOnboarding } =
    useAppState();

  const flowRef = useRef(null);

  return (
    <ErrorBoundary>
      <div className="app-container">
        {showOnboarding ? (
          <OnboardingFlow isOpen={true} onComplete={handleOnboardingComplete} />
        ) : (
          <RoadmapFlow ref={flowRef} roadmapId={currentRoadmapId} onError={handleResetOnboarding} />
        )}
        <SettingsMenu onResetOnboarding={handleResetOnboarding} onResetFlow={() => flowRef.current?.resetFlow?.()} />
        <Toaster />
      </div>
    </ErrorBoundary>
  );
}

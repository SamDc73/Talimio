import React, { useRef, useEffect } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import HomePage from "./features/home";
import "@xyflow/react/dist/style.css";

import {
	ChatSidebar,
	ChatSidebarProvider,
} from "./components/header/MainHeader";
import { Toaster } from "./components/toaster";
import { ThemeProvider } from "./contexts/ThemeContext";
import { BookViewer } from "./features/book-viewer";
// Sidebar import removed - now imported in individual components
import { OnboardingFlow } from "./features/onboarding";
import RoadmapFlow from "./features/roadmap";
import RoadmapPreviewPage from "./features/roadmap/RoadmapPreviewPage";
import { useOutlineData } from "./features/roadmap/outline/useOutlineData";
import { VideoViewer } from "./features/video-viewer";
import { useAppState } from "./hooks/useAppState";
import useAppStore from "./stores/useAppStore";

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
		return (
			<div className="flex items-center justify-center h-screen">
				Loading...
			</div>
		);
	}

	return (
		<div className="h-screen">
			<RoadmapFlow
				ref={flowRef}
				roadmapId={roadmapId}
				onError={handleResetOnboarding}
			/>
		</div>
	);
}

export default function App() {
	const { showOnboarding, currentRoadmapId, handleOnboardingComplete } =
		useAppState();
	const cleanupOldStorage = useAppStore((state) => state.cleanupOldStorage);

	// Clean up old localStorage on app startup
	useEffect(() => {
		cleanupOldStorage();
	}, [cleanupOldStorage]);

	return (
		<ThemeProvider>
			<ChatSidebarProvider>
				<div className="app-container">
					<Routes>
						<Route
							path="/roadmap/preview/:roadmapId"
							element={<RoadmapPreviewPage />}
						/>
						<Route path="/roadmap/:roadmapId" element={<RoadmapPage />} />
						<Route path="/books/:bookId" element={<BookViewer />} />
						<Route path="/videos/:videoId" element={<VideoViewer />} />
						<Route path="/" element={<HomePage />} />
					</Routes>
					<Toaster />
					<ChatSidebar />
				</div>
			</ChatSidebarProvider>
		</ThemeProvider>
	);
}

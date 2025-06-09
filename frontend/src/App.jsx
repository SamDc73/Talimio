import React, { useRef } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import HomePage from "./features/home";
import "@xyflow/react/dist/style.css";

import { CodeBlockTest } from "@/components/code-block-test";
import {
	ChatSidebar,
	ChatSidebarProvider,
} from "./components/header/MainHeader";
import { Toaster } from "./components/toaster";
import { ThemeProvider } from "./contexts/ThemeContext";
import { BookViewer } from "./features/book-viewer";
import { SidebarProvider } from "./features/navigation/SidebarContext";
// Sidebar import removed - now imported in individual components
import { OnboardingFlow } from "./features/onboarding";
import RoadmapFlow from "./features/roadmap";
import { useOutlineData } from "./features/roadmap/outline/useOutlineData";
import { VideoViewer } from "./features/video-viewer";
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
		return (
			<div className="flex items-center justify-center h-screen">
				Loading...
			</div>
		);
	}

	return (
		<SidebarProvider>
			<div className="h-screen">
				<RoadmapFlow
					ref={flowRef}
					roadmapId={roadmapId}
					onError={handleResetOnboarding}
				/>
			</div>
		</SidebarProvider>
	);
}

export default function App() {
	const { showOnboarding, currentRoadmapId, handleOnboardingComplete } =
		useAppState();

	return (
		<ThemeProvider>
			<ChatSidebarProvider>
				<div className="app-container">
					<Routes>
						<Route path="/roadmap/:roadmapId" element={<RoadmapPage />} />
						<Route path="/books/:bookId" element={<BookViewer />} />
						<Route path="/videos/:videoId" element={<VideoViewer />} />
						<Route path="/code-test" element={<CodeBlockTest />} />
						<Route path="/" element={<HomePage />} />
					</Routes>
					<Toaster />
					<ChatSidebar />
				</div>
			</ChatSidebarProvider>
		</ThemeProvider>
	);
}

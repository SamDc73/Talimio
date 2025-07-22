import { useEffect, useRef } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import HomePage from "./features/home";
import "@xyflow/react/dist/style.css";

import {
	ChatSidebar,
	ChatSidebarProvider,
} from "./components/header/MainHeader";
import ProtectedRoute from "./components/ProtectedRoute";
import { Toaster } from "./components/toaster";
import { TextSelectionProvider } from "./components/ui/GlobalTextSelectionTooltip";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import AuthPage from "./features/auth/AuthPage";
import { BookViewer } from "./features/book-viewer";
import { CourseLayout as RoadmapFlow } from "./features/course";
import RoadmapPreviewPage from "./features/roadmap/RoadmapPreviewPage";
import { VideoViewer } from "./features/video-viewer";
import { useAppState } from "./hooks/useAppState";
import useAppStore from "./stores/useAppStore";

function RoadmapPage() {
	const { roadmapId } = useParams();
	const flowRef = useRef(null);
	const { handleResetRoadmap } = useAppState();

	if (!roadmapId) {
		console.warn("RoadmapPage rendered without roadmapId, redirecting.");
		return <Navigate to="/" replace />;
	}

	return (
		<div className="h-screen">
			<RoadmapFlow
				ref={flowRef}
				roadmapId={roadmapId}
				onError={handleResetRoadmap}
			/>
		</div>
	);
}

// Create a separate component for the main app content
function AppContent() {
	const cleanupOldStorage = useAppStore((state) => state.cleanupOldStorage);
	const { isAuthenticated } = useAuth();

	// Clean up old localStorage on app startup
	useEffect(() => {
		cleanupOldStorage();
	}, [cleanupOldStorage]);

	return (
		<TextSelectionProvider>
			<ChatSidebarProvider>
				<div className="app-container">
					<Routes>
						{/* Auth route */}
						<Route
							path="/auth"
							element={
								isAuthenticated ? <Navigate to="/" replace /> : <AuthPage />
							}
						/>

						{/* Protected routes */}
						<Route
							path="/"
							element={
								<ProtectedRoute>
									<HomePage />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>

						{/* Legacy roadmap routes - maintained for backward compatibility */}
						<Route
							path="/roadmap/preview/:roadmapId"
							element={
								<ProtectedRoute>
									<RoadmapPreviewPage />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>
						<Route
							path="/roadmap/:roadmapId"
							element={
								<ProtectedRoute>
									<RoadmapPage />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>
						<Route
							path="/roadmap/:roadmapId/lesson/:lessonId"
							element={
								<ProtectedRoute>
									<RoadmapPage />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>

						{/* New course routes */}
						<Route
							path="/course/preview/:roadmapId"
							element={
								<ProtectedRoute>
									<RoadmapPreviewPage />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>
						<Route
							path="/course/:roadmapId"
							element={
								<ProtectedRoute>
									<RoadmapPage />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>
						<Route
							path="/course/:roadmapId/lesson/:lessonId"
							element={
								<ProtectedRoute>
									<RoadmapPage />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>

						{/* Other content routes */}
						<Route
							path="/books/:bookId"
							element={
								<ProtectedRoute>
									<BookViewer />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>
						<Route
							path="/videos/:videoId"
							element={
								<ProtectedRoute>
									<VideoViewer />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>
					</Routes>
					<Toaster />
				</div>
			</ChatSidebarProvider>
		</TextSelectionProvider>
	);
}

export default function App() {
	return (
		<ThemeProvider>
			<AuthProvider>
				<AppContent />
			</AuthProvider>
		</ThemeProvider>
	);
}

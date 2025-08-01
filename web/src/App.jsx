import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import {
	ChatSidebar,
	ChatSidebarProvider,
} from "./components/header/MainHeader";
import ProtectedRoute from "./components/ProtectedRoute";
import { Toaster } from "./components/toaster";
import { TooltipProvider } from "./components/tooltip";
import { TextSelectionProvider } from "./components/ui/GlobalTextSelectionTooltip";
import { AuthProvider } from "./contexts/AuthContext";
import { ProgressProvider } from "./contexts/ProgressContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import AuthPage from "./features/auth/AuthPage";
import { BookViewer } from "./features/book-viewer";
import CoursePage from "./features/course/CoursePage";
import CoursePreviewPage from "./features/course/CoursePreviewPage";
import HomePage from "./features/home";
import LessonPage from "./features/lesson/LessonPage";
import RoadmapPage from "./features/roadmap";
import RoadmapPreviewPage from "./features/roadmap/RoadmapPreviewPage";
import { VideoViewer } from "./features/video-viewer";
import { useAuth } from "./hooks/useAuth";
import useAppStore from "./stores/useAppStore";

// Create a client instance
const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: 3,
			retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
			staleTime: 30 * 1000, // 30 seconds
			cacheTime: 10 * 60 * 1000, // 10 minutes
		},
	},
});

// Load auth test utilities in development
if (import.meta.env.VITE_DEBUG_MODE === "true") {
	import("./utils/authTest.js");
}

function RoadmapPageWrapper() {
	const { roadmapId } = useParams();

	if (!roadmapId) {
		console.warn("RoadmapPage rendered without roadmapId, redirecting.");
		return <Navigate to="/" replace />;
	}

	return <RoadmapPage roadmapId={roadmapId} />;
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
		<TooltipProvider>
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

							{/* Roadmap routes */}
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
								path="/roadmap/:roadmapId/lesson/:lessonId"
								element={
									<ProtectedRoute>
										<RoadmapPageWrapper />
										<ChatSidebar />
									</ProtectedRoute>
								}
							/>
							<Route
								path="/roadmap/:roadmapId"
								element={
									<ProtectedRoute>
										<RoadmapPageWrapper />
										<ChatSidebar />
									</ProtectedRoute>
								}
							/>

							{/* Course routes */}
							<Route
								path="/course/preview/:courseId"
								element={
									<ProtectedRoute>
										<CoursePreviewPage />
										<ChatSidebar />
									</ProtectedRoute>
								}
							/>
							<Route
								path="/course/:courseId/lesson/:lessonId"
								element={
									<ProtectedRoute>
										<CoursePage />
										<ChatSidebar />
									</ProtectedRoute>
								}
							/>
							<Route
								path="/course/:courseId"
								element={
									<ProtectedRoute>
										<CoursePage />
										<ChatSidebar />
									</ProtectedRoute>
								}
							/>

							{/* Lesson route */}
							<Route
								path="/lesson/:lessonId"
								element={
									<ProtectedRoute>
										<LessonPage />
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
		</TooltipProvider>
	);
}

export default function App() {
	return (
		<QueryClientProvider client={queryClient}>
			<ThemeProvider>
				<AuthProvider>
					<ProgressProvider>
						<AppContent />
					</ProgressProvider>
				</AuthProvider>
			</ThemeProvider>
		</QueryClientProvider>
	);
}

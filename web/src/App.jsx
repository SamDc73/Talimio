import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useEffect } from "react"
import { Navigate, Route, Routes, useParams } from "react-router-dom"
import CourseLayout from "./components/CourseLayout"
import { ChatSidebar, ChatSidebarProvider } from "./components/header/MainHeader"
import ProtectedRoute from "./components/ProtectedRoute"
import { Toaster } from "./components/toaster"
import { TooltipProvider } from "./components/tooltip"
import { TextSelectionProvider } from "./components/ui/GlobalTextSelectionTooltip"
import { AuthProvider } from "./contexts/AuthContext"
import { ProgressProvider } from "./contexts/ProgressContext"
import { ThemeProvider } from "./contexts/ThemeContext"
import AuthPage from "./features/auth/AuthPage"
import { BookViewer } from "./features/book-viewer"
import CoursePreviewPage from "./features/course/CoursePreviewPage"
import CourseView from "./features/course/CourseView"
import HomePage from "./features/home"
import RoadmapPage from "./features/roadmap"
import RoadmapPreviewPage from "./features/roadmap/RoadmapPreviewPage"
import { VideoViewer } from "./features/video-viewer"
import { useAuth } from "./hooks/useAuth"
import useAppStore from "./stores/useAppStore"

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
})

// Load auth test utilities in development
if (import.meta.env.VITE_DEBUG_MODE === "true") {
	import("./utils/authTest.js")
}

function RoadmapPageWrapper() {
	const { roadmapId } = useParams()

	if (!roadmapId) {
		return <Navigate to="/" replace />
	}

	return <RoadmapPage roadmapId={roadmapId} />
}

// Course routes wrapper - only loads when actually needed
function CourseRoutes() {
	const { courseId, lessonId } = useParams()

	return (
		<CourseView
			mode="outline" // This will be managed inside CourseLayout
			modules={[]} // This will be loaded inside CourseLayout
			roadmapId={courseId}
		/>
	)
}

// Create a separate component for the main app content
function AppContent() {
	const cleanupOldStorage = useAppStore((state) => state.cleanupOldStorage)
	const { isAuthenticated } = useAuth()

	// Clean up old localStorage on app startup (if function exists)
	useEffect(() => {
		if (cleanupOldStorage) {
			cleanupOldStorage()
		}
	}, [cleanupOldStorage])

	return (
		<TooltipProvider>
			<TextSelectionProvider>
				<ChatSidebarProvider>
					<Routes>
						{/* Auth route */}
						<Route path="/auth" element={isAuthenticated ? <Navigate to="/" replace /> : <AuthPage />} />

						{/* Course routes with persistent layout */}
						<Route
							path="/course/:courseId"
							element={
								<ProtectedRoute>
									<CourseLayout />
								</ProtectedRoute>
							}
						>
							{/* Nested routes that use the CourseLayout */}
							<Route index element={<CourseRoutes />} />
							<Route path="lesson/:lessonId" element={<CourseRoutes />} />
						</Route>

						{/* Standalone lesson route also uses CourseLayout */}
						<Route
							path="/lesson/:lessonId"
							element={
								<ProtectedRoute>
									<CourseLayout />
								</ProtectedRoute>
							}
						>
							<Route index element={<CourseRoutes />} />
						</Route>

						{/* Course preview - doesn't use persistent layout */}
						<Route
							path="/course/preview/:courseId"
							element={
								<ProtectedRoute>
									<CoursePreviewPage />
									<ChatSidebar />
								</ProtectedRoute>
							}
						/>

						{/* Home page */}
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
				</ChatSidebarProvider>
			</TextSelectionProvider>
		</TooltipProvider>
	)
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
	)
}

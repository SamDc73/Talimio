import { Navigate, Route, Routes } from "react-router-dom"
import ProtectedRoute from "@/components/ProtectedRoute"
import { TextSelectionTooltip } from "@/components/TextSelectionTooltip"
import { AuthProvider } from "@/contexts/AuthProvider.jsx"
import { ThemeProvider } from "@/contexts/ThemeContext"
import { ChatSidebarProvider } from "@/features/assistant/contexts/ChatSidebarContext"
import AuthPage from "@/features/auth/AuthPage"
import { BookViewer } from "@/features/book-viewer"
import CoursePage from "@/features/course/CoursePage"
import CoursePreviewPage from "@/features/course/CoursePreviewPage"
import HomePage from "@/features/home"
import LessonPage from "@/features/lesson/LessonPage"
import { VideoViewer } from "@/features/video-viewer"

function App() {
	return (
		<AuthProvider>
			<ThemeProvider>
				<ChatSidebarProvider>
					<Routes>
						{/* Public routes */}
						<Route path="/auth" element={<AuthPage />} />

						{/* Protected routes */}
						<Route
							path="/"
							element={
								<ProtectedRoute>
									<HomePage />
								</ProtectedRoute>
							}
						/>

						{/* Course routes */}
						<Route
							path="/course/:courseId"
							element={
								<ProtectedRoute>
									<CoursePage />
								</ProtectedRoute>
							}
						/>
						<Route
							path="/course/:courseId/lesson/:lessonId"
							element={
								<ProtectedRoute>
									<LessonPage />
								</ProtectedRoute>
							}
						/>
						<Route
							path="/course/preview/:courseId"
							element={
								<ProtectedRoute>
									<CoursePreviewPage />
								</ProtectedRoute>
							}
						/>

						{/* Content routes */}
						<Route
							path="/books/:bookId"
							element={
								<ProtectedRoute>
									<BookViewer />
								</ProtectedRoute>
							}
						/>
						<Route
							path="/videos/:videoId"
							element={
								<ProtectedRoute>
									<VideoViewer />
								</ProtectedRoute>
							}
						/>

						{/* Catch all - redirect to home */}
						<Route path="*" element={<Navigate to="/" replace />} />
					</Routes>
					{/* Global selection tooltip*/}
					<TextSelectionTooltip />
				</ChatSidebarProvider>
			</ThemeProvider>
		</AuthProvider>
	)
}

export default App

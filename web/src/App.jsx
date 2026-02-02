import { Navigate, Route, Routes } from "react-router-dom"
import ProtectedRoute from "@/components/ProtectedRoute"
import { TextSelectionTooltip } from "@/components/TextSelectionTooltip"
import { AuthProvider } from "@/contexts/AuthProvider.jsx"
import { ThemeProvider } from "@/contexts/ThemeContext"
import { ChatSidebarProvider } from "@/features/assistant/contexts/ChatSidebarContext"
import AuthPage from "@/features/auth/AuthPage"
import BookViewer from "@/features/book-viewer/BookViewer"
import { CourseProvider } from "@/features/course/CourseContext.jsx"
import CourseLayout from "@/features/course/components/CourseLayout.jsx"
import DocumentsView from "@/features/course/views/DocumentsView.jsx"
import LessonContent from "@/features/course/views/LessonContent.jsx"
import OutlineView from "@/features/course/views/OutlineView.jsx"
import TrackView from "@/features/course/views/TrackView.jsx"
import HomePage from "@/features/home"
import { VideoViewer } from "@/features/video-viewer/VideoViewer"

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

						{/* Course routes (nested layout) */}
						<Route
							path="/course/:courseId/*"
							element={
								<ProtectedRoute>
									<CourseProvider>
										<CourseLayout />
									</CourseProvider>
								</ProtectedRoute>
							}
						>
							<Route index element={<OutlineView />} />
							<Route path="track" element={<TrackView />} />
							<Route path="documents" element={<DocumentsView />} />
							<Route path="lesson/:lessonId" element={<LessonContent />} />
							{/* Fallback: unknown nested path redirects to outline */}
							<Route path="*" element={<Navigate to="." replace />} />
						</Route>

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

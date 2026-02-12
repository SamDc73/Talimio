import { Navigate, Route, Routes } from "react-router-dom"
import ProtectedRoute from "@/components/ProtectedRoute"
import { TextSelectionTooltip } from "@/components/TextSelectionTooltip"
import { AuthProvider } from "@/contexts/AuthProvider"
import { ThemeProvider } from "@/contexts/ThemeContext"
import { ChatSidebarProvider } from "@/features/assistant/contexts/ChatSidebarProvider"
import AuthPage from "@/features/auth/AuthPage"
import ResetPasswordPage from "@/features/auth/ResetPasswordPage"
import VerifyEmailPage from "@/features/auth/VerifyEmailPage"
import BookViewer from "@/features/book-viewer/BookViewer"
import { CourseProvider } from "@/features/course/CourseContext"
import CourseLayout from "@/features/course/components/CourseLayout"
import DocumentsView from "@/features/course/views/DocumentsView"
import LessonContent from "@/features/course/views/LessonContent"
import OutlineView from "@/features/course/views/OutlineView"
import PracticeView from "@/features/course/views/PracticeView"
import TrackView from "@/features/course/views/TrackView"
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
						<Route path="/reset-password" element={<ResetPasswordPage />} />
						<Route path="/verify-email" element={<VerifyEmailPage />} />

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
							<Route path="practice" element={<PracticeView />} />
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

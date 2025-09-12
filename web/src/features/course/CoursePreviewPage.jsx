import { motion } from "framer-motion"
import { ArrowLeft, BookOpen, RefreshCw, Save, Target } from "lucide-react"
import { useEffect, useState } from "react"
import { useLocation, useNavigate, useParams } from "react-router-dom"
import { Button } from "@/components/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/dialog"
import { Input } from "@/components/input"
import { Label } from "@/components/label"
import { api } from "@/lib/apiClient"

function CoursePreviewPage() {
	const { courseId } = useParams()
	const navigate = useNavigate()
	const location = useLocation()

	// Get state from navigation (for new courses)
	const isNew = location.state?.isNew || false
	const originalPrompt = location.state?.originalPrompt || ""

	// Loading and form states
	const [isLoading, setIsLoading] = useState(true)
	const [isSaving, setIsSaving] = useState(false)
	const [isRegenerating, setIsRegenerating] = useState(false)

	// Data states
	const [course, setCourse] = useState(null)
	const [formData, setFormData] = useState({
		title: "",
		description: "",
		tags: [],
	})

	// Load course data
	useEffect(() => {
		const loadCourse = async () => {
			try {
				setIsLoading(true)
				const response = await api.get(`/courses/${courseId}`)
				setCourse(response)

				// Parse tags from JSON string
				let tags = []
				try {
					tags = response.tags_json ? JSON.parse(response.tags_json) : []
				} catch (_e) {}

				setFormData({
					title: response.title,
					description: response.description,
					tags: tags,
				})
			} catch (_error) {
				console.log("Error")
			} finally {
				setIsLoading(false)
			}
		}

		if (courseId) {
			loadCourse()
		}
	}, [courseId])

	const handleSave = async () => {
		if (!formData.title.trim()) {
			console.log("Title Required")
			return
		}

		setIsSaving(true)

		try {
			await api.patch(`/courses/${courseId}`, {
				title: formData.title,
				description: formData.description,
			})

			console.log("Course Updated!")

			// Navigate to the course view
			navigate(`/course/${courseId}`)
		} catch (_error) {
			console.log("Save Failed")
		} finally {
			setIsSaving(false)
		}
	}

	const handleRegenerate = async () => {
		if (!originalPrompt) return

		setIsRegenerating(true)

		try {
			const response = await api.post("/courses", {
				userPrompt: originalPrompt,
			})

			console.log("Course Regenerated!")

			// Navigate to new course preview
			navigate(`/course/preview/${response.id}`, {
				state: {
					isNew: true,
					originalPrompt: originalPrompt,
				},
				replace: true,
			})
		} catch (_error) {
			console.log("Regeneration Failed")
		} finally {
			setIsRegenerating(false)
		}
	}

	// Loading state
	if (isLoading) {
		return (
			<Dialog open={true} onOpenChange={() => navigate("/")}>
				<DialogContent className="sm:max-w-4xl">
					<DialogHeader>
						<DialogTitle className="sr-only">Loading Course</DialogTitle>
						<DialogDescription className="sr-only">Please wait while we load your course details</DialogDescription>
					</DialogHeader>
					<div className="flex items-center justify-center py-12">
						<div className="text-center">
							<div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
							<p className="text-gray-100-foreground">Loading course...</p>
						</div>
					</div>
				</DialogContent>
			</Dialog>
		)
	}

	return (
		<Dialog open={true} onOpenChange={() => navigate("/")}>
			<DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto">
				<DialogHeader className="space-y-4">
					<DialogTitle className="flex items-center gap-3 text-2xl">
						<div className="p-2 bg-gradient-to-br from-cyan-500 to-teal-500 rounded-lg">
							<BookOpen className="h-6 w-6 text-white" />
						</div>
						{isNew ? "Review Your Course" : "Edit Course"}
					</DialogTitle>
					<DialogDescription className="text-gray-100-foreground text-sm">
						{isNew
							? "Review and customize your AI-generated learning course before getting started"
							: "Update your course details and settings"}
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-6">
					{/* Course Details Form */}
					<div className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="title" className="text-sm font-medium">
								Course Title
							</Label>
							<Input
								id="title"
								value={formData.title}
								onChange={(e) => setFormData({ ...formData, title: e.target.value })}
								placeholder="Enter course title"
								className="text-base"
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="description" className="text-sm font-medium">
								Description
							</Label>
							<textarea
								id="description"
								value={formData.description}
								onChange={(e) => setFormData({ ...formData, description: e.target.value })}
								placeholder="Describe what this course covers"
								rows={3}
								className="w-full px-4 py-3 text-sm border border-gray-300 bg-white rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-ring transition-all resize-none placeholder:text-gray-100-foreground/60"
							/>
						</div>
					</div>

					{/* Course Overview */}
					{course?.lessons && course.lessons.length > 0 && (
						<div className="space-y-3">
							<div className="flex items-center gap-2 text-sm font-medium">
								<Target className="h-4 w-4 text-cyan-500" />
								Learning Path Overview ({course.lessons.length} lessons)
							</div>
							<div className="bg-gray-100/30 rounded-lg p-4 space-y-2 max-h-48 overflow-y-auto">
								{course.lessons.map((lesson, index) => (
									<div key={lesson.id} className="flex items-start gap-3 text-sm">
										<div className="flex-shrink-0 w-6 h-6 bg-cyan-100 text-cyan-700 rounded-full flex items-center justify-center text-xs font-medium mt-0.5">
											{index + 1}
										</div>
										<div className="space-y-1">
											<div className="font-medium">{lesson.title}</div>
											<div className="text-gray-100-foreground text-xs leading-relaxed">{lesson.description}</div>
										</div>
									</div>
								))}
							</div>
						</div>
					)}

					{/* Action Buttons */}
					<div className="flex gap-3 pt-4 border-t">
						<Button variant="outline" onClick={() => navigate("/")} className="flex-1" disabled={isSaving}>
							<ArrowLeft className="h-4 w-4 mr-2" />
							Back to Dashboard
						</Button>

						{isNew && originalPrompt && (
							<Button variant="outline" onClick={handleRegenerate} disabled={isRegenerating} className="flex-1">
								<RefreshCw className={`h-4 w-4 mr-2 ${isRegenerating ? "animate-spin" : ""}`} />
								Regenerate
							</Button>
						)}

						<Button
							onClick={handleSave}
							disabled={isSaving}
							className="flex-1 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white"
						>
							{isSaving ? (
								<motion.div className="flex items-center gap-2" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
									<div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
									Saving...
								</motion.div>
							) : (
								<>
									<Save className="h-4 w-4 mr-2" />
									Save & Continue
								</>
							)}
						</Button>
					</div>
				</div>
			</DialogContent>
		</Dialog>
	)
}

export default CoursePreviewPage

import { motion } from "framer-motion"
import { ArrowLeft, BookOpen, RefreshCw, Save, Target } from "lucide-react"
import { useEffect, useState } from "react"
import { useLocation, useNavigate, useParams } from "react-router-dom"

import { Button } from "@/components/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/dialog"
import { Input } from "@/components/input"
import { Label } from "@/components/label"
import { toast } from "@/hooks/use-toast"
import { api } from "@/lib/apiClient"

function RoadmapPreviewPage() {
	const { roadmapId } = useParams()
	const navigate = useNavigate()
	const location = useLocation()

	// Get state from navigation (for new roadmaps)
	const isNew = location.state?.isNew || false
	const originalPrompt = location.state?.originalPrompt || ""

	// Loading and form states
	const [isLoading, setIsLoading] = useState(true)
	const [isSaving, setIsSaving] = useState(false)
	const [isRegenerating, setIsRegenerating] = useState(false)

	// Data states
	const [roadmap, setRoadmap] = useState(null)
	const [formData, setFormData] = useState({
		title: "",
		description: "",
		tags: [],
	})

	// Load roadmap data
	useEffect(() => {
		const loadRoadmap = async () => {
			try {
				setIsLoading(true)
				const response = await api.get(`/courses/${roadmapId}`)
				setRoadmap(response)

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
				toast({
					title: "Error",
					description: "Failed to load roadmap.",
					variant: "destructive",
				})
			} finally {
				setIsLoading(false)
			}
		}

		if (roadmapId) {
			loadRoadmap()
		}
	}, [roadmapId])

	const handleSave = async () => {
		if (!formData.title.trim()) {
			toast({
				title: "Title Required",
				description: "Please enter a title for your roadmap.",
				variant: "destructive",
			})
			return
		}

		setIsSaving(true)

		try {
			await api.patch(`/courses/${roadmapId}`, {
				title: formData.title,
				description: formData.description,
			})

			toast({
				title: "Roadmap Updated!",
				description: "Your roadmap has been saved successfully.",
			})

			// Navigate to the course view
			navigate(`/course/${roadmapId}`)
		} catch (_error) {
			toast({
				title: "Save Failed",
				description: "Failed to save roadmap. Please try again.",
				variant: "destructive",
			})
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

			toast({
				title: "Roadmap Regenerated!",
				description: "A new roadmap has been generated.",
			})

			// Navigate to new course preview
			navigate(`/course/preview/${response.id}`, {
				state: {
					isNew: true,
					originalPrompt: originalPrompt,
				},
				replace: true,
			})
		} catch (_error) {
			toast({
				title: "Regeneration Failed",
				description: "Failed to regenerate roadmap. Please try again.",
				variant: "destructive",
			})
		} finally {
			setIsRegenerating(false)
		}
	}

	// Loading state
	if (isLoading) {
		return (
			<div className="min-h-screen bg-white flex items-center justify-center">
				<div className="text-center">
					<div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
					<p className="text-gray-100-foreground">Loading roadmap...</p>
				</div>
			</div>
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
						{isNew ? "Review Your Roadmap" : "Edit Roadmap"}
					</DialogTitle>
					<DialogDescription className="text-gray-100-foreground text-sm">
						{isNew
							? "Review and customize your AI-generated learning roadmap before getting started"
							: "Update your roadmap details and settings"}
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-6">
					{/* Roadmap Details Form */}
					<div className="space-y-4">
						<div className="space-y-2">
							<Label for="title" className="text-sm font-medium">
								Roadmap Title
							</Label>
							<Input
								id="title"
								value={formData.title}
								onChange={(e) => setFormData({ ...formData, title: e.target.value })}
								placeholder="Enter roadmap title"
								className="text-base"
							/>
						</div>

						<div className="space-y-2">
							<Label for="description" className="text-sm font-medium">
								Description
							</Label>
							<textarea
								id="description"
								value={formData.description}
								onChange={(e) => setFormData({ ...formData, description: e.target.value })}
								placeholder="Describe what this roadmap covers"
								rows={3}
								className="w-full px-4 py-3 text-sm border border-gray-300 bg-white rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-ring transition-all resize-none placeholder:text-gray-100-foreground/60"
							/>
						</div>
					</div>

					{/* Course Overview */}
					{roadmap?.modules && roadmap.modules.length > 0 && (
						<div className="space-y-3">
							<div className="flex items-center gap-2 text-sm font-medium">
								<Target className="h-4 w-4 text-cyan-500" />
								Learning Path Overview ({roadmap.modules.length} modules)
							</div>
							<div className="bg-gray-100/30 rounded-lg p-4 space-y-2 max-h-48 overflow-y-auto">
								{roadmap.modules.map((module, index) => (
									<div key={module.id} className="flex items-start gap-3 text-sm">
										<div className="flex-shrink-0 w-6 h-6 bg-cyan-100 text-cyan-700 rounded-full flex items-center justify-center text-xs font-medium mt-0.5">
											{index + 1}
										</div>
										<div className="space-y-1">
											<div className="font-medium">{module.title}</div>
											<div className="text-gray-100-foreground text-xs leading-relaxed">{module.description}</div>
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

export default RoadmapPreviewPage

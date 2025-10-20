/**
 * Course Prompt Modal - Updated for unified course API
 *
 * This modal allows users to create new courses using AI generation
 * through the new unified course API structure.
 */

import { motion } from "framer-motion"
import { Sparkles } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/Dialog"
import { Label } from "@/components/Label"
import { cn } from "@/lib/utils"
import { useCourseNavigation } from "../../utils/navigationUtils"
import { useCourseService } from "./api/courseApi"

function CoursePromptModal({ isOpen, onClose, onSuccess, defaultPrompt = "" }) {
	const [prompt, setPrompt] = useState(defaultPrompt)
	const [isGenerating, setIsGenerating] = useState(false)
	const [error, setError] = useState("")

	const courseService = useCourseService()
	const { goToCourse } = useCourseNavigation()

	const resetForm = () => {
		setPrompt("")
		setError("")
	}

	const closeModal = () => {
		resetForm()
		onClose()
	}

	const handleSubmit = async (e) => {
		e.preventDefault()

		if (!prompt.trim()) {
			setError("Please describe what you'd like to learn")
			return
		}

		setIsGenerating(true)
		setError("")

		try {
			const response = await courseService.createCourse({
				prompt: prompt.trim(),
			})

			if (response?.id) {
				if (onSuccess) {
					onSuccess(response)
				}
				goToCourse(response.id)
				closeModal()
			} else {
				throw new Error("Failed to create course - no response data")
			}
		} catch (err) {
			setError(err.message || "Failed to create course. Please try again.")
		} finally {
			setIsGenerating(false)
		}
	}

	const handleOpenChange = (open) => {
		if (!open && !isGenerating) {
			closeModal()
		}
	}

	const examplePrompts = [
		"Learn React and build modern web apps",
		"Master Python for data science",
		"Get started with machine learning",
		"Learn JavaScript fundamentals",
	]

	return (
		<Dialog open={isOpen} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-[540px] gap-6">
				<DialogHeader className="space-y-3">
					<div className="flex items-center gap-3">
						<div className="p-2.5 bg-gradient-to-br from-[var(--color-course)]/90 to-[var(--color-course)] rounded-lg">
							<Sparkles className="h-5 w-5 text-white" />
						</div>
						<DialogTitle className="text-2xl">Create Course</DialogTitle>
					</div>
				</DialogHeader>

				<form onSubmit={handleSubmit} className="space-y-6">
					{/* Textarea Input */}
					<div className="space-y-3">
						<Label htmlFor="course-prompt" className="text-base">
							What would you like to learn?
						</Label>
						<textarea
							id="course-prompt"
							value={prompt}
							onChange={(e) => setPrompt(e.target.value)}
							placeholder="Describe what you want to learn..."
							disabled={isGenerating}
							className={cn(
								"w-full px-4 py-3 rounded-lg border border-border bg-background",
								"text-sm leading-relaxed resize-none",
								"focus:outline-none focus:ring-2 focus:ring-[var(--color-course)]/20 focus:border-[var(--color-course)]",
								"placeholder:text-muted-foreground/60",
								"transition-all duration-200",
								"disabled:opacity-50 disabled:cursor-not-allowed"
							)}
							rows={4}
							maxLength={500}
							autoFocus
						/>
						<div className="flex items-center justify-between text-xs">
							<span className="text-muted-foreground">Try one of the examples below</span>
							<span className="text-muted-foreground/70">{prompt.length}/500</span>
						</div>
					</div>

					{/* Example Prompts */}
					<div className="space-y-2.5">
						<div className="flex flex-wrap gap-2">
							{examplePrompts.map((example) => (
								<button
									key={example}
									type="button"
									onClick={() => setPrompt(example)}
									disabled={isGenerating}
									className={cn(
										"text-xs px-3.5 py-2 rounded-full",
										"bg-secondary/60 hover:bg-secondary text-secondary-foreground",
										"border border-border/40 hover:border-border",
										"transition-all duration-200",
										"disabled:opacity-50 disabled:cursor-not-allowed"
									)}
								>
									{example}
								</button>
							))}
						</div>
					</div>

					{/* Error Message */}
					{error && (
						<motion.div
							initial={{ opacity: 0, y: -10 }}
							animate={{ opacity: 1, y: 0 }}
							className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg"
						>
							<p className="text-sm text-destructive">{error}</p>
						</motion.div>
					)}

					{/* Actions */}
					<div className="flex justify-end gap-3 pt-2">
						<Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isGenerating}>
							Cancel
						</Button>
						<Button
							type="submit"
							disabled={isGenerating || !prompt.trim()}
							className="min-w-[140px] bg-[var(--color-course)] hover:bg-[var(--color-course)]/90 text-white"
						>
							{isGenerating ? (
								<motion.div className="flex items-center gap-2" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
									<motion.div
										className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
										animate={{ rotate: 360 }}
										transition={{ duration: 1, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
									/>
									<span>Creating...</span>
								</motion.div>
							) : (
								<div className="flex items-center gap-2">
									<Sparkles className="h-4 w-4" />
									<span>Create Course</span>
								</div>
							)}
						</Button>
					</div>
				</form>
			</DialogContent>
		</Dialog>
	)
}

export default CoursePromptModal

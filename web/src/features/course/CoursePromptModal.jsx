/**
 * Course Prompt Modal - Updated for unified course API
 *
 * This modal allows users to create new courses using AI generation
 * through the new unified course API structure.
 */

import { X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/Button"
import { useCourseNavigation } from "../../utils/navigationUtils"
import { useCourseService } from "./api/courseApi"

function CoursePromptModal({ isOpen, onClose, onSuccess, defaultPrompt = "" }) {
	const [prompt, setPrompt] = useState(defaultPrompt)
	const [isGenerating, setIsGenerating] = useState(false)
	const [error, setError] = useState("")

	const courseService = useCourseService()
	const { goToCoursePreview } = useCourseNavigation()

	const handleSubmit = async (e) => {
		e.preventDefault()

		if (!prompt.trim()) {
			setError("Please enter a description of what you want to learn")
			return
		}

		setIsGenerating(true)
		setError("")

		try {
			// Use the new unified course API
			const response = await courseService.createCourse({
				prompt: prompt.trim(),
			})

			if (response?.id) {
				// Course created successfully
				if (onSuccess) {
					onSuccess(response)
				}

				// Navigate to course preview for customization
				goToCoursePreview(response.id)
				onClose()
			} else {
				throw new Error("Failed to create course - no response data")
			}
		} catch (err) {
			setError(err.message || "Failed to create course. Please try again.")
		} finally {
			setIsGenerating(false)
		}
	}

	const handleClose = () => {
		if (!isGenerating) {
			setPrompt("")
			setError("")
			onClose()
		}
	}

	if (!isOpen) return null

	return (
		<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
			<div className="bg-white dark:bg-gray-800 rounded-lg max-w-lg w-full mx-4 shadow-xl">
				{/* Header */}
				<div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
					<h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Create New Course</h2>
					<button
						type="button"
						onClick={handleClose}
						disabled={isGenerating}
						className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors disabled:opacity-50"
					>
						<X className="h-6 w-6" />
					</button>
				</div>

				{/* Content */}
				<form onSubmit={handleSubmit} className="p-6">
					<div className="mb-4">
						<label htmlFor="course-prompt" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
							What would you like to learn?
						</label>
						<textarea
							id="course-prompt"
							value={prompt}
							onChange={(e) => setPrompt(e.target.value)}
							placeholder="Describe what you want to learn... (e.g., 'Learn React and build modern web applications')"
							disabled={isGenerating}
							className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-gray-100 resize-none disabled:opacity-50"
							rows={4}
							maxLength={500}
						/>
						<div className="text-right text-xs text-gray-500 mt-1">{prompt.length}/500 characters</div>
					</div>

					{/* Error Message */}
					{error && (
						<div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
							<p className="text-sm text-red-600 dark:text-red-400">{error}</p>
						</div>
					)}

					{/* Info */}
					<div className="mb-6 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md">
						<p className="text-sm text-blue-700 dark:text-blue-300">
							<strong>AI will create:</strong> A structured course with modules and lessons tailored to your learning
							goals. You'll be able to customize it before starting.
						</p>
					</div>

					{/* Actions */}
					<div className="flex justify-end space-x-3">
						<Button type="button" variant="outline" onClick={handleClose} disabled={isGenerating}>
							Cancel
						</Button>
						<Button type="submit" disabled={isGenerating || !prompt.trim()} className="min-w-[120px]">
							{isGenerating ? (
								<div className="flex items-center space-x-2">
									<div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
									<span>Creating...</span>
								</div>
							) : (
								"Create Course"
							)}
						</Button>
					</div>
				</form>
			</div>
		</div>
	)
}

export default CoursePromptModal

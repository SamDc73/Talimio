/**
 * Course Prompt Modal - Updated for unified course API with self-assessment flow
 */

import { AnimatePresence, motion } from "framer-motion"
import { HelpCircle, Loader2, Sparkles } from "lucide-react"
import { useMemo, useState } from "react"

import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/Dialog"
import { Label } from "@/components/Label"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/Tooltip"
import { cn } from "@/lib/utils"
import useAppStore, { selectSelfAssessmentEnabled, selectSetSelfAssessmentEnabled } from "@/stores/useAppStore"
import { useCourseNavigation } from "../../utils/navigationUtils"
import { useCourseService } from "./api/courseApi"
import SelfAssessmentDialog from "./SelfAssessmentDialog"

const MODAL_STEPS = {
	PROMPT: "prompt",
	SELF_ASSESSMENT: "selfAssessment",
}

const examplePrompts = [
	"Learn React and build modern web apps",
	"Master Python for data science",
	"Get started with machine learning",
	"Learn JavaScript fundamentals",
]

const tooltipCopy = "Answer a few quick questions to tailor your course. Optional."

function formatSelfAssessmentSummary(responses) {
	if (!responses?.length) {
		return ""
	}

	const lines = responses
		.map(({ question, answer }) => {
			const cleanQuestion = (question || "").replace(/\s+/g, " ").trim()
			const cleanAnswer = (answer || "").replace(/\s+/g, " ").trim()
			if (!cleanQuestion || !cleanAnswer) {
				return null
			}
			return `- Q: ${cleanQuestion}\n  A: ${cleanAnswer}`
		})
		.filter(Boolean)

	if (!lines.length) {
		return ""
	}

	return `Self-Assessment:\n${lines.join("\n")}`
}

function buildFinalPrompt(basePrompt, summaryBlock) {
	const trimmedPrompt = basePrompt.trim()
	if (!summaryBlock) {
		return trimmedPrompt
	}
	return `${trimmedPrompt}\n\n${summaryBlock}`
}

function CoursePromptModal({ isOpen, onClose, onSuccess, defaultPrompt = "" }) {
	const [prompt, setPrompt] = useState(defaultPrompt)
	const [activeStep, setActiveStep] = useState(MODAL_STEPS.PROMPT)
	const [isGenerating, setIsGenerating] = useState(false)
	const [error, setError] = useState("")

	const courseService = useCourseService()
	const { goToCourse } = useCourseNavigation()

	const selfAssessmentEnabled = useAppStore(selectSelfAssessmentEnabled) ?? false
	const setSelfAssessmentEnabled = useAppStore(selectSetSelfAssessmentEnabled)

	const shouldRunSelfAssessment = useMemo(() => {
		return selfAssessmentEnabled
	}, [selfAssessmentEnabled])

	const resetForm = () => {
		setPrompt("")
		setError("")
		setActiveStep(MODAL_STEPS.PROMPT)
	}

	const closeModal = (force = false) => {
		if (!force && isGenerating) {
			return
		}
		resetForm()
		onClose()
	}

	const handleOpenChange = (open) => {
		if (!open) {
			closeModal()
		}
	}

	const handleToggleSelfAssessment = (event) => {
		const { checked } = event.target
		setSelfAssessmentEnabled(checked)
	}

	const handlePromptSubmit = async (event) => {
		event.preventDefault()

		const trimmedPrompt = prompt.trim()
		if (!trimmedPrompt) {
			setError("Please describe what you'd like to learn")
			return
		}

		if (shouldRunSelfAssessment) {
			setError("")
			setActiveStep(MODAL_STEPS.SELF_ASSESSMENT)
			return
		}

		await createCourseWithSummary([])
	}

	const handleSelfAssessmentComplete = async (responses) => {
		await createCourseWithSummary(responses)
	}

	const handleSkipAll = async () => {
		await createCourseWithSummary([])
	}

	const createCourseWithSummary = async (responses) => {
		const trimmedPrompt = prompt.trim()
		if (!trimmedPrompt) {
			setError("Please describe what you'd like to learn")
			setActiveStep(MODAL_STEPS.PROMPT)
			return
		}

		const summaryBlock = formatSelfAssessmentSummary(responses)
		const finalPrompt = buildFinalPrompt(trimmedPrompt, summaryBlock)

		setIsGenerating(true)
		setError("")

		try {
			const response = await courseService.createCourse({ prompt: finalPrompt })

			if (response?.id) {
				if (onSuccess) {
					onSuccess(response)
				}
				goToCourse(response.id)
				closeModal(true)
				return
			}

			throw new Error("Failed to create course - no response data")
		} catch (creationError) {
			const fallbackMessage = creationError?.message || "Failed to create course. Please try again."
			setError(fallbackMessage)
			setActiveStep(MODAL_STEPS.PROMPT)
		} finally {
			setIsGenerating(false)
		}
	}

	const promptStepContent = (
		<motion.div
			key="prompt-step"
			initial={{ opacity: 0, x: 16 }}
			animate={{ opacity: 1, x: 0 }}
			exit={{ opacity: 0, x: -16 }}
			transition={{ duration: 0.2 }}
			className="space-y-6"
		>
			<DialogHeader className="space-y-3">
				<div className="flex items-center gap-3">
					<div className="p-2.5 bg-gradient-to-br from-[var(--color-course)]/90 to-[var(--color-course)] rounded-lg">
						<Sparkles className="h-5 w-5 text-white" />
					</div>
					<DialogTitle className="text-2xl">Create Course</DialogTitle>
				</div>
			</DialogHeader>

			<form onSubmit={handlePromptSubmit} className="space-y-6">
				<div className="space-y-3">
					<Label htmlFor="course-prompt" className="text-base">
						What would you like to learn?
					</Label>
					<textarea
						id="course-prompt"
						value={prompt}
						onChange={(event) => setPrompt(event.target.value)}
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
					/>
					<div className="flex items-center justify-between text-xs">
						<span className="text-muted-foreground">Try one of the examples below</span>
						<span className="text-muted-foreground/70">{prompt.length}/500</span>
					</div>
				</div>

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

				<label
					htmlFor="enable-self-assessment"
					className={cn(
						"flex items-center gap-2.5 px-1 py-0.5 -mx-1 rounded-md",
						"transition-colors duration-150",
						"cursor-pointer hover:bg-muted/40",
						isGenerating && "opacity-50 cursor-not-allowed"
					)}
				>
					<input
						type="checkbox"
						id="enable-self-assessment"
						checked={selfAssessmentEnabled}
						onChange={handleToggleSelfAssessment}
						disabled={isGenerating}
						className="h-4 w-4 rounded border-border text-[var(--color-course)] focus:ring-2 focus:ring-[var(--color-course)]/20 focus:ring-offset-0 transition-all"
					/>
					<span className="text-sm text-foreground select-none">Self-assessment</span>
					<Tooltip>
						<TooltipTrigger asChild>
							<button
								type="button"
								onClick={(e) => e.preventDefault()}
								disabled={isGenerating}
								className="ml-0.5 text-muted-foreground/60 hover:text-muted-foreground transition-colors"
								aria-label="Self-assessment information"
							>
								<HelpCircle className="h-3.5 w-3.5" />
							</button>
						</TooltipTrigger>
						<TooltipContent side="top" className="text-xs">
							{tooltipCopy}
						</TooltipContent>
					</Tooltip>
				</label>

				{error ? (
					<div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
						<p className="text-sm text-destructive">{error}</p>
					</div>
				) : null}

				<div className="flex justify-end gap-3 pt-2">
					<Button type="button" variant="outline" onClick={closeModal} disabled={isGenerating}>
						Cancel
					</Button>
					<Button
						type="submit"
						disabled={isGenerating || !prompt.trim()}
						className="min-w-[140px] bg-[var(--color-course)] hover:bg-[var(--color-course)]/90 text-white"
					>
						{isGenerating ? (
							<div className="flex items-center gap-2">
								<Loader2 className="h-4 w-4 animate-spin" />
								<span>Creating…</span>
							</div>
						) : (
							<div className="flex items-center gap-2">
								<Sparkles className="h-4 w-4" />
								<span>Continue</span>
							</div>
						)}
					</Button>
				</div>
			</form>
		</motion.div>
	)

	const selfAssessmentStep = (
		<motion.div
			key="self-assessment-step"
			initial={{ opacity: 0, x: 16 }}
			animate={{ opacity: 1, x: 0 }}
			exit={{ opacity: 0, x: -16 }}
			transition={{ duration: 0.2 }}
			className="space-y-6"
		>
			<SelfAssessmentDialog
				topic={prompt.trim()}
				level={null}
				onBack={() => setActiveStep(MODAL_STEPS.PROMPT)}
				onSkipAll={handleSkipAll}
				onComplete={handleSelfAssessmentComplete}
				isSubmitting={isGenerating}
			/>
		</motion.div>
	)

	return (
		<Dialog open={isOpen} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-[580px] gap-6">
				<AnimatePresence mode="wait">
					{activeStep === MODAL_STEPS.PROMPT ? promptStepContent : selfAssessmentStep}
				</AnimatePresence>
			</DialogContent>
		</Dialog>
	)
}

export default CoursePromptModal

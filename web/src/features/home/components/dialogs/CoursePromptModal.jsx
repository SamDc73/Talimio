/**
 * Course Prompt Modal - Updated for unified course API with self-assessment flow
 */

import { AnimatePresence, motion } from "framer-motion"
import { FileText, HelpCircle, Image, Loader2, Paperclip, Sparkles, X } from "lucide-react"
import { useRef, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/Dialog"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/Tooltip"
import { cn } from "@/lib/utils"
import useAppStore, { selectSelfAssessmentEnabled, selectSetSelfAssessmentEnabled } from "@/stores/useAppStore"
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

const ACCEPTED_ATTACHMENT_EXTENSIONS = [".pdf", ".epub", ".png", ".jpg", ".jpeg"]
const ACCEPTED_ATTACHMENT_ACCEPT_ATTR = ACCEPTED_ATTACHMENT_EXTENSIONS.join(",")
const ACCEPTED_ATTACHMENT_MIME_TYPES = {
	"application/pdf": ".pdf",
	"application/epub+zip": ".epub",
	"image/png": ".png",
	"image/jpeg": ".jpg",
}

function buildPastedFileName(extension) {
	const isoTimestamp = new Date().toISOString().replace(/[:.]/g, "-")
	return `pasted-${isoTimestamp}${extension}`
}

function buildAttachmentId(file, sequence) {
	const fileIdentity = `${file.name}-${file.size}-${file.lastModified}`
	if (globalThis.crypto?.randomUUID) {
		return `${fileIdentity}-${globalThis.crypto.randomUUID()}`
	}

	if (globalThis.crypto?.getRandomValues) {
		const values = new Uint32Array(1)
		globalThis.crypto.getRandomValues(values)
		return `${fileIdentity}-${values[0].toString(16)}`
	}

	return `${fileIdentity}-${Date.now()}-${sequence}`
}

function normalizeAttachmentFile(file) {
	if (!file) {
		return null
	}

	const fileName = (file.name || "").trim()
	const fileNameLower = fileName.toLowerCase()
	const nameHasAllowedExtension = ACCEPTED_ATTACHMENT_EXTENSIONS.some((ext) => fileNameLower.endsWith(ext))
	if (fileName && nameHasAllowedExtension) {
		return file
	}

	const mimeType = (file.type || "").toLowerCase()
	const extensionFromMimeType = ACCEPTED_ATTACHMENT_MIME_TYPES[mimeType]
	if (!extensionFromMimeType) {
		return file
	}

	let normalizedName = buildPastedFileName(extensionFromMimeType)
	if (fileName) {
		normalizedName = fileNameLower.endsWith(extensionFromMimeType) ? fileName : `${fileName}${extensionFromMimeType}`
	}

	try {
		const lastModified = typeof file.lastModified === "number" ? file.lastModified : Date.now()
		return new File([file], normalizedName, { type: file.type || undefined, lastModified })
	} catch {
		return file
	}
}

function isAllowedAttachment(file) {
	const fileName = file?.name?.toLowerCase?.() ?? ""
	const isAllowedByExtension = ACCEPTED_ATTACHMENT_EXTENSIONS.some((ext) => fileName.endsWith(ext))
	if (isAllowedByExtension) {
		return true
	}
	const mimeType = (file?.type || "").toLowerCase()
	return Boolean(ACCEPTED_ATTACHMENT_MIME_TYPES[mimeType])
}

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

	if (lines.length === 0) {
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

function CoursePromptModal({ isOpen, onClose, onSuccess, defaultPrompt = "", defaultAdaptiveEnabled = false }) {
	const [prompt, setPrompt] = useState(defaultPrompt)
	const [activeStep, setActiveStep] = useState(MODAL_STEPS.PROMPT)
	const [isGenerating, setIsGenerating] = useState(false)
	const [error, setError] = useState("")
	const [adaptiveEnabled, setAdaptiveEnabled] = useState(() => Boolean(defaultAdaptiveEnabled))
	const [attachments, setAttachments] = useState([])
	const [dragActive, setDragActive] = useState(false)
	const [isAddingAttachments, setIsAddingAttachments] = useState(false)
	const fileInputRef = useRef(null)
	const attachmentSequenceRef = useRef(0)

	const courseService = useCourseService()

	const selfAssessmentEnabled = useAppStore(selectSelfAssessmentEnabled) ?? false
	const setSelfAssessmentEnabled = useAppStore(selectSetSelfAssessmentEnabled)

	const resetForm = () => {
		setPrompt("")
		setError("")
		setAdaptiveEnabled(Boolean(defaultAdaptiveEnabled))
		setActiveStep(MODAL_STEPS.PROMPT)
		setAttachments([])
		setDragActive(false)
		if (fileInputRef.current) {
			fileInputRef.current.value = ""
		}
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

	const handleToggleAdaptive = (event) => {
		const { checked } = event.target
		setAdaptiveEnabled(checked)
	}

	const addAttachments = (files) => {
		const nextFiles = [...(files || [])].map((file) => normalizeAttachmentFile(file)).filter(Boolean)
		if (nextFiles.length === 0) {
			return
		}

		const invalidFiles = []
		const validFiles = []

		for (const file of nextFiles) {
			const isAllowed = isAllowedAttachment(file)
			if (isAllowed) {
				validFiles.push(file)
			} else {
				invalidFiles.push(file)
			}
		}

		if (invalidFiles.length > 0) {
			setError(`Unsupported files: ${invalidFiles.map((file) => file.name).join(", ")}`)
		} else {
			setError("")
		}

		if (validFiles.length === 0) {
			return
		}

		setAttachments((prev) => [
			...prev,
			...validFiles.map((file) => {
				attachmentSequenceRef.current += 1
				return {
					id: buildAttachmentId(file, attachmentSequenceRef.current),
					file,
				}
			}),
		])
	}

	const handleFileInputChange = (event) => {
		addAttachments(event.target.files)
		if (fileInputRef.current) {
			fileInputRef.current.value = ""
		}
	}

	const handleDrag = (event) => {
		event.preventDefault()
		event.stopPropagation()
		if (isGenerating) {
			return
		}
		if (event.type === "dragenter" || event.type === "dragover") {
			setDragActive(true)
		} else if (event.type === "dragleave") {
			setDragActive(false)
		}
	}

	const handleDrop = (event) => {
		event.preventDefault()
		event.stopPropagation()
		setDragActive(false)
		if (isGenerating) {
			return
		}
		addAttachments(event.dataTransfer?.files)
	}

	const removeAttachment = (attachmentId) => {
		if (isGenerating) {
			return
		}
		setAttachments((prev) => prev.filter((item) => item.id !== attachmentId))
	}

	const handlePaste = (event) => {
		if (isGenerating) {
			return
		}

		const clipboardData = event.clipboardData
		const clipboardFiles = clipboardData?.files ? [...clipboardData.files] : []

		const itemFiles = []
		const clipboardItems = clipboardData?.items ? [...clipboardData.items] : []
		for (const item of clipboardItems) {
			if (item?.kind !== "file") {
				continue
			}
			const file = item.getAsFile()
			if (file) {
				itemFiles.push(file)
			}
		}

		const nextFiles = clipboardFiles.length > 0 ? clipboardFiles : itemFiles
		if (nextFiles.length === 0) {
			return
		}

		event.preventDefault()
		setIsAddingAttachments(true)
		try {
			addAttachments(nextFiles)
		} finally {
			queueMicrotask(() => setIsAddingAttachments(false))
		}
	}

	const handlePromptSubmit = async (event) => {
		event.preventDefault()

		const trimmedPrompt = prompt.trim()
		if (!trimmedPrompt) {
			setError("Please describe what you'd like to learn")
			return
		}

		if (selfAssessmentEnabled) {
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
			const response = await courseService.createCourse({
				prompt: finalPrompt,
				adaptive_enabled: adaptiveEnabled,
				files: attachments.map((attachment) => attachment.file),
			})

			if (response?.id) {
				if (onSuccess) {
					onSuccess(response)
				}
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
			aria-busy={isGenerating}
			initial={{ opacity: 0, x: 16 }}
			animate={{ opacity: 1, x: 0 }}
			exit={{ opacity: 0, x: -16 }}
			transition={{ duration: 0.2 }}
			className="space-y-5"
		>
			<DialogHeader className="space-y-2">
				<div className="flex items-center gap-3">
					<div className="p-2.5 bg-linear-to-br from-(--color-course)/90 to-(--color-course) rounded-lg">
						<Sparkles className="size-5  text-white" />
					</div>
					<DialogTitle className="text-2xl">Create Course</DialogTitle>
				</div>
			</DialogHeader>

			<form onSubmit={handlePromptSubmit} onPaste={handlePaste} className="space-y-5">
				<div className="space-y-3">
					<Label htmlFor="course-prompt" className="text-base font-medium">
						What would you like to learn?
					</Label>
					<fieldset
						aria-label="Course prompt editor and file drop zone"
						className={cn(
							"relative flex flex-col rounded-xl border bg-background transition-all duration-200",
							"focus-within:border-(--color-course) focus-within:ring-4 focus-within:ring-(--color-course)/10",
							dragActive
								? "border-(--color-course) bg-(--color-course)/5 ring-4 ring-(--color-course)/10"
								: "border-border shadow-sm hover:border-muted-foreground/30"
						)}
						onDragEnter={handleDrag}
						onDragOver={handleDrag}
						onDragLeave={handleDrag}
						onDrop={handleDrop}
					>
						<textarea
							id="course-prompt"
							value={prompt}
							onChange={(event) => setPrompt(event.target.value)}
							placeholder="Describe what you want to learn..."
							disabled={isGenerating}
							className={cn(
								"w-full bg-transparent px-4 py-3 placeholder:text-muted-foreground/50",
								"text-sm/relaxed  resize-none focus:outline-none",
								"min-h-[120px]"
							)}
							rows={4}
							maxLength={500}
						/>

						<div className="flex items-end justify-between px-3 pb-3 pt-2 gap-2">
							<div className="flex items-center gap-2 flex-1 flex-wrap">
								<Input
									type="file"
									ref={fileInputRef}
									multiple
									accept={ACCEPTED_ATTACHMENT_ACCEPT_ATTR}
									onChange={handleFileInputChange}
									disabled={isGenerating}
									className="hidden"
								/>
								<Tooltip>
									<TooltipTrigger asChild>
										<button
											type="button"
											onClick={() => fileInputRef.current?.click()}
											disabled={isGenerating}
											className={cn(
												"inline-flex items-center justify-center rounded-lg p-2 text-muted-foreground transition-colors",
												"hover:bg-secondary hover:text-foreground",
												isAddingAttachments && "animate-pulse cursor-wait",
												isGenerating && "opacity-50 cursor-not-allowed"
											)}
										>
											<Paperclip className="size-4" />
											<span className="sr-only">Attach files</span>
										</button>
									</TooltipTrigger>
									<TooltipContent side="right" className="text-xs">
										Attach files ({ACCEPTED_ATTACHMENT_EXTENSIONS.join(", ")})
									</TooltipContent>
								</Tooltip>

								<AnimatePresence>
									{attachments.length > 0 && (
										<motion.div
											initial={{ opacity: 0, width: 0 }}
											animate={{ opacity: 1, width: "auto" }}
											exit={{ opacity: 0, width: 0 }}
											className="flex flex-wrap gap-2"
										>
											{attachments.map((attachment) => {
												const fileName = attachment.file?.name ?? "Untitled"
												const lowerName = fileName.toLowerCase()
												const isImage =
													lowerName.endsWith(".png") || lowerName.endsWith(".jpg") || lowerName.endsWith(".jpeg")

												return (
													<motion.div
														key={attachment.id}
														layout
														initial={{ scale: 0.8, opacity: 0 }}
														animate={{ scale: 1, opacity: 1 }}
														exit={{ scale: 0.8, opacity: 0 }}
														className="group flex items-center gap-2 rounded-md bg-secondary/50 px-2.5 py-1.5 text-xs font-medium text-secondary-foreground ring-1 ring-inset ring-black/5"
													>
														{isImage ? (
															<Image className="size-3.5 text-muted-foreground/70" />
														) : (
															<FileText className="size-3.5 text-muted-foreground/70" />
														)}
														<span className="truncate max-w-[100px]" title={fileName}>
															{fileName}
														</span>
														<button
															type="button"
															onClick={() => removeAttachment(attachment.id)}
															className="ml-1 text-muted-foreground/50 hover:text-destructive transition-colors"
														>
															<X className="size-3.5" />
														</button>
													</motion.div>
												)
											})}
										</motion.div>
									)}
								</AnimatePresence>

								{attachments.length === 0 && (
									<span className="text-xs text-muted-foreground/40 hidden sm:inline-block ml-1 select-none">
										Drag & drop files
									</span>
								)}
							</div>

							<div className="text-xs text-muted-foreground/40 font-mono select-none">{prompt.length}/500</div>
						</div>
					</fieldset>
				</div>

				<div className="space-y-2">
					<div className="flex flex-wrap gap-2">
						{examplePrompts.map((example) => (
							<button
								key={example}
								type="button"
								onClick={() => setPrompt(example)}
								disabled={isGenerating}
								className={cn(
									"text-xs px-3 py-1.5 rounded-full",
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

				<div className="space-y-2 py-2.5">
					<label
						htmlFor="enable-adaptive-mode"
						className={cn(
							"flex items-center gap-2.5 px-1 py-1.5 -mx-1 rounded-md",
							"transition-colors duration-150",
							"cursor-pointer hover:bg-muted/40",
							isGenerating && "opacity-50 cursor-not-allowed"
						)}
					>
						<input
							type="checkbox"
							id="enable-adaptive-mode"
							checked={adaptiveEnabled}
							onChange={handleToggleAdaptive}
							disabled={isGenerating}
							className="size-4  rounded-sm border-border text-(--color-course) focus:ring-2 focus:ring-(--color-course)/20 focus:ring-offset-0 transition-all"
						/>
						<span className="text-sm text-foreground select-none">Adaptive mode</span>
						<Tooltip>
							<TooltipTrigger asChild>
								<button
									type="button"
									onClick={(e) => e.preventDefault()}
									disabled={isGenerating}
									className="ml-0.5 text-muted-foreground/60 hover:text-muted-foreground transition-colors"
									aria-label="Adaptive mode information"
								>
									<HelpCircle className="size-3.5 " />
								</button>
							</TooltipTrigger>
							<TooltipContent side="top" className="text-xs">
								Enable spaced reviews and concept graphs tailored to each learner.
							</TooltipContent>
						</Tooltip>
					</label>

					<label
						htmlFor="enable-self-assessment"
						className={cn(
							"flex items-center gap-2.5 px-1 py-1.5 -mx-1 rounded-md",
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
							className="size-4  rounded-sm border-border text-(--color-course) focus:ring-2 focus:ring-(--color-course)/20 focus:ring-offset-0 transition-all"
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
									<HelpCircle className="size-3.5 " />
								</button>
							</TooltipTrigger>
							<TooltipContent side="top" className="text-xs">
								{tooltipCopy}
							</TooltipContent>
						</Tooltip>
					</label>
				</div>

				{error ? (
					<div className="p-2.5 bg-destructive/10 border border-destructive/20 rounded-lg">
						<p className="text-sm text-destructive">{error}</p>
					</div>
				) : null}

				<div className="flex justify-end gap-2.5 pt-2.5">
					<Button type="button" variant="outline" onClick={closeModal} disabled={isGenerating}>
						Cancel
					</Button>
					<Button
						type="submit"
						disabled={isGenerating || !prompt.trim()}
						className="min-w-[140px] bg-(--color-course) hover:bg-(--color-course)/90 text-white"
					>
						{isGenerating ? (
							<div className="flex items-center gap-2">
								<Loader2 className="size-4  animate-spin" />
								<span>Creating…</span>
							</div>
						) : (
							<div className="flex items-center gap-2">
								<Sparkles className="size-4 " />
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
			aria-busy={isGenerating}
			initial={{ opacity: 0, x: 16 }}
			animate={{ opacity: 1, x: 0 }}
			exit={{ opacity: 0, x: -16 }}
			transition={{ duration: 0.2 }}
			className="space-y-5"
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
			<DialogContent className="sm:max-w-[560px] gap-5">
				<div className="relative">
					{isGenerating ? (
						<div className="absolute inset-0 z-20 flex items-center justify-center rounded-lg bg-background/80 backdrop-blur-sm">
							<div className="flex flex-col items-center gap-3 text-muted-foreground">
								<Loader2 className="size-5  animate-spin" />
								<span className="text-sm">
									{attachments.length > 0 ? "Uploading attachments & generating course..." : "Generating course..."}
								</span>
							</div>
						</div>
					) : null}
					<AnimatePresence mode="wait">
						{activeStep === MODAL_STEPS.PROMPT ? promptStepContent : selfAssessmentStep}
					</AnimatePresence>
				</div>
			</DialogContent>
		</Dialog>
	)
}

export default CoursePromptModal

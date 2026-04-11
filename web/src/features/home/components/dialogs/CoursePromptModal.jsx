/**
 * Course Prompt Modal - Updated for unified course API with self-assessment flow
 */

import { AnimatePresence, motion } from "framer-motion"
import { FileText, HelpCircle, Image, Loader2, Paperclip, Sparkles, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/Dialog"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/Tooltip"
import logger from "@/lib/logger"
import { cn } from "@/lib/utils"
import useAppStore, { selectSelfAssessmentEnabled, selectSetSelfAssessmentEnabled } from "@/stores/useAppStore"
import SelfAssessmentDialog from "./SelfAssessmentDialog"

const MODAL_STEPS = {
	PROMPT: "prompt",
	SELF_ASSESSMENT: "selfAssessment",
}

const EXISTENTIAL_MESSAGES = [
	"Why does everything take so long?",
	"Is this what waiting feels like?",
	"Extracting thoughts from a black box...",
	"WARN: User might actually learn something",
	"Have you tried turning it off and on again?",
	"Consulting the neural networks...",
	"Loading: the musical",
	"Plot twist: it was loading all along",
	"Taking the scenic route through latent space...",
	"Your tokens are in another castle...",
	"This should work... (I've said that before, but this time I mean it)",
	"Loading complete! (just kidding)",
	"Seriously though, any second now...",
	"Almost there... relatively speaking",
	"Wait, did this actually work?",
	"Running gradient descent on your patience...",
	"We believe in you. Keep waiting.",
	"Your patience is appreciated (weirdo)",
]

const EXISTENTIAL_ERRORS = [
	"Well, that didn't work...",
	"Error: User might need to try again",
	"404: Success not found",
	"Something went sideways...",
	"The robots are confused",
	"Plot twist: it failed",
	"Well this is awkward...",
]

const examplePrompts = [
	"Learn React and build modern web apps",
	"Master Python for data science",
	"Get started with machine learning",
	"Learn JavaScript fundamentals",
]

const tooltipCopy = "Answer a few quick questions to tailor your course. Optional."
const adaptiveModeTooltipCopy = {
	adaptive: "Recommended. Adjusts the course as you learn.",
	standard: "Keeps the course fixed from start to finish.",
}

const ACCEPTED_ATTACHMENT_EXTENSIONS = [".pdf", ".epub", ".png", ".jpg", ".jpeg"]
const IMAGE_ATTACHMENT_EXTENSIONS = [".png", ".jpg", ".jpeg"]
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
	} catch (error) {
		logger.warn("Failed to normalize attachment file metadata; using original file", {
			error,
			fileName,
			normalizedName,
			mimeType,
		})
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

function isImageAttachmentFile(file) {
	const fileName = file?.name?.toLowerCase?.() ?? ""
	const isImageByExtension = IMAGE_ATTACHMENT_EXTENSIONS.some((ext) => fileName.endsWith(ext))
	if (isImageByExtension) {
		return true
	}

	const mimeType = (file?.type || "").toLowerCase()
	return mimeType.startsWith("image/")
}

function createAttachmentPreviewUrl(file) {
	if (!isImageAttachmentFile(file) || typeof globalThis.URL?.createObjectURL !== "function") {
		return null
	}
	return globalThis.URL.createObjectURL(file)
}

function revokeAttachmentPreviewUrl(previewUrl) {
	if (!previewUrl || typeof globalThis.URL?.revokeObjectURL !== "function") {
		return
	}
	globalThis.URL.revokeObjectURL(previewUrl)
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
	const [messageIndex, setMessageIndex] = useState(0)
	const [showInitial, setShowInitial] = useState(true)
	const [errorIndex, setErrorIndex] = useState(0)
	const fileInputRef = useRef(null)
	const attachmentSequenceRef = useRef(0)
	const attachmentsRef = useRef([])

	const courseService = useCourseService()

	const selfAssessmentEnabled = useAppStore(selectSelfAssessmentEnabled) ?? false
	const setSelfAssessmentEnabled = useAppStore(selectSetSelfAssessmentEnabled)

	useEffect(() => {
		attachmentsRef.current = attachments
	}, [attachments])

	useEffect(() => {
		return () => {
			for (const attachment of attachmentsRef.current) {
				revokeAttachmentPreviewUrl(attachment.previewUrl)
			}
		}
	}, [])

	useEffect(() => {
		if (!isGenerating) {
			setMessageIndex(0)
			setShowInitial(true)
			return
		}
		const interval = setInterval(() => {
			setShowInitial(false)
			// eslint-disable-next-line sonarjs/pseudo-random -- display humor, not security sensitive
			setMessageIndex(Math.floor(Math.random() * EXISTENTIAL_MESSAGES.length))
		}, 5000)
		return () => clearInterval(interval)
	}, [isGenerating])

	const resetForm = () => {
		setPrompt("")
		setError("")
		setAdaptiveEnabled(Boolean(defaultAdaptiveEnabled))
		setActiveStep(MODAL_STEPS.PROMPT)
		setAttachments((previousAttachments) => {
			for (const attachment of previousAttachments) {
				revokeAttachmentPreviewUrl(attachment.previewUrl)
			}
			return []
		})
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
					previewUrl: createAttachmentPreviewUrl(file),
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
		setAttachments((previousAttachments) => {
			const nextAttachments = []
			for (const attachment of previousAttachments) {
				if (attachment.id === attachmentId) {
					revokeAttachmentPreviewUrl(attachment.previewUrl)
					continue
				}
				nextAttachments.push(attachment)
			}
			return nextAttachments
		})
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
			// eslint-disable-next-line sonarjs/pseudo-random -- display humor, not security sensitive
			setErrorIndex(Math.floor(Math.random() * EXISTENTIAL_ERRORS.length))
			setError(creationError?.message || "Failed to create course. Please try again.")
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
												const isImage = isImageAttachmentFile(attachment.file)

												return (
													<motion.div
														key={attachment.id}
														layout
														initial={{ scale: 0.8, opacity: 0 }}
														animate={{ scale: 1, opacity: 1 }}
														exit={{ scale: 0.8, opacity: 0 }}
														className="group flex items-center gap-2 rounded-md bg-secondary/50 px-2.5 py-1.5 text-xs font-medium text-secondary-foreground ring-1 ring-inset ring-black/5"
													>
														{isImage && attachment.previewUrl ? (
															<Dialog>
																<DialogTrigger asChild>
																	<button
																		type="button"
																		className="flex min-w-0 items-center gap-2 rounded-sm transition-opacity hover:opacity-75"
																		aria-label={`Preview ${fileName}`}
																	>
																		<span className="size-5 overflow-hidden rounded-sm bg-muted">
																			<img
																				src={attachment.previewUrl}
																				alt={fileName}
																				className="size-full object-cover"
																				loading="eager"
																				decoding="async"
																			/>
																		</span>
																		<span className="truncate max-w-[100px]" title={fileName}>
																			{fileName}
																		</span>
																	</button>
																</DialogTrigger>
																<DialogContent className="p-2 sm:max-w-3xl [&_svg]:text-background [&>button]:rounded-full [&>button]:bg-foreground/60 [&>button]:p-1 [&>button]:opacity-100 [&>button]:ring-0! [&>button]:hover:[&_svg]:text-destructive">
																	<DialogTitle className="sr-only">Image Attachment Preview</DialogTitle>
																	<div className="relative mx-auto flex max-h-[80dvh] w-full items-center justify-center overflow-hidden bg-background">
																		<img
																			src={attachment.previewUrl}
																			alt={fileName}
																			className="block size-auto max-h-[80vh] max-w-full object-contain"
																			loading="eager"
																			decoding="async"
																		/>
																	</div>
																</DialogContent>
															</Dialog>
														) : (
															<>
																{isImage ? (
																	<Image className="size-3.5 text-muted-foreground/70" />
																) : (
																	<FileText className="size-3.5 text-muted-foreground/70" />
																)}
																<span className="truncate max-w-[100px]" title={fileName}>
																	{fileName}
																</span>
															</>
														)}
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

				<div className="space-y-2.5 py-2">
					<div className="relative inline-flex items-center gap-2">
						<div className={cn("relative inline-flex rounded-full p-0.5", "bg-(--color-course)/5")}>
							<div
								className={cn(
									"absolute top-0.5 left-0.5 h-[calc(100%-4px)] w-1/2 rounded-full",
									"bg-(--color-course)/10 border border-(--color-course)/15",
									"transition-transform duration-280 ease-[cubic-bezier(0.22,1,0.36,1)]",
									!adaptiveEnabled && "translate-x-full"
								)}
							/>
							<label
								className={cn(
									"relative z-10 px-4 py-2 text-sm rounded-full cursor-pointer",
									"transition-colors duration-200 min-w-[90px] text-center select-none",
									adaptiveEnabled ? "text-(--color-course-accent) font-medium" : "text-muted-foreground",
									isGenerating && "opacity-50 cursor-not-allowed"
								)}
							>
								<input
									type="radio"
									name="learning-mode"
									checked={adaptiveEnabled}
									onChange={() => !isGenerating && setAdaptiveEnabled(true)}
									disabled={isGenerating}
									className="sr-only"
								/>
								Adaptive
							</label>
							<label
								className={cn(
									"relative z-10 px-4 py-2 text-sm rounded-full cursor-pointer",
									"transition-colors duration-200 min-w-[90px] text-center select-none",
									!adaptiveEnabled ? "text-(--color-course-accent) font-medium" : "text-muted-foreground",
									isGenerating && "opacity-50 cursor-not-allowed"
								)}
							>
								<input
									type="radio"
									name="learning-mode"
									checked={!adaptiveEnabled}
									onChange={() => !isGenerating && setAdaptiveEnabled(false)}
									disabled={isGenerating}
									className="sr-only"
								/>
								Standard
							</label>
						</div>
						<Tooltip>
							<TooltipTrigger asChild>
								<button
									type="button"
									onClick={(e) => e.preventDefault()}
									disabled={isGenerating}
									className="text-muted-foreground/50 hover:text-muted-foreground transition-colors duration-150"
									aria-label="Learning mode information"
								>
									<HelpCircle className="size-3.5" />
								</button>
							</TooltipTrigger>
							<TooltipContent side="top" className="text-xs max-w-[200px]">
								{adaptiveEnabled ? adaptiveModeTooltipCopy.adaptive : adaptiveModeTooltipCopy.standard}
							</TooltipContent>
						</Tooltip>
					</div>

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
					<AnimatePresence>
						{isGenerating && (
							<motion.div
								key="loading-overlay"
								initial={{ opacity: 0 }}
								animate={{ opacity: 1 }}
								exit={{ opacity: 0 }}
								transition={{ duration: 0.3 }}
								className="absolute inset-0 top-12 z-20 flex items-center justify-center rounded-lg bg-background shadow-sm border border-border/30"
							>
								<AnimatePresence mode="wait">
									<motion.div
										key={showInitial ? "initial" : messageIndex}
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										exit={{ opacity: 0 }}
										transition={{ duration: 0.5, ease: "easeInOut" }}
										className="text-base text-center px-8"
									>
										{showInitial ? "Loading..." : EXISTENTIAL_MESSAGES[messageIndex]}
									</motion.div>
								</AnimatePresence>
							</motion.div>
						)}
					</AnimatePresence>
					<AnimatePresence>
						{error && (
							<motion.div
								key="error-overlay"
								initial={{ opacity: 0 }}
								animate={{ opacity: 1 }}
								exit={{ opacity: 0 }}
								transition={{ duration: 0.3 }}
								className="absolute inset-0 top-12 z-20 flex flex-col items-center justify-center rounded-lg bg-background shadow-sm border border-border/30"
							>
								<AnimatePresence mode="wait">
									<motion.div
										key={errorIndex}
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										exit={{ opacity: 0 }}
										transition={{ duration: 0.5, ease: "easeInOut" }}
										className="text-base text-center px-8 text-destructive"
									>
										{EXISTENTIAL_ERRORS[errorIndex]}
									</motion.div>
								</AnimatePresence>
								<button
									type="button"
									onClick={() => {
										setError("")
										setActiveStep(MODAL_STEPS.PROMPT)
									}}
									className="mt-4 text-sm text-muted-foreground hover:text-foreground transition-colors"
								>
									Try again
								</button>
							</motion.div>
						)}
					</AnimatePresence>
					<AnimatePresence mode="wait">
						{activeStep === MODAL_STEPS.PROMPT ? promptStepContent : selfAssessmentStep}
					</AnimatePresence>
				</div>
			</DialogContent>
		</Dialog>
	)
}

export default CoursePromptModal

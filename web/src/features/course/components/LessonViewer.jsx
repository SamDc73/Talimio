import {
	AlertTriangle,
	ArrowLeft,
	ArrowRight,
	CheckCircle2,
	HelpCircle,
	History,
	Loader2,
	RotateCcw,
} from "lucide-react"
import { useMemo, useRef } from "react"
import { Link } from "react-router-dom"
import { Badge } from "@/components/Badge"
import { Button } from "@/components/Button"
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/DropdownMenu"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/Tooltip"
import { cn } from "@/lib/utils"
import { AdaptiveReviewPanel } from "./AdaptiveReviewPanel"
import { ContentRenderer } from "./ContentRenderer"
import { LessonQuickCheckPanel } from "./LessonQuickCheckPanel"
import { PracticeRegistryProvider } from "./PracticeRegistryProvider"

const LESSON_REGENERATION_BANNER_STYLES = {
	inProgress: {
		icon: Loader2,
		iconClassName: "animate-spin text-(--color-course)",
		role: "status",
		title: "Regenerating lesson",
		message: "Refreshing this lesson with your notes. The updated version will appear automatically.",
		className: "border-(--color-course)/15 bg-(--color-course)/5",
	},
	error: {
		icon: AlertTriangle,
		iconClassName: "text-destructive",
		role: "alert",
		title: "Regeneration failed",
		className: "border-destructive/30 bg-destructive/10",
	},
}

const LESSON_NEXT_PASS_BANNER_STYLES = {
	inProgress: {
		icon: Loader2,
		iconClassName: "animate-spin text-(--color-course)",
		role: "status",
		title: "Going deeper",
		className: "border-(--color-course)/15 bg-(--color-course)/5",
	},
	error: {
		icon: AlertTriangle,
		iconClassName: "text-destructive",
		role: "alert",
		title: "Couldn't start the deeper version",
		className: "border-destructive/30 bg-destructive/10",
	},
}

const LESSON_SHELL_HEADER_CLASS_NAME =
	"border-b border-border/40 bg-linear-to-br from-(--color-course)/8 via-background to-(--color-course-accent)/5"

const LESSON_FLOW_ACTION_BUTTON_CLASS_NAME =
	"gap-1.5 bg-(--color-course) text-(--color-course-text) hover:bg-(--color-course)/90 shadow-xs"

const FLOW_CARD_COMPLETED_ROW_CLASS_NAME =
	"flex min-h-[3.294rem] w-full items-center justify-between gap-[0.786rem] rounded-[1.272rem] border border-border/20 bg-muted/20 px-[1.272rem] py-[0.618rem] text-left transition-all hover:bg-muted/40"

const FLOW_CARD_HEADER_BUTTON_CLASS_NAME =
	"flex min-h-[4.182rem] w-full items-center gap-[0.786rem] px-[1.272rem] py-[1.062rem] text-left"

const FLOW_CARD_MARKER_SLOT_CLASS_NAME = "flex size-[2.058rem] shrink-0 items-center justify-center"

const FLOW_CARD_MARKER_CLASS_NAME = `${FLOW_CARD_MARKER_SLOT_CLASS_NAME} rounded-full text-[0.786rem] leading-none font-semibold tracking-[-0.014em] tabular-nums transition-all`

const FLOW_CARD_COMPLETED_ICON_CLASS_NAME = "size-[1.618rem] text-(--color-course)"

const FLOW_CARD_TITLE_CLASS_NAME =
	"min-w-0 flex-1 truncate text-[1.062rem] leading-[1.272rem] font-medium tracking-[-0.011em] transition-colors"

const FLOW_CARD_CONTENT_CLASS_NAME =
	"border-t border-border/20 px-[1.272rem] py-[1.272rem] md:px-[1.618rem] md:py-[1.618rem]"

function truncatePreview(text, maxLength = 56) {
	if (!text || text.length <= maxLength) {
		return text
	}

	return `${text.slice(0, maxLength - 3).trimEnd()}...`
}

function cleanWindowPreviewLine(line) {
	return line
		.replace(/!\[[^\]]*\]\([^)]+\)/g, " ")
		.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
		.replace(/^#{1,6}\s+/, "")
		.replace(/^>\s?/, "")
		.replace(/^[-*+]\s+/, "")
		.replace(/^\d+\.\s+/, "")
		.replace(/[*_`~]/g, "")
		.replace(/\s+/g, " ")
		.trim()
}

function getWindowMicroSummary(window) {
	if (typeof window?.content === "string") {
		const windowTitle = typeof window?.title === "string" ? window.title.trim().toLowerCase() : null

		for (const line of window.content.split("\n")) {
			const preview = cleanWindowPreviewLine(line)

			if (!preview) {
				continue
			}

			if (windowTitle && preview.toLowerCase() === windowTitle) {
				continue
			}

			return truncatePreview(preview)
		}
	}

	if (Number.isFinite(window?.estimatedMinutes) && window.estimatedMinutes > 0) {
		return `${window.estimatedMinutes} min section`
	}

	return "Section finished"
}

function getWindowProgressDotClasses(isActive, isCompleted) {
	if (isActive) {
		return {
			dotSizeClass: "size-[0.5rem]",
			dotColorClass: "bg-(--color-course) shadow-sm",
		}
	}

	if (isCompleted) {
		return {
			dotSizeClass: "size-[0.382rem]",
			dotColorClass: "bg-(--color-course)/45",
		}
	}

	return {
		dotSizeClass: "size-[0.309rem]",
		dotColorClass: "bg-muted-foreground/20",
	}
}

function getWindowMarkerClass(isActive, isCompleted) {
	if (isActive) {
		return "bg-(--color-course) text-(--color-course-text)"
	}

	if (isCompleted) {
		return "bg-(--color-course)/12 text-(--color-course)"
	}

	return "bg-muted text-muted-foreground/60"
}

function LessonFlowActionButton({ label, onClick, className }) {
	return (
		<Button type="button" size="sm" onClick={onClick} className={cn(LESSON_FLOW_ACTION_BUTTON_CLASS_NAME, className)}>
			{label}
			<ArrowRight className="size-4" />
		</Button>
	)
}

function LessonWindowProgressDots({ windows, activeWindowIndex, onWindowChange }) {
	return (
		<div className="px-6 pb-[1rem] pt-[0.618rem] md:px-8">
			<div className="flex items-center justify-center">
				<div className="flex flex-wrap items-center gap-[0.618rem]">
					{windows.map((window) => {
						const isActive = window.windowIndex === activeWindowIndex
						const isCompleted = window.windowIndex < activeWindowIndex
						const { dotSizeClass, dotColorClass } = getWindowProgressDotClasses(isActive, isCompleted)

						return (
							<button
								key={window.id}
								type="button"
								onClick={() => onWindowChange?.(window.windowIndex)}
								className="flex size-[1.618rem] items-center justify-center rounded-full transition-colors hover:bg-muted/40"
								aria-label={`Go to ${window.title || `section ${window.windowIndex + 1}`}`}
							>
								<span className={cn("rounded-full transition-all duration-200", dotSizeClass, dotColorClass)} />
							</button>
						)
					})}
				</div>
			</div>
		</div>
	)
}

function LessonNextRail({ nextLesson, onLessonNavigate }) {
	if (!nextLesson || !onLessonNavigate) {
		return null
	}

	return (
		<div className="px-6 pb-[1.618rem] pt-[0.618rem] md:px-8">
			<div className="flex justify-end">
				<LessonFlowActionButton
					label="Next Lesson"
					onClick={() => onLessonNavigate(nextLesson.id)}
					className="w-full justify-center sm:w-auto sm:min-w-[8.5rem]"
				/>
			</div>
		</div>
	)
}

/**
 * LessonViewer - Presents a lesson with MDX content and actions
 * - Uses design tokens (bg-card, border-border, text-foreground, etc.)
 * - Dark mode via Tailwind's .dark class (no isDarkMode prop)
 * - Aligns with Tailwind v4 and Styling guides
 */
export function LessonViewer({
	lesson,
	isLoading,
	error,
	onBack,
	onRegenerate,
	isRegeneratingLesson = false,
	regenerateStatus = null,
	modules = [],
	nextLesson,
	onLessonNavigate,
	onStartNextPass,
	onVersionSelect,
	activeWindowIndex = 0,
	onWindowChange,
	isStartingNextPass = false,
	nextPassStatus = null,
	adaptiveEnabled = false,
	courseId,
}) {
	const containerRef = useRef(null)
	const availableVersions = Array.isArray(lesson?.availableVersions) ? lesson.availableVersions : []
	const nextPass = lesson?.nextPass ?? null
	const lessonWindows = Array.isArray(lesson?.windows) ? lesson.windows : []
	const lessonCourseId = courseId ?? lesson?.courseId ?? null
	const lessonConceptId = lesson?.conceptId ?? null
	const hasMultipleWindows = lessonWindows.length > 1
	const selectedWindow = lessonWindows[activeWindowIndex] ?? lessonWindows[0] ?? null
	const currentVersionLabel =
		typeof lesson?.majorVersion === "number" && typeof lesson?.minorVersion === "number"
			? `${lesson.majorVersion}.${lesson.minorVersion}`
			: null
	const isViewingHistoricalVersion =
		lesson?.versionId && lesson?.currentVersionId && String(lesson.versionId) !== String(lesson.currentVersionId)
	const canShowVersionMenu = Boolean((availableVersions.length > 1 || nextPass) && (onVersionSelect || onStartNextPass))
	let regenerationBanner = null
	let regenerationBannerContent = null
	let nextPassBanner = null
	let nextPassBannerContent = null

	if (isRegeneratingLesson) {
		regenerationBanner = LESSON_REGENERATION_BANNER_STYLES.inProgress
	} else if (regenerateStatus?.type === "error") {
		regenerationBanner = {
			...LESSON_REGENERATION_BANNER_STYLES.error,
			message: regenerateStatus.message,
		}
	}

	if (regenerationBanner) {
		const RegenerationIcon = regenerationBanner.icon

		regenerationBannerContent = (
			<div className="px-6 pt-5 md:px-8">
				<div
					role={regenerationBanner.role}
					aria-live="polite"
					className={cn(
						"flex items-start gap-3 rounded-xl border px-4 py-3 text-sm backdrop-blur-sm",
						regenerationBanner.className
					)}
				>
					<RegenerationIcon
						className={cn("mt-0.5 size-4 shrink-0", regenerationBanner.iconClassName)}
						aria-hidden="true"
					/>
					<div className="space-y-1">
						<p className="font-medium text-foreground">{regenerationBanner.title}</p>
						<p className="text-muted-foreground">{regenerationBanner.message}</p>
					</div>
				</div>
			</div>
		)
	}

	if (isStartingNextPass) {
		nextPassBanner = {
			...LESSON_NEXT_PASS_BANNER_STYLES.inProgress,
			message: nextPassStatus?.message || "Preparing the deeper version for this concept.",
		}
	} else if (nextPassStatus?.type === "error") {
		nextPassBanner = {
			...LESSON_NEXT_PASS_BANNER_STYLES.error,
			message: nextPassStatus.message,
		}
	}

	if (nextPassBanner) {
		const NextPassIcon = nextPassBanner.icon

		nextPassBannerContent = (
			<div className="px-6 pt-5 md:px-8">
				<div
					role={nextPassBanner.role}
					aria-live="polite"
					className={cn(
						"flex items-start gap-3 rounded-xl border px-4 py-3 text-sm backdrop-blur-sm",
						nextPassBanner.className
					)}
				>
					<NextPassIcon className={cn("mt-0.5 size-4 shrink-0", nextPassBanner.iconClassName)} aria-hidden="true" />
					<div className="space-y-1">
						<p className="font-medium text-foreground">{nextPassBanner.title}</p>
						<p className="text-muted-foreground">{nextPassBanner.message}</p>
					</div>
				</div>
			</div>
		)
	}

	const formatVersionKindLabel = (version) => {
		switch (version?.versionKind) {
			case "first_pass":
				return "First version"
			case "regeneration":
				return "Updated"
			case "revisit_pass":
				return "Deeper version"
			default:
				return "Version"
		}
	}

	const formatVersionTimestamp = (timestamp) => {
		if (!timestamp) {
			return null
		}

		const parsed = new Date(timestamp)
		if (Number.isNaN(parsed.getTime())) {
			return null
		}

		return new Intl.DateTimeFormat(undefined, {
			month: "short",
			day: "numeric",
			year: parsed.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
		}).format(parsed)
	}

	const nextVersionDisplay = nextPass ? `v${nextPass.majorVersion}.0` : null
	let nextPassActionLabel = null
	let nextPassHelperText = null
	if (nextPass) {
		nextPassActionLabel = nextPass.status === "recommended_now" ? "Go deeper" : "Go deeper early"
		nextPassHelperText =
			nextPass.status === "recommended_now" ? `Creates ${nextVersionDisplay}` : `${nextVersionDisplay} · usually later`
	}

	const derivedNextLesson = useMemo(() => {
		if (!lesson?.id || !modules?.length) {
			return null
		}

		const allLessons = []
		for (const module of modules) {
			if (Array.isArray(module?.lessons)) {
				for (const lessonItem of module.lessons) {
					allLessons.push(lessonItem)
				}
			}
		}

		const currentIndex = allLessons.findIndex((lessonItem) => String(lessonItem?.id) === String(lesson.id))
		if (currentIndex === -1) {
			return null
		}

		return currentIndex < allLessons.length - 1 ? allLessons[currentIndex + 1] : null
	}, [lesson?.id, modules])

	const resolvedNextLesson = nextLesson !== undefined ? nextLesson : derivedNextLesson

	// Loading state
	if (isLoading) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-muted-foreground">
					<div className="animate-spin rounded-full size-12  border-y-2  border-primary mb-4" />
					<p>Loading lesson...</p>
				</div>
			</div>
		)
	}

	// Error state
	if (error) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-destructive">
					<div className="mx-auto max-w-3xl rounded-2xl border border-destructive/30 bg-destructive/10 p-6 shadow-sm">
						<h2 className="text-xl font-semibold mb-4">Error loading lesson</h2>
						<p className="mb-4">{error}</p>
						<Button onClick={onBack} variant="outline" size="sm">
							<ArrowLeft className="size-4 " />
							Back
						</Button>
					</div>
				</div>
			</div>
		)
	}

	// No lesson state
	if (!lesson) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-muted-foreground">
					<div className="mx-auto max-w-3xl rounded-2xl border border-border/70 bg-card p-6 shadow-sm">
						<h2 className="text-xl font-semibold mb-4 text-foreground">No lesson available</h2>
						<p className="mb-4">This lesson could not be loaded.</p>
						<Button onClick={onBack} variant="outline" size="sm">
							<ArrowLeft className="size-4 " />
							Back
						</Button>
					</div>
				</div>
			</div>
		)
	}

	return (
		<div ref={containerRef} className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
			<div className="max-w-4xl w-full mx-auto px-4 flex justify-center">
				<div className="my-8 flex w-full flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm">
					{/* Header */}
					<div className={cn(LESSON_SHELL_HEADER_CLASS_NAME, "px-6 pt-5 pb-6 md:px-8 md:pt-6 md:pb-8")}>
						<div className="flex flex-col gap-4 md:gap-5">
							<div className="flex items-center justify-between gap-3">
								<div className="flex items-center gap-3">
									<Button
										onClick={onBack}
										variant="ghost"
										size="sm"
										className="gap-1.5 -ml-2 text-muted-foreground/60 hover:text-foreground hover:bg-transparent"
									>
										<ArrowLeft className="size-4" />
										Back
									</Button>
									{canShowVersionMenu && (
										<DropdownMenu>
											<DropdownMenuTrigger asChild>
												<Button
													variant="ghost"
													size="sm"
													className="gap-1 h-6 px-2 text-xs text-muted-foreground/60 hover:text-(--color-course) hover:bg-(--color-course)/8 transition-colors"
												>
													<History className="size-3" />v{currentVersionLabel}
												</Button>
											</DropdownMenuTrigger>
											<DropdownMenuContent align="end" className="w-72">
												<div className="flex items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground">
													<span>Versions</span>
													<Tooltip>
														<TooltipTrigger asChild>
															<button
																type="button"
																onClick={(event) => event.preventDefault()}
																className="text-muted-foreground/60 transition-colors hover:text-muted-foreground"
																aria-label="Version information"
															>
																<HelpCircle className="size-3.5" />
															</button>
														</TooltipTrigger>
														<TooltipContent side="left" className="max-w-[220px] text-xs">
															<p>
																Minor versions rewrite the same lesson. Major versions like v2.0 revisit the topic more
																deeply.
															</p>
														</TooltipContent>
													</Tooltip>
												</div>
												<DropdownMenuSeparator />
												{availableVersions.map((version) => (
													<DropdownMenuItem
														key={version.id}
														onClick={() => onVersionSelect?.(version.id)}
														className="flex items-start justify-between gap-3"
													>
														<div className="min-w-0">
															<p className="font-mono text-sm font-medium text-foreground">v{version.versionLabel}</p>
															<p className="text-xs text-muted-foreground">
																{[formatVersionKindLabel(version), formatVersionTimestamp(version.createdAt)]
																	.filter(Boolean)
																	.join(" · ")}
															</p>
														</div>
														{version.isCurrent ? (
															<Badge variant="outline" className="px-2 py-0.5 text-[10px] uppercase tracking-[0.14em]">
																Current
															</Badge>
														) : null}
													</DropdownMenuItem>
												))}
												{nextPass ? <DropdownMenuSeparator /> : null}
												{nextPass ? (
													<DropdownMenuItem
														onClick={() => onStartNextPass?.()}
														disabled={isViewingHistoricalVersion || isStartingNextPass}
														className={cn(
															"flex items-start gap-3 rounded-md px-3 py-2.5",
															nextPass.status === "available_early" ? "text-muted-foreground" : "text-foreground"
														)}
													>
														<div className="min-w-0 space-y-1">
															<p className="font-medium leading-none">
																{isStartingNextPass ? "Opening deeper version" : nextPassActionLabel}
															</p>
															<p className="text-xs text-muted-foreground">{nextPassHelperText}</p>
															<p className="line-clamp-2 text-xs/relaxed text-muted-foreground/80">{nextPass.reason}</p>
														</div>
													</DropdownMenuItem>
												) : null}
											</DropdownMenuContent>
										</DropdownMenu>
									)}
								</div>

								<div className="flex items-center gap-2">
									{onRegenerate && (
										<Button
											onClick={() => onRegenerate(lesson.id)}
											variant="ghost"
											size="sm"
											className="text-muted-foreground hover:text-(--color-course) hover:bg-(--color-course)/8 transition-colors"
											disabled={isRegeneratingLesson || isViewingHistoricalVersion}
											title={
												isViewingHistoricalVersion ? "Switch back to the current version to regenerate." : undefined
											}
										>
											{isRegeneratingLesson ? (
												<Loader2 className="size-4 animate-spin" />
											) : (
												<RotateCcw className="size-4" />
											)}
											{isRegeneratingLesson ? "Regenerating" : "Regenerate"}
										</Button>
									)}
									{adaptiveEnabled && lessonCourseId && lessonConceptId && (
										<Link
											to={`/course/${lessonCourseId}/practice?focusConceptId=${encodeURIComponent(String(lessonConceptId))}`}
										>
											<Button
												size="sm"
												className="gap-1.5 bg-(--color-course) text-(--color-course-text) hover:bg-(--color-course)/90 shadow-xs"
											>
												Practice
											</Button>
										</Link>
									)}
								</div>
							</div>

							<div className="space-y-2.5">
								<h1 className="max-w-3xl text-3xl/tight font-semibold tracking-tight text-foreground md:text-4xl/tight">
									{lesson.title || lesson.slug || "Lesson"}
								</h1>
								{lesson.description ? (
									<p className="max-w-2xl text-sm/relaxed text-muted-foreground md:text-base/relaxed">
										{lesson.description}
									</p>
								) : null}
							</div>
						</div>
					</div>

					{regenerationBannerContent}
					{nextPassBannerContent}

					{hasMultipleWindows ? (
						<div>
							<div className="space-y-[0.618rem] px-6 py-[1rem] md:px-8 md:py-[1.618rem]">
								{lessonWindows.map((window) => {
									const isActive = window.windowIndex === activeWindowIndex
									const isCompleted = window.windowIndex < activeWindowIndex
									const isLastWindow = window.windowIndex === lessonWindows.length - 1
									const sectionClass = isActive
										? "border-(--color-course)/20 bg-(--color-course)/3 shadow-xs"
										: "border-border/30 bg-card"
									const markerClass = getWindowMarkerClass(isActive, isCompleted)
									const titleClass = isActive ? "text-foreground" : "text-muted-foreground"

									if (isCompleted) {
										return (
											<button
												key={window.id}
												type="button"
												onClick={() => onWindowChange?.(window.windowIndex)}
												className={FLOW_CARD_COMPLETED_ROW_CLASS_NAME}
											>
												<div className="flex min-w-0 flex-1 items-center gap-[0.786rem]">
													<span className={FLOW_CARD_MARKER_SLOT_CLASS_NAME}>
														<CheckCircle2 className={FLOW_CARD_COMPLETED_ICON_CLASS_NAME} />
													</span>
													<span className="truncate text-[0.938rem] leading-[1.272rem] font-medium tracking-[-0.011em] text-muted-foreground line-through decoration-muted-foreground/30">
														{window.title || `Section ${window.windowIndex + 1}`}
													</span>
												</div>
												<span className="max-w-[38.2%] truncate text-[0.786rem] leading-[1.128rem] text-muted-foreground/60">
													{getWindowMicroSummary(window)}
												</span>
											</button>
										)
									}

									return (
										<section
											key={window.id}
											className={cn("overflow-hidden rounded-[1.618rem] border transition-all", sectionClass)}
										>
											<button
												type="button"
												onClick={() => onWindowChange?.(window.windowIndex)}
												className={FLOW_CARD_HEADER_BUTTON_CLASS_NAME}
												aria-expanded={isActive}
											>
												<span className={cn(FLOW_CARD_MARKER_CLASS_NAME, markerClass)}>{window.windowIndex + 1}</span>
												<span className={cn(FLOW_CARD_TITLE_CLASS_NAME, titleClass)}>
													{window.title || `Section ${window.windowIndex + 1}`}
												</span>
											</button>
											{isActive ? (
												<div className={FLOW_CARD_CONTENT_CLASS_NAME}>
													<div className="space-y-6" data-selection-zone="true">
														<PracticeRegistryProvider>
															<ContentRenderer
																content={
																	window.content || selectedWindow?.content || lesson.content || lesson.md_source
																}
																lessonId={lesson.id}
																courseId={lessonCourseId}
																lessonConceptId={lessonConceptId}
															/>
															<LessonQuickCheckPanel
																courseId={lessonCourseId}
																lessonId={lesson.id}
																lessonConceptId={lessonConceptId}
															/>
														</PracticeRegistryProvider>

														{adaptiveEnabled && lessonCourseId && lesson?.id ? (
															<AdaptiveReviewPanel
																courseId={lessonCourseId}
																lessonId={lesson.id}
																lessonConceptId={lessonConceptId}
																adaptiveEnabled={adaptiveEnabled}
															/>
														) : null}
													</div>

													{!isLastWindow ? (
														<div className="mt-[1.618rem] border-t border-border/20 pt-[1.618rem]">
															<div className="flex justify-end">
																<LessonFlowActionButton
																	label="Next"
																	onClick={() => onWindowChange?.(window.windowIndex + 1)}
																	className="w-full justify-center sm:w-auto sm:min-w-[7.382rem]"
																/>
															</div>
														</div>
													) : null}
												</div>
											) : null}
										</section>
									)
								})}
							</div>

							{activeWindowIndex === lessonWindows.length - 1 ? (
								<LessonNextRail nextLesson={resolvedNextLesson} onLessonNavigate={onLessonNavigate} />
							) : null}

							<LessonWindowProgressDots
								windows={lessonWindows}
								activeWindowIndex={activeWindowIndex}
								onWindowChange={onWindowChange}
							/>
						</div>
					) : (
						<>
							<div className="p-6 md:p-8" data-selection-zone="true">
								<PracticeRegistryProvider>
									<ContentRenderer
										content={selectedWindow?.content || lesson.content || lesson.md_source}
										lessonId={lesson.id}
										courseId={lessonCourseId}
										lessonConceptId={lessonConceptId}
									/>
									<LessonQuickCheckPanel
										courseId={lessonCourseId}
										lessonId={lesson.id}
										lessonConceptId={lessonConceptId}
									/>
								</PracticeRegistryProvider>
							</div>

							{/* Adaptive Review Panel - blends seamlessly into lesson flow */}
							{adaptiveEnabled && lessonCourseId && lesson?.id && (
								<div className="px-6 pt-4 md:px-8">
									<AdaptiveReviewPanel
										courseId={lessonCourseId}
										lessonId={lesson.id}
										lessonConceptId={lessonConceptId}
										adaptiveEnabled={adaptiveEnabled}
									/>
								</div>
							)}

							<LessonNextRail nextLesson={resolvedNextLesson} onLessonNavigate={onLessonNavigate} />
						</>
					)}
				</div>
			</div>
		</div>
	)
}

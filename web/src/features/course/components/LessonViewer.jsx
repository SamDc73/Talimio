import {
	AlertTriangle,
	ArrowLeft,
	ArrowRight,
	CheckCircle,
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
	"border-b border-border/60 bg-linear-to-br from-(--color-course)/12 via-background to-(--color-course-accent)/10"
const ACTIVE_WINDOW_BUTTON_CLASS_NAME = "border-(--color-course)/20 bg-(--color-course)/10 text-(--color-course)"
const REGENERATE_ACTION_CLASS_NAME =
	"border-(--color-course)/20 text-(--color-course) hover:bg-(--color-course)/10 hover:text-(--color-course)"

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
	onMarkComplete,
	onRegenerate,
	isRegeneratingLesson = false,
	regenerateStatus = null,
	modules = [],
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

	const windowTitle = selectedWindow?.title || (hasMultipleWindows ? `Window ${activeWindowIndex + 1}` : null)
	const currentVersionDisplay = currentVersionLabel ? `v${currentVersionLabel}` : "Versions"
	const nextVersionDisplay = nextPass ? `v${nextPass.majorVersion}.0` : null
	let nextPassActionLabel = null
	let nextPassHelperText = null
	if (nextPass) {
		nextPassActionLabel = nextPass.status === "recommended_now" ? "Go deeper" : "Go deeper early"
		nextPassHelperText =
			nextPass.status === "recommended_now" ? `Creates ${nextVersionDisplay}` : `${nextVersionDisplay} · usually later`
	}

	// Calculate previous and next lessons from modules
	const { previousLesson, nextLesson } = useMemo(() => {
		if (!lesson?.id || !modules?.length) {
			return { previousLesson: null, nextLesson: null }
		}

		// Flatten all lessons from all modules
		const allLessons = []
		for (const module of modules) {
			if (Array.isArray(module?.lessons)) {
				for (const lessonItem of module.lessons) {
					allLessons.push(lessonItem)
				}
			}
		}

		// Find current lesson index
		const currentIndex = allLessons.findIndex((l) => String(l?.id) === String(lesson.id))
		if (currentIndex === -1) {
			return { previousLesson: null, nextLesson: null }
		}

		return {
			previousLesson: currentIndex > 0 ? allLessons[currentIndex - 1] : null,
			nextLesson: currentIndex < allLessons.length - 1 ? allLessons[currentIndex + 1] : null,
		}
	}, [lesson?.id, modules])

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
					<div className={cn(LESSON_SHELL_HEADER_CLASS_NAME, "p-6 md:p-8")}>
						<div className="flex flex-col gap-5">
							<div className="flex flex-wrap items-center justify-between gap-3">
								<Button onClick={onBack} variant="secondary" size="sm">
									<ArrowLeft className="size-4 " />
									Back
								</Button>

								<div className="flex flex-wrap items-center gap-2">
									{adaptiveEnabled && lessonCourseId && lessonConceptId && (
										<Link
											to={`/course/${lessonCourseId}/practice?focusConceptId=${encodeURIComponent(String(lessonConceptId))}`}
										>
											<Button variant="outline" size="sm">
												Practice Concept
											</Button>
										</Link>
									)}
									{canShowVersionMenu ? (
										<DropdownMenu>
											<DropdownMenuTrigger asChild>
												<Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
													<History className="size-4" />
													<span className="font-mono text-xs">{currentVersionDisplay}</span>
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
									) : null}
									{onRegenerate && (
										<Button
											onClick={() => onRegenerate(lesson.id)}
											variant="outline"
											size="sm"
											className={REGENERATE_ACTION_CLASS_NAME}
											disabled={isRegeneratingLesson || isViewingHistoricalVersion}
											title={
												isViewingHistoricalVersion ? "Switch back to the current version to regenerate." : undefined
											}
										>
											{isRegeneratingLesson ? (
												<Loader2 className="size-4 animate-spin" />
											) : (
												<RotateCcw className="size-4 " />
											)}
											{isRegeneratingLesson ? "Regenerating" : "Regenerate"}
										</Button>
									)}

									{onMarkComplete && (
										<Button onClick={() => onMarkComplete(lesson.id)} size="sm">
											<CheckCircle className="size-4 " />
											Complete
										</Button>
									)}
								</div>
							</div>

							<div className="space-y-4">
								<div className="flex flex-wrap items-center gap-2">
									{lesson.module_name ? (
										<Badge
											variant="outline"
											className="rounded-full border-border/60 bg-background/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground"
										>
											{lesson.module_name}
										</Badge>
									) : null}
								</div>

								<div className="space-y-3">
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
					</div>

					{regenerationBannerContent}
					{nextPassBannerContent}

					{hasMultipleWindows ? (
						<div className="border-b border-border/50 bg-background/80 px-6 py-4 md:px-8">
							<div className="flex flex-wrap items-center justify-between gap-3">
								<div className="flex flex-wrap items-center gap-2">
									{lessonWindows.map((window) => {
										const isActive = window.windowIndex === activeWindowIndex
										return (
											<button
												key={window.id}
												type="button"
												onClick={() => onWindowChange?.(window.windowIndex)}
												className={cn(
													"rounded-full border px-3 py-1.5 text-sm transition-colors",
													isActive
														? ACTIVE_WINDOW_BUTTON_CLASS_NAME
														: "border-border bg-background text-muted-foreground hover:bg-muted"
												)}
											>
												<span className="font-medium">{window.windowIndex + 1}</span>
												{window.title ? <span className="ml-2 hidden sm:inline">{window.title}</span> : null}
											</button>
										)
									})}
								</div>
								{selectedWindow?.estimatedMinutes ? (
									<span className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
										{selectedWindow.estimatedMinutes} min
									</span>
								) : null}
							</div>
						</div>
					) : null}

					{/* Content */}
					<div className="p-6 md:p-8" data-selection-zone="true">
						<PracticeRegistryProvider>
							{hasMultipleWindows && windowTitle ? (
								<div className="mb-6 space-y-1">
									<p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Window {activeWindowIndex + 1} of {lessonWindows.length}
									</p>
									<h2 className="text-xl font-semibold text-foreground">{windowTitle}</h2>
								</div>
							) : null}
							<ContentRenderer
								content={selectedWindow?.content || lesson.content || lesson.md_source}
								lessonId={lesson.id}
								courseId={lessonCourseId}
								lessonConceptId={lessonConceptId}
							/>
							<LessonQuickCheckPanel courseId={lessonCourseId} lessonId={lesson.id} lessonConceptId={lessonConceptId} />
						</PracticeRegistryProvider>
					</div>

					{hasMultipleWindows ? (
						<div className="px-6 pb-2 md:px-8">
							<div className="flex items-center justify-between gap-4 border-t border-border/40 pt-4">
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={() => onWindowChange?.(activeWindowIndex - 1)}
									disabled={activeWindowIndex === 0}
								>
									<ArrowLeft className="size-4 " />
									Back
								</Button>
								<span className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
									Window {activeWindowIndex + 1} of {lessonWindows.length}
								</span>
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={() => onWindowChange?.(activeWindowIndex + 1)}
									disabled={activeWindowIndex >= lessonWindows.length - 1}
								>
									Next
									<ArrowRight className="size-4 " />
								</Button>
							</div>
						</div>
					) : null}

					{/* Adaptive Review Panel - blends seamlessly into lesson flow */}
					{adaptiveEnabled && lessonCourseId && lesson?.id && (
						<div className="px-6 md:px-8 pt-4">
							<AdaptiveReviewPanel
								courseId={lessonCourseId}
								lessonId={lesson.id}
								lessonConceptId={lessonConceptId}
								adaptiveEnabled={adaptiveEnabled}
							/>
						</div>
					)}

					{/* Lesson Navigation - subtle footer navigation */}
					{onLessonNavigate && (previousLesson || nextLesson) && (
						<div className="px-6 md:px-8 pb-8 pt-4">
							<div className="flex items-center justify-between gap-4 pt-6 mt-6 border-t border-border/40">
								{previousLesson ? (
									<Button type="button" variant="outline" size="sm" onClick={() => onLessonNavigate(previousLesson.id)}>
										<ArrowLeft className="size-4 " />
										Previous
									</Button>
								) : (
									<div />
								)}

								{nextLesson ? (
									<Button
										type="button"
										variant="default"
										size="sm"
										onClick={() => onLessonNavigate(nextLesson.id)}
										className="ml-auto"
									>
										Next Lesson
										<ArrowRight className="size-4 " />
									</Button>
								) : (
									<div />
								)}
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	)
}

import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle, History, Loader2, RotateCcw } from "lucide-react"
import { useMemo, useRef } from "react"
import { Link } from "react-router-dom"
import { Badge } from "@/components/Badge"
import { Button } from "@/components/Button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/DropdownMenu"
import { cn } from "@/lib/utils"
import { AdaptiveReviewPanel } from "./AdaptiveReviewPanel"
import { ContentRenderer } from "./ContentRenderer"
import { LessonQuickCheckPanel } from "./LessonQuickCheckPanel"
import { PracticeRegistryProvider } from "./PracticeRegistryProvider"

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
	onVersionSelect,
	activeWindowIndex = 0,
	onWindowChange,
	adaptiveEnabled = false,
	courseId,
}) {
	const containerRef = useRef(null)
	const availableVersions = Array.isArray(lesson?.availableVersions) ? lesson.availableVersions : []
	const lessonWindows = Array.isArray(lesson?.windows) ? lesson.windows : []
	const hasMultipleWindows = lessonWindows.length > 1
	const selectedWindow = lessonWindows[activeWindowIndex] ?? lessonWindows[0] ?? null
	const currentVersionLabel =
		typeof lesson?.majorVersion === "number" && typeof lesson?.minorVersion === "number"
			? `${lesson.majorVersion}.${lesson.minorVersion}`
			: null
	const isViewingHistoricalVersion =
		lesson?.versionId && lesson?.currentVersionId && String(lesson.versionId) !== String(lesson.currentVersionId)
	let regenerationBanner = null
	let regenerationBannerContent = null

	if (isRegeneratingLesson) {
		regenerationBanner = {
			icon: Loader2,
			iconClassName: "animate-spin text-primary",
			role: "status",
			title: "Regenerating lesson",
			message: "Refreshing this lesson with your notes. The updated version will appear automatically.",
			className: "border-primary/15 bg-primary/5",
		}
	} else if (regenerateStatus?.type === "error") {
		regenerationBanner = {
			icon: AlertTriangle,
			iconClassName: "text-destructive",
			role: "alert",
			title: "Regeneration failed",
			message: regenerateStatus.message,
			className: "border-destructive/30 bg-destructive/10",
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

	const formatVersionKindLabel = (version) => {
		return version?.historyLabel || version?.passLabel || version?.versionKind || "Version"
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
					<div className="max-w-3xl mx-auto p-6 bg-destructive/10 rounded-lg border border-destructive/30">
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
					<div className="max-w-3xl mx-auto p-6 bg-muted rounded-lg border border-border">
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
					<div className="border-b border-border/60 bg-linear-to-br from-emerald-500/[0.08] via-background to-cyan-500/[0.04] p-6 md:p-8">
						<div className="flex flex-col gap-5">
							<div className="flex flex-wrap items-center justify-between gap-3">
								<Button onClick={onBack} variant="secondary" size="sm">
									<ArrowLeft className="size-4 " />
									Back
								</Button>

								<div className="flex flex-wrap items-center gap-2">
									{adaptiveEnabled && courseId && lesson?.concept_id && (
										<Link
											to={`/course/${courseId}/practice?focusConceptId=${encodeURIComponent(String(lesson.concept_id))}`}
										>
											<Button variant="outline" size="sm">
												Practice Concept
											</Button>
										</Link>
									)}
									{availableVersions.length > 1 && onVersionSelect ? (
										<DropdownMenu>
											<DropdownMenuTrigger asChild>
												<Button variant="ghost" size="sm" className="text-muted-foreground">
													<History className="size-4" />
													<span>History</span>
													{currentVersionLabel ? (
														<span className="font-mono text-xs">v{currentVersionLabel}</span>
													) : null}
												</Button>
											</DropdownMenuTrigger>
											<DropdownMenuContent align="end" className="w-72">
												{availableVersions.map((version) => (
													<DropdownMenuItem
														key={version.id}
														onClick={() => onVersionSelect(version.id)}
														className="flex items-start justify-between gap-3"
													>
														<div className="min-w-0">
															<p className="font-medium text-foreground">
																{version.passLabel || "Version"}{" "}
																<span className="font-mono text-xs">v{version.versionLabel}</span>
															</p>
															<p className="text-xs text-muted-foreground">
																{[formatVersionKindLabel(version), formatVersionTimestamp(version.createdAt)]
																	.filter(Boolean)
																	.join(" · ")}
															</p>
															{version.sourceReason ? (
																<p className="line-clamp-2 text-xs/relaxed text-muted-foreground/80">
																	{version.sourceReason}
																</p>
															) : null}
														</div>
														{version.isCurrent ? (
															<Badge variant="outline" className="px-2 py-0.5 text-[10px] uppercase tracking-[0.14em]">
																Current
															</Badge>
														) : null}
													</DropdownMenuItem>
												))}
											</DropdownMenuContent>
										</DropdownMenu>
									) : null}
									{onRegenerate && (
										<Button
											onClick={() => onRegenerate(lesson.id)}
											variant="outline"
											size="sm"
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
									{lesson.passLabel ? (
										<Badge
											variant="outline"
											className="rounded-full border-border/60 bg-background/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground"
										>
											{lesson.passLabel}
										</Badge>
									) : null}
									{lesson.versionLabel && lesson.versionLabel !== lesson.passLabel ? (
										<Badge
											variant="outline"
											className="rounded-full border-border/60 bg-background/80 px-3 py-1 font-mono text-[11px] text-muted-foreground"
										>
											v{lesson.versionLabel}
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
														? "border-(--color-course) bg-(--color-course)/10 text-(--color-course)"
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
								courseId={courseId ?? lesson.course_id}
								lessonConceptId={lesson.concept_id}
							/>
							<LessonQuickCheckPanel
								courseId={courseId ?? lesson.course_id}
								lessonId={lesson.id}
								lessonConceptId={lesson.concept_id}
							/>
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
					{adaptiveEnabled && courseId && lesson?.id && (
						<div className="px-6 md:px-8 pt-4">
							<AdaptiveReviewPanel
								courseId={courseId}
								lessonId={lesson.id}
								lessonConceptId={lesson.concept_id}
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

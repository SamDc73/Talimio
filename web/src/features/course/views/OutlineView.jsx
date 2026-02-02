import { useQuery } from "@tanstack/react-query"
import { ArrowRight, CheckCircle2, Circle } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import { Button } from "@/components/Button"
import { MasteryCircle } from "@/components/MasteryCircle"
import { useCourseContext } from "@/features/course/CourseContext.jsx"
import OutlineNode from "@/features/course/components/navigation/OutlineNode.jsx"
import { useCourseProgress } from "@/features/course/hooks/useCourseProgress"
import { useCourseNavigation } from "@/utils/navigationUtils"

function extractLessonId(item) {
	if (!item || typeof item !== "object") return null
	const candidate =
		item.lessonId ??
		item.lesson_id ??
		item.lessonIdRef ??
		item.lesson?.id ??
		(item.id && (item.type === "lesson" || item.category === "lesson") ? item.id : undefined)

	if (candidate === undefined || candidate === null) {
		return null
	}

	return typeof candidate === "string" || typeof candidate === "number" ? candidate : null
}

function findFiniteNumber(values) {
	for (const value of values) {
		if (value === undefined || value === null) continue
		const numeric = typeof value === "string" ? Number(value) : value
		if (typeof numeric === "number" && Number.isFinite(numeric)) {
			return numeric
		}
	}
}

function BuildForecast(meta) {
	if (!meta || typeof meta !== "object") return null
	const candidate =
		meta.forecast ??
		meta.completion_forecast ??
		meta.completionForecast ??
		meta.eta ??
		meta.projections?.completion ??
		null

	const candidateObject = candidate !== null && typeof candidate === "object" ? candidate : {}
	const weeks = findFiniteNumber([
		candidateObject.weeks,
		candidateObject.weeks_remaining,
		candidateObject.weeksRemaining,
		meta.forecast_weeks,
		meta.weeks_remaining,
	])
	const days = findFiniteNumber([
		candidateObject.days,
		candidateObject.days_remaining,
		candidateObject.daysRemaining,
		candidateObject.total_days,
		meta.forecast_days,
		meta.days_remaining,
	])

	if (weeks === undefined && days === undefined) {
		if (typeof candidate === "number") {
			const normalizedDays = Math.max(0, Math.round(candidate))
			return {
				weeks: normalizedDays > 0 ? Math.round(normalizedDays / 7) : 0,
				days: normalizedDays,
			}
		}
		return null
	}

	const normalizedDays =
		days === undefined ? (weeks === undefined ? 0 : Math.max(0, Math.round(weeks * 7))) : Math.max(0, Math.round(days))
	const normalizedWeeks =
		weeks === undefined ? (normalizedDays > 0 ? Math.round(normalizedDays / 7) : 0) : Math.max(0, Math.round(weeks))

	if (normalizedDays === 0 && normalizedWeeks === 0) {
		return null
	}

	return {
		weeks: normalizedWeeks,
		days: normalizedDays,
	}
}

function OutlineView() {
	const { courseId, modules, adaptiveEnabled } = useCourseContext()

	const { isCompleted, metadata, rawMetadata, toggleCompletion } = useCourseProgress(courseId)
	const { goToLesson } = useCourseNavigation()
	const courseService = useCourseService(courseId)

	const flatLessons = useMemo(() => {
		const out = []
		const walk = (items, moduleId, moduleTitle) => {
			for (const item of items) {
				out.push({ id: item.id, title: item.title, moduleId, moduleTitle })
				if (Array.isArray(item?.lessons) && item.lessons.length > 0) walk(item.lessons, moduleId, moduleTitle)
			}
		}
		for (const mod of modules || []) walk(mod.lessons || [], mod.id, mod.title)
		return out
	}, [modules])

	const completedIds = Array.isArray(metadata?.completedLessons) ? metadata.completedLessons : []
	const totalLessons = adaptiveEnabled
		? typeof metadata?.totalLessons === "number"
			? metadata.totalLessons
			: flatLessons.length
		: flatLessons.length
	const completedCount = adaptiveEnabled ? completedIds.length : flatLessons.filter((l) => isCompleted(l.id)).length

	const { data: frontierData } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: async () => await courseService.fetchConceptFrontier(),
		enabled: Boolean(courseId) && adaptiveEnabled,
		staleTime: 30_000,
		refetchOnWindowFocus: false,
	})

	const nextLesson = useMemo(() => {
		if (adaptiveEnabled && frontierData) {
			const candidate = frontierData?.dueForReview?.[0] || frontierData?.frontier?.[0]
			if (candidate) {
				const lessonId = candidate.lessonId ?? candidate.lesson_id ?? candidate.lessonIdRef
				const found = flatLessons.find((l) => String(l.id) === String(lessonId))
				if (found) return found
				if (lessonId) return { id: lessonId, title: candidate.name }
			}
		}
		return flatLessons.find((l) => !isCompleted(l.id)) || null
	}, [adaptiveEnabled, frontierData, flatLessons, isCompleted])

	const handleStartNext = useCallback(() => {
		if (!nextLesson) return
		goToLesson(courseId, nextLesson.id)
	}, [courseId, goToLesson, nextLesson])

	const dueList = useMemo(
		() => (adaptiveEnabled && Array.isArray(frontierData?.dueForReview) ? frontierData.dueForReview : []),
		[adaptiveEnabled, frontierData]
	)
	const frontierList = useMemo(
		() => (adaptiveEnabled && Array.isArray(frontierData?.frontier) ? frontierData.frontier : []),
		[adaptiveEnabled, frontierData]
	)
	const comingList = useMemo(
		() => (adaptiveEnabled && Array.isArray(frontierData?.comingSoon) ? frontierData.comingSoon : []),
		[adaptiveEnabled, frontierData]
	)

	const inProgressList = useMemo(() => {
		const dueIds = new Set((dueList || []).map((it) => String(it?.id)))
		const all = [...(dueList || []), ...(frontierList || [])]
		const toTs = (it) => {
			const raw = it?.nextReviewAt ?? it?.next_review_at
			if (!raw) return Number.POSITIVE_INFINITY
			const t = Date.parse(raw)
			return Number.isFinite(t) ? t : Number.POSITIVE_INFINITY
		}
		const num = (v, d = 0) => {
			if (v === undefined || v === null) return d
			const n = typeof v === "string" ? Number(v) : v
			return Number.isFinite(n) ? n : d
		}
		const cmp = (a, b) => {
			const aDue = dueIds.has(String(a?.id))
			const bDue = dueIds.has(String(b?.id))
			if (aDue !== bDue) return aDue ? -1 : 1
			if (aDue) {
				const ta = toTs(a)
				const tb = toTs(b)
				if (ta !== tb) return ta - tb
			}
			const ma = num(a?.mastery ?? a?.confidence ?? a?.strength, 0)
			const mb = num(b?.mastery ?? b?.confidence ?? b?.strength, 0)
			if (ma !== mb) return ma - mb
			const da = num(a?.difficulty, 999)
			const db = num(b?.difficulty, 999)
			if (da !== db) return da - db
			const oa = num(a?.order, 999_999)
			const ob = num(b?.order, 999_999)
			if (oa !== ob) return oa - ob
			const na = String(a?.name ?? "")
			const nb = String(b?.name ?? "")
			return na.localeCompare(nb)
		}
		return all.toSorted(cmp)
	}, [dueList, frontierList])

	const idToTitle = useMemo(() => {
		const map = new Map()
		const assign = (id, title) => {
			if (id === undefined || id === null) {
				return
			}
			const normalizedTitle = typeof title === "string" ? title.trim() : ""
			if (normalizedTitle) {
				map.set(String(id), normalizedTitle)
			}
		}

		for (const lesson of flatLessons) {
			assign(lesson?.id, lesson?.title ?? lesson?.name)
		}

		const metadataLessons = Array.isArray(metadata?.lessons) ? metadata.lessons : []
		for (const lesson of metadataLessons) {
			assign(
				lesson?.id ?? lesson?.lessonId ?? lesson?.lesson_id ?? lesson?.lessonIdRef,
				lesson?.title ?? lesson?.name ?? lesson?.label
			)
		}

		for (const list of [dueList, frontierList, comingList]) {
			for (const item of list || []) {
				assign(extractLessonId(item), item?.name ?? item?.title ?? item?.label)
			}
		}

		return map
	}, [flatLessons, metadata, dueList, frontierList, comingList])

	const forecast = useMemo(() => {
		const fromRaw = BuildForecast(rawMetadata)
		if (fromRaw) return fromRaw
		return BuildForecast(metadata)
	}, [metadata, rawMetadata])

	const primaryCtaLabel = "Start"
	const primaryCtaVariant = "outline"

	// Focus mode preference (non-adaptive legacy support)
	const [focusMode] = useState(() => {
		try {
			return localStorage.getItem("talmio_focus_mode") === "1"
		} catch {
			return false
		}
	})
	useEffect(() => {
		try {
			localStorage.setItem("talmio_focus_mode", focusMode ? "1" : "0")
		} catch {}
	}, [focusMode])

	const [showAllUpcoming, setShowAllUpcoming] = useState(false)
	const visibleComingList = useMemo(
		() => (showAllUpcoming ? comingList : comingList.slice(0, 5)),
		[showAllUpcoming, comingList]
	)

	// Non-adaptive: return the original minimal outline view
	if (!adaptiveEnabled) {
		const showModules = !focusMode && modules && modules.length > 0
		return (
			<div className="flex-1 bg-background">
				<div className="mx-auto w-full max-w-4xl px-4 py-6 md:px-6 md:py-8 lg:px-8 lg:py-10">
					<div className="flex flex-col gap-6 md:gap-8 lg:gap-10">
						<section className="rounded-3xl border border-border/70 bg-card/95 shadow-sm ring-1 ring-border/40">
							<div className="flex flex-col gap-6 p-5 md:p-6 lg:p-7">
								<div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
									<div className="min-w-0 flex-1 space-y-2">
										<div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
											Next up
										</div>
										<h2 className="truncate text-lg/tight font-semibold  text-foreground md:text-xl">
											{nextLesson ? nextLesson.title : "All caught up"}
										</h2>
									</div>
									<div className="flex flex-col items-start gap-3 md:flex-row md:items-center md:gap-4">
										<span className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
											<CheckCircle2 className="size-3.5  text-emerald-500" />
											<span>
												Completed {completedCount}/{totalLessons}
											</span>
										</span>
										{nextLesson ? (
											<Button onClick={handleStartNext} variant={primaryCtaVariant} className="h-9 rounded-full px-4">
												<span className="text-sm font-semibold">{primaryCtaLabel}</span>
												<ArrowRight className="size-4 " />
											</Button>
										) : null}
									</div>
								</div>
								{forecast ? (
									<p className="text-xs text-muted-foreground/80">
										Forecast: ~{forecast.weeks >= 2 ? `${forecast.weeks} weeks` : `${forecast.days} days`}
									</p>
								) : null}
							</div>
						</section>

						{showModules ? (
							<section className="flex flex-col gap-4 md:gap-5 lg:gap-6">
								{modules.map((module, idx) => (
									<OutlineNode
										key={module.id || idx}
										module={module}
										index={idx}
										onLessonClick={(_idx, lessonId) => goToLesson(courseId, lessonId)}
										isLessonCompleted={(lessonId) => isCompleted(lessonId)}
										toggleLessonCompletion={(lessonId) => toggleCompletion?.(lessonId, totalLessons)}
									/>
								))}
							</section>
						) : null}
					</div>
				</div>
			</div>
		)
	}

	return (
		<div className="flex-1 bg-background">
			<div className="mx-auto w-full max-w-4xl px-4 py-6 md:px-6 md:py-8 lg:px-8 lg:py-10">
				<div className="flex flex-col gap-6 md:gap-8 lg:gap-10">
					{/* Next Up - Hero Card */}
					<section className="rounded-3xl border border-border/70 bg-card/95 shadow-sm ring-1 ring-border/40">
						<div className="flex flex-col gap-6 p-5 md:p-6 lg:p-7">
							<div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
								<div className="min-w-0 flex-1 space-y-2">
									<div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Next up
									</div>
									<h2 className="truncate text-lg/tight font-semibold  text-foreground md:text-xl">
										{nextLesson ? nextLesson.title : "All caught up"}
									</h2>
								</div>
								<div className="flex flex-col items-start gap-3 md:flex-row md:items-center md:gap-4">
									<span className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
										<CheckCircle2 className="size-3.5  text-emerald-500" />
										<span>
											Completed {completedCount}/{totalLessons}
										</span>
									</span>
									{nextLesson ? (
										<Button onClick={handleStartNext} variant={primaryCtaVariant} className="h-9 rounded-full px-4">
											<span className="text-sm font-semibold">{primaryCtaLabel}</span>
											<ArrowRight className="size-4 " />
										</Button>
									) : null}
								</div>
							</div>
							{forecast ? (
								<p className="text-xs text-muted-foreground/80">
									Forecast: ~{forecast.weeks >= 2 ? `${forecast.weeks} weeks` : `${forecast.days} days`}
								</p>
							) : null}

							{Array.isArray(metadata?.completedLessons) && metadata.completedLessons.length > 0 ? (
								<div className="space-y-2">
									<div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Recent</div>
									<div className="flex flex-wrap gap-2">
										{metadata.completedLessons
											.slice(-4)
											.toReversed()
											.map((id) => {
												const label = idToTitle.get(String(id)) || "Lesson"
												return (
													<button
														key={id}
														type="button"
														onClick={() => goToLesson(courseId, id)}
														className="inline-flex max-w-48 items-center gap-2 rounded-full border border-border/70 bg-muted/50 px-3 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted/70"
														title={label}
													>
														<span className="truncate">{label}</span>
														<ArrowRight className="size-3.5  opacity-60" />
													</button>
												)
											})}
									</div>
								</div>
							) : null}
						</div>
					</section>

					{/* Your Path - Clean numbered modules matching non-adaptive style */}
					{adaptiveEnabled && (dueList.length > 0 || frontierList.length > 0 || comingList.length > 0) ? (
						<section className="flex flex-col gap-4 md:gap-5 lg:gap-6">
							{/* In Progress - single section merging due and frontier */}
							{dueList.length > 0 || frontierList.length > 0 ? (
								<div className="relative overflow-hidden rounded-3xl border border-border/70 bg-card/95 p-5 md:p-6 lg:p-7 shadow-sm transition-shadow hover:shadow-md">
									<div className="mb-5 flex w-full items-center gap-3 md:gap-4">
										<div className="flex size-8  shrink-0 items-center justify-center rounded-full border border-border/70 bg-muted/60 text-sm font-medium text-muted-foreground">
											1
										</div>
										<h2 className="flex-1 truncate text-lg font-semibold text-foreground md:text-xl">In Progress</h2>
									</div>
									<div className="space-y-2.5">
										{inProgressList.map((item, idx) => {
											const lessonId = extractLessonId(item)
											const label = idToTitle.get(String(lessonId)) || item?.name || `Concept ${idx + 1}`
											const mastery = item?.mastery ?? item?.confidence ?? item?.strength ?? 0
											return (
												<div
													key={lessonId || idx}
													className="group flex items-center gap-3 rounded-2xl border border-transparent px-4 py-3 md:px-5 md:py-3.5 transition-colors hover:border-emerald-200 hover:bg-emerald-50/40"
												>
													<MasteryCircle value={mastery} className="shrink-0 text-emerald-600" />
													<button
														type="button"
														onClick={() => lessonId && goToLesson(courseId, lessonId)}
														className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-xl px-2 py-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2"
													>
														<span className="truncate text-sm font-medium text-foreground">{label}</span>
														<ArrowRight className="size-4  text-muted-foreground/60 opacity-0 transition-opacity group-hover:opacity-100" />
													</button>
												</div>
											)
										})}
									</div>
								</div>
							) : null}

							{/* Coming Up - Module 2 */}
							{comingList.length > 0 ? (
								<div className="relative overflow-hidden rounded-3xl border border-border/70 bg-card/95 p-5 md:p-6 lg:p-7 shadow-sm transition-shadow hover:shadow-md">
									<div className="mb-5 flex w-full items-center gap-3 md:gap-4">
										<div className="flex size-8  shrink-0 items-center justify-center rounded-full border border-border/70 bg-muted/60 text-sm font-medium text-muted-foreground">
											{dueList.length > 0 || frontierList.length > 0 ? 2 : 1}
										</div>
										<h2 className="flex-1 truncate text-lg font-semibold text-foreground md:text-xl">Upcoming</h2>
									</div>

									<div className="space-y-2.5">
										{visibleComingList.map((item, idx) => {
											const lessonId = extractLessonId(item)
											const label = idToTitle.get(String(lessonId)) || item?.name || `Concept ${idx + 1}`
											return (
												<div
													key={lessonId || idx}
													className="flex items-center gap-3 rounded-2xl border border-transparent px-4 py-3 md:px-5 md:py-3.5 opacity-60"
												>
													<Circle className="size-5  shrink-0 text-muted-foreground/50" />
													<span className="truncate text-sm font-medium text-muted-foreground">{label}</span>
												</div>
											)
										})}
										{comingList.length > 5 ? (
											<div className="px-4 py-2">
												<button
													type="button"
													onClick={() => setShowAllUpcoming((v) => !v)}
													className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground/80"
												>
													{showAllUpcoming ? "Show less" : `Show all (+${comingList.length - 5})`}
												</button>
											</div>
										) : null}
									</div>
								</div>
							) : null}
						</section>
					) : null}
				</div>
			</div>
		</div>
	)
}

export default OutlineView

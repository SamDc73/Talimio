import { Clock, Download } from "lucide-react"
import { useEffect, useState } from "react"
import { extractVideoChapters, getVideoChapters } from "@/api/videosApi"
import CompletionCheckbox from "@/components/sidebar/CompletionCheckbox"
import ProgressCircle from "@/components/sidebar/ProgressCircle"
import ProgressIndicator from "@/components/sidebar/ProgressIndicator"
import SidebarContainer from "@/components/sidebar/SidebarContainer"
import SidebarNav from "@/components/sidebar/SidebarNav"
import logger from "@/lib/logger"

const formatTime = (seconds) => {
	const hours = Math.floor(seconds / 3600)
	const minutes = Math.floor((seconds % 3600) / 60)
	const secs = Math.floor(seconds % 60)

	if (hours > 0) {
		return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
	}
	return `${minutes}:${secs.toString().padStart(2, "0")}`
}

export function VideoSidebar({ video, currentTime, onSeek, progressPercentage, progressApi }) {
	const [chapters, setChapters] = useState([])
	const [activeChapter, setActiveChapter] = useState(null)
	const [isLoadingChapters, setIsLoadingChapters] = useState(false)
	const [isExtracting, setIsExtracting] = useState(false)
	const [optimisticCompletions, setOptimisticCompletions] = useState({})

	const toggleCompletion = progressApi?.toggleCompletion
	const isCompleted = progressApi?.isCompleted || (() => false)
	const refetch = progressApi?.refetch

	useEffect(() => {
		if (!video?.id) return

		async function fetchChapters() {
			setIsLoadingChapters(true)
			try {
				const apiChapters = await getVideoChapters(video.id)
				if (apiChapters && apiChapters.length > 0) {
					const formattedChapters = apiChapters.map((chapter) => ({
						id: chapter.id,
						timestamp: chapter.startTime,
						timeStr: formatTime(chapter.startTime),
						title: chapter.title,
						chapter_id: chapter.id,
					}))
					setChapters(formattedChapters)
				} else {
					setChapters([])
				}
			} catch (error) {
				if (!error.message?.includes("404")) {
					logger.error("Failed to load video chapters", error, { videoId: video?.id })
				}
				setChapters([])
			} finally {
				setIsLoadingChapters(false)
			}
		}

		fetchChapters()
	}, [video?.id])

	useEffect(() => {
		if (chapters.length > 0 && currentTime !== undefined) {
			const active = chapters.findIndex((chapter, index) => {
				const nextChapter = chapters[index + 1]
				return currentTime >= chapter.timestamp && (!nextChapter || currentTime < nextChapter.timestamp)
			})
			setActiveChapter(active)
		}
	}, [currentTime, chapters])

	const handleChapterClick = (chapter) => {
		if (onSeek) {
			onSeek(chapter.timestamp)
		}
	}

	const toggleChapterCompletion = async (chapter) => {
		const chapterId = chapter.id || chapter.chapter_id

		if (!toggleCompletion) {
			return
		}

		setOptimisticCompletions((prev) => ({
			...prev,
			[chapterId]: !isChapterCompleted(chapterId),
		}))

		try {
			await toggleCompletion(chapterId, chapters.length)
			setOptimisticCompletions((prev) => {
				const newState = { ...prev }
				delete newState[chapterId]
				return newState
			})
		} catch (error) {
			setOptimisticCompletions((prev) => {
				const newState = { ...prev }
				delete newState[chapterId]
				return newState
			})
			logger.error("Failed to toggle chapter completion", error, { chapterId, videoId: video?.id })
		}
	}

	const isChapterCompleted = (chapterId) => {
		if (chapterId in optimisticCompletions) {
			return optimisticCompletions[chapterId]
		}
		return isCompleted(chapterId)
	}

	const handleExtractChapters = async () => {
		setIsExtracting(true)
		try {
			const result = await extractVideoChapters(video.id)
			logger.track("video_chapters_extracted", { videoId: video.id, chapterCount: result?.length || 0 })

			const updatedChapters = await getVideoChapters(video.id)
			if (updatedChapters && updatedChapters.length > 0) {
				const formattedChapters = updatedChapters.map((chapter) => ({
					id: chapter.id,
					timestamp: chapter.startTime,
					timeStr: formatTime(chapter.startTime),
					title: chapter.title,
					chapter_id: chapter.id,
				}))
				setChapters(formattedChapters)
			}

			await refetch?.()
		} catch (error) {
			logger.error("Failed to extract video chapters", error, { videoId: video?.id })
		} finally {
			setIsExtracting(false)
		}
	}

	if (!video) return null

	const completedChapterCount = chapters.filter((chapter) => {
		const chapterId = chapter.id || chapter.chapter_id
		return isChapterCompleted(chapterId)
	}).length

	const isFullyCompleted = chapters.length > 0 && completedChapterCount === chapters.length
	const displayProgress = isFullyCompleted ? 100 : progressPercentage || 0
	const displaySuffix = isFullyCompleted ? "Done" : "Watched"

	return (
		<SidebarContainer data-testid="video-sidebar">
			<ProgressIndicator
				progress={displayProgress}
				variant="video"
				suffix={displaySuffix}
				data-testid="progress-percentage"
			>
				<span className="text-xs text-zinc-500">
					{chapters.length > 0
						? `${completedChapterCount} of ${chapters.length} chapters`
						: `${formatTime(currentTime || 0)} / ${formatTime(video.duration || 0)}`}
				</span>
			</ProgressIndicator>

			<SidebarNav>
				{chapters.length === 0 ? (
					<div className="py-8 px-4 text-center text-muted-foreground">
						<Clock className="size-12  mx-auto mb-4 opacity-50" />
						{isLoadingChapters ? (
							<div>
								<p className="text-sm font-medium">Loading chapters...</p>
								<p className="text-xs mt-2 text-muted-foreground/80">Fetching video chapter data</p>
							</div>
						) : (
							<div>
								<p className="text-sm font-medium">No chapters available</p>
								<p className="text-xs mt-2 text-muted-foreground/80">This video doesn't have chapter markers</p>

								{/* Extract chapters button */}
								<button
									type="button"
									onClick={handleExtractChapters}
									disabled={isExtracting}
									className="mt-4 inline-flex items-center gap-2 rounded-lg bg-video px-4 py-2 text-sm font-medium text-video-text transition-colors hover:bg-video-accent/80 disabled:cursor-not-allowed disabled:opacity-50"
								>
									<Download className="size-4 " />
									{isExtracting ? "Extracting..." : "Extract Chapters"}
								</button>
							</div>
						)}
					</div>
				) : (
					<div className="space-y-2">
						{chapters.map((chapter, index) => {
							const chapterId = chapter.id || chapter.chapter_id
							const chapterCompleted = isChapterCompleted(chapterId)
							const isActive = activeChapter === index

							return (
								<div
									key={chapter.id}
									className={`rounded-2xl border ${
										isActive ? "border-video/40 bg-video/5" : "border-border bg-card"
									} shadow-sm overflow-hidden`}
								>
									<div className="flex items-center gap-3 px-4 py-3">
										<ProgressCircle number={index + 1} progress={chapterCompleted ? 100 : 0} variant="video" />
										<CompletionCheckbox
											isCompleted={chapterCompleted}
											onClick={() => toggleChapterCompletion(chapter)}
											variant="video"
											data-testid={`chapter-checkbox-${index}`}
											asDiv={true}
										/>

										<button
											type="button"
											onClick={() => handleChapterClick(chapter)}
											className="flex-1 text-left group"
										>
											<div className="flex items-center gap-2 mb-1">
												<span
													className={`text-xs font-mono transition-colors ${
														isActive ? "text-video font-semibold" : "text-muted-foreground group-hover:text-video"
													}`}
												>
													{chapter.timeStr}
												</span>
												{chapterCompleted && (
													<span className="text-xs font-medium text-video bg-video/15 px-2 py-0.5 rounded-full">
														Done
													</span>
												)}
											</div>
											<h5
												className={`text-sm font-semibold line-clamp-2 transition-colors ${
													chapterCompleted || isActive ? "text-video" : "text-foreground group-hover:text-video"
												}`}
											>
												{chapter.title}
											</h5>
											{isActive && currentTime !== undefined && (
												<div className="mt-2">
													<div className="h-1 bg-muted rounded-full overflow-hidden">
														<div
															className="h-full bg-video transition-all duration-300"
															style={{
																width: `${Math.min(
																	100,
																	((currentTime - chapter.timestamp) /
																		((chapters[index + 1]?.timestamp || video.duration) - chapter.timestamp)) *
																		100
																)}%`,
															}}
														/>
													</div>
												</div>
											)}
										</button>
									</div>
								</div>
							)
						})}
					</div>
				)}
			</SidebarNav>
		</SidebarContainer>
	)
}

export default VideoSidebar

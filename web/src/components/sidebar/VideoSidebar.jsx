import { Clock, Download } from "lucide-react"

// Helper function to format seconds to time string - outside component to prevent recreating
const formatTime = (seconds) => {
	const hours = Math.floor(seconds / 3600)
	const minutes = Math.floor((seconds % 3600) / 60)
	const secs = Math.floor(seconds % 60)

	if (hours > 0) {
		return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
	}
	return `${minutes}:${secs.toString().padStart(2, "0")}`
}

import { useEffect, useState } from "react"
import { useVideoProgress } from "@/hooks/useVideoProgress"
import logger from "@/lib/logger"
import { extractVideoChapters, getVideoChapters } from "@/services/videosService"
import CompletionCheckbox from "./CompletionCheckbox"
import ProgressCircle from "./ProgressCircle"
import ProgressIndicator from "./ProgressIndicator"
import SidebarContainer from "./SidebarContainer"
import SidebarNav from "./SidebarNav"

export function VideoSidebar({ video, currentTime, onSeek, progressPercentage }) {
	const [chapters, setChapters] = useState([])
	const [activeChapter, setActiveChapter] = useState(null)
	const [isLoadingChapters, setIsLoadingChapters] = useState(false)
	const [isExtracting, setIsExtracting] = useState(false)
	const [optimisticCompletions, setOptimisticCompletions] = useState({})

	// Use the standardized hook
	const { toggleCompletion, isCompleted, refetch } = useVideoProgress(video?.id)

	// Helper function to format seconds to time string - moved outside component to prevent recreating
	// This function is pure and doesn't need to be inside the component

	// Fetch chapters from API only
	useEffect(() => {
		if (!video?.id) return

		async function fetchChapters() {
			setIsLoadingChapters(true)
			try {
				const apiChapters = await getVideoChapters(video.id)
				// Convert API chapters to the expected format
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
				// Log authentication errors for debugging
				if (error.message?.includes("401") || error.message?.includes("Authentication")) {
				} else if (!error.message?.includes("404")) {
				}
				setChapters([])
			} finally {
				setIsLoadingChapters(false)
			}
		}

		fetchChapters()
	}, [video?.id]) // Removed formatTime from deps - it's now a pure function outside component

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

		// Optimistic update - immediately update UI
		setOptimisticCompletions((prev) => ({
			...prev,
			[chapterId]: !isChapterCompleted(chapterId),
		}))

		try {
			// Pass the total chapters count so progress can be calculated correctly
			await toggleCompletion(chapterId, chapters.length)
			// On success, clear the optimistic state (real state will take over)
			setOptimisticCompletions((prev) => {
				const newState = { ...prev }
				delete newState[chapterId]
				return newState
			})
		} catch (error) {
			// On error, revert optimistic update
			setOptimisticCompletions((prev) => {
				const newState = { ...prev }
				delete newState[chapterId]
				return newState
			})
			logger.error("Failed to toggle chapter completion", error, { chapterId, videoId: video?.id })
		}
	}

	// Helper to check if chapter is completed (with optimistic state)
	const isChapterCompleted = (chapterId) => {
		// Check optimistic state first
		if (chapterId in optimisticCompletions) {
			return optimisticCompletions[chapterId]
		}
		// Fall back to actual state
		return isCompleted(chapterId)
	}

	const handleExtractChapters = async () => {
		setIsExtracting(true)
		try {
			const result = await extractVideoChapters(video.id)
			logger.track("video_chapters_extracted", { videoId: video.id, chapterCount: result?.length || 0 })

			// Refresh chapters
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

			// Refresh progress data
			await refetch()
		} catch (error) {
			logger.error("Failed to extract video chapters", error, { videoId: video?.id })
		} finally {
			setIsExtracting(false)
		}
	}

	if (!video) return null

	// Calculate chapter completion progress for the "Done" pill
	// Only show "Done" when ALL chapters are completed
	const completedChapterCount = chapters.filter((chapter) => {
		const chapterId = chapter.id || chapter.chapter_id
		return isChapterCompleted(chapterId)
	}).length

	const _chapterCompletionPercentage =
		chapters.length > 0 ? Math.round((completedChapterCount / chapters.length) * 100) : 0

	// Determine what to show in the progress indicator
	// Show "Done" only when all chapters are completed, otherwise show watch percentage
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
						<Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
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
									className="mt-4 inline-flex items-center gap-2 rounded-lg bg-video px-4 py-2 text-sm font-medium text-video-foreground transition-colors hover:bg-video-accent/80 disabled:cursor-not-allowed disabled:opacity-50"
								>
									<Download className="w-4 h-4" />
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
													chapterCompleted
														? "text-video"
														: isActive
															? "text-video"
															: "text-foreground group-hover:text-video"
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

import { Clock, Download } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { useVideoProgress } from "@/hooks/useVideoProgress";
import {
	extractVideoChapters,
	getVideoChapters,
} from "@/services/videosService";
import CompletionCheckbox from "./CompletionCheckbox";
import ProgressIndicator from "./ProgressIndicator";
import SidebarContainer from "./SidebarContainer";
import SidebarNav from "./SidebarNav";

export function VideoSidebar({ video, currentTime, onSeek }) {
	const [chapters, setChapters] = useState([]);
	const [activeChapter, setActiveChapter] = useState(null);
	const [isLoadingChapters, setIsLoadingChapters] = useState(false);
	const [isExtracting, setIsExtracting] = useState(false);
	const [optimisticCompletions, setOptimisticCompletions] = useState({});
	const { toast } = useToast();

	// Use the standardized hook
	const { progress, toggleCompletion, isCompleted, refetch } = useVideoProgress(
		video?.id,
	);

	// Helper function to format seconds to time string
	const formatTime = useCallback((seconds) => {
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const secs = Math.floor(seconds % 60);

		if (hours > 0) {
			return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
		}
		return `${minutes}:${secs.toString().padStart(2, "0")}`;
	}, []);

	// Fetch chapters from API only
	useEffect(() => {
		if (!video?.id) return;

		async function fetchChapters() {
			setIsLoadingChapters(true);
			try {
				const apiChapters = await getVideoChapters(video.id);
				// Convert API chapters to the expected format
				if (apiChapters && apiChapters.length > 0) {
					const formattedChapters = apiChapters.map((chapter) => ({
						id: chapter.id,
						timestamp: chapter.startTime,
						timeStr: formatTime(chapter.startTime),
						title: chapter.title,
						chapter_id: chapter.id,
					}));
					setChapters(formattedChapters);
				} else {
					setChapters([]);
				}
			} catch (error) {
				// Don't log error if it's expected (404 when no chapters exist)
				if (!error.message?.includes("404")) {
					console.error("Failed to fetch video chapters:", error);
				}
				setChapters([]);
			} finally {
				setIsLoadingChapters(false);
			}
		}

		fetchChapters();
	}, [video?.id, formatTime]);

	useEffect(() => {
		if (chapters.length > 0 && currentTime !== undefined) {
			const active = chapters.findIndex((chapter, index) => {
				const nextChapter = chapters[index + 1];
				return (
					currentTime >= chapter.timestamp &&
					(!nextChapter || currentTime < nextChapter.timestamp)
				);
			});
			setActiveChapter(active);
		}
	}, [currentTime, chapters]);

	const handleChapterClick = (chapter) => {
		if (onSeek) {
			onSeek(chapter.timestamp);
		}
	};

	const toggleChapterCompletion = async (chapter) => {
		const chapterId = chapter.id || chapter.chapter_id;

		// Optimistic update - immediately update UI
		setOptimisticCompletions((prev) => ({
			...prev,
			[chapterId]: !isChapterCompleted(chapterId),
		}));

		try {
			// Pass the total chapters count so progress can be calculated correctly
			await toggleCompletion(chapterId, chapters.length);
			// On success, clear the optimistic state (real state will take over)
			setOptimisticCompletions((prev) => {
				const newState = { ...prev };
				delete newState[chapterId];
				return newState;
			});
		} catch (_error) {
			// On error, revert optimistic update
			setOptimisticCompletions((prev) => {
				const newState = { ...prev };
				delete newState[chapterId];
				return newState;
			});
			toast({
				title: "Error",
				description: "Failed to update chapter progress",
				variant: "destructive",
			});
		}
	};

	// Helper to check if chapter is completed (with optimistic state)
	const isChapterCompleted = (chapterId) => {
		// Check optimistic state first
		if (chapterId in optimisticCompletions) {
			return optimisticCompletions[chapterId];
		}
		// Fall back to actual state
		return isCompleted(chapterId);
	};

	const handleExtractChapters = async () => {
		setIsExtracting(true);
		try {
			const result = await extractVideoChapters(video.id);
			toast({
				title: "Chapters extracted",
				description: `Successfully extracted ${result.count || 0} chapters`,
			});

			// Refresh chapters
			const chapters = await getVideoChapters(video.id);
			setApiChapters(chapters || []);

			// Refresh progress data
			await refetch();
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to extract chapters",
				variant: "destructive",
			});
		} finally {
			setIsExtracting(false);
		}
	};

	if (!video) return null;

	return (
		<SidebarContainer data-testid="video-sidebar">
			<ProgressIndicator
				progress={progress.percentage}
				variant="video"
				suffix="Watched"
				data-testid="progress-percentage"
			/>

			{/* Video info */}
			<div className="px-4 py-3 border-b border-border">
				<h3 className="text-sm font-semibold text-zinc-800 truncate">
					{video.title}
				</h3>
				<p className="text-xs text-zinc-500 mt-1">{video.channel}</p>
			</div>

			<SidebarNav>
				{chapters.length === 0 ? (
					<div className="text-center text-zinc-500 mt-8">
						<Clock className="w-12 h-12 mx-auto mb-4 text-zinc-300" />
						<p className="text-sm">No chapters available</p>
						{!isLoadingChapters && (
							<>
								<p className="text-xs mt-2">
									This video doesn't have chapter markers
								</p>

								{/* Extract chapters button */}
								<button
									type="button"
									onClick={handleExtractChapters}
									disabled={isExtracting}
									className="mt-4 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
								>
									<Download className="w-4 h-4" />
									{isExtracting ? "Extracting..." : "Extract Chapters"}
								</button>
							</>
						)}
					</div>
				) : (
					<div className="space-y-2">
						<h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-2">
							Chapters
						</h4>
						{chapters.map((chapter, index) => {
							const chapterId = chapter.id || chapter.chapter_id;
							const chapterCompleted = isChapterCompleted(chapterId);
							const isActive = activeChapter === index;

							return (
								<div
									key={chapter.id}
									className={`rounded-2xl border ${
										isActive
											? "border-violet-200 bg-violet-50/50"
											: "border-border bg-white"
									} shadow-sm overflow-hidden`}
								>
									<div className="flex items-center gap-3 px-4 py-3">
										<CompletionCheckbox
											isCompleted={chapterCompleted}
											onClick={() => toggleChapterCompletion(chapter)}
											variant="video"
											data-testid={`chapter-checkbox-${index}`}
										/>

										<button
											type="button"
											onClick={() => handleChapterClick(chapter)}
											className="flex-1 text-left"
										>
											<div className="flex items-center gap-2 mb-1">
												<span
													className={`text-xs font-mono ${
														isActive ? "text-violet-600" : "text-zinc-500"
													}`}
												>
													{chapter.timeStr}
												</span>
											</div>
											<h5
												className={`text-sm font-medium line-clamp-2 ${
													chapterCompleted
														? "text-violet-700"
														: isActive
															? "text-violet-600"
															: "text-zinc-700"
												}`}
											>
												{chapter.title}
											</h5>
											{isActive && currentTime !== undefined && (
												<div className="mt-2">
													<div className="h-1 bg-zinc-200 rounded-full overflow-hidden">
														<div
															className="h-full bg-violet-600 transition-all duration-300"
															style={{
																width: `${Math.min(
																	100,
																	((currentTime - chapter.timestamp) /
																		((chapters[index + 1]?.timestamp ||
																			video.duration) -
																			chapter.timestamp)) *
																		100,
																)}%`,
															}}
														/>
													</div>
												</div>
											)}
										</button>
									</div>
								</div>
							);
						})}
					</div>
				)}
			</SidebarNav>

			{/* Footer with video duration */}
			<div className="px-4 py-3 border-t border-border bg-muted">
				<div className="text-xs text-zinc-600">
					<p>Duration: {formatDuration(video.duration)}</p>
					{chapters.length > 0 && (
						<p className="text-zinc-500 mt-1">{chapters.length} chapters</p>
					)}
				</div>
			</div>
		</SidebarContainer>
	);
}

function formatDuration(seconds) {
	if (!seconds) return "Unknown";

	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = Math.floor(seconds % 60);

	if (hours > 0) {
		return `${hours}h ${minutes}m`;
	}
	return `${minutes}m ${secs}s`;
}

export default VideoSidebar;

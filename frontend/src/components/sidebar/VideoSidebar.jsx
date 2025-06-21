import { useToast } from "@/hooks/use-toast";
import {
	extractVideoChapters,
	getVideoChapters,
	syncVideoChapterProgress,
	updateVideoChapterStatus,
} from "@/services/videosService";
import useAppStore from "@/stores/useAppStore";
import { Clock, Download, FileText } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import CompletionCheckbox from "./CompletionCheckbox";
import ProgressIndicator from "./ProgressIndicator";
import SidebarContainer from "./SidebarContainer";
import SidebarNav from "./SidebarNav";

// Stable empty object to prevent infinite re-renders
const EMPTY_CHAPTER_COMPLETION = {};

// Migrate completed chapters from localStorage to Zustand (for backwards compatibility)
const migrateVideoChaptersFromStorage = (videoUuid, setChapterCompletion) => {
	try {
		const saved = localStorage.getItem(`video_chapters_${videoUuid}`);
		if (saved) {
			const completedArray = JSON.parse(saved);
			const completedObj = {};
			completedArray.forEach((chapterId) => {
				completedObj[chapterId] = true;
			});
			setChapterCompletion(videoUuid, completedObj);
			// Clean up localStorage after migration
			localStorage.removeItem(`video_chapters_${videoUuid}`);
		}
	} catch (error) {
		console.error("Failed to migrate completed chapters from storage:", error);
	}
};

export function VideoSidebar({ video, currentTime, onSeek }) {
	const [chapters, setChapters] = useState([]);
	const [apiChapters, setApiChapters] = useState([]);
	const [activeChapter, setActiveChapter] = useState(null);
	const [isLoadingChapters, setIsLoadingChapters] = useState(false);
	const [isExtracting, setIsExtracting] = useState(false);
	const { toast } = useToast();
	const hasSyncedProgress = useRef(false);

	// Zustand store selectors - use shallow comparison to prevent infinite loops
	const {
		updateVideoChapterCompletion,
		setVideoChapterStatus,
		getVideoChapterCompletion,
	} = useAppStore(
		useShallow((state) => ({
			updateVideoChapterCompletion: state.updateVideoChapterCompletion,
			setVideoChapterStatus: state.setVideoChapterStatus,
			getVideoChapterCompletion: state.getVideoChapterCompletion,
		})),
	);

	// Get video chapter completion separately to avoid new object creation
	const videoChapterCompletion = useMemo(() => {
		return video?.uuid
			? getVideoChapterCompletion(video.uuid)
			: EMPTY_CHAPTER_COMPLETION;
	}, [video?.uuid, getVideoChapterCompletion]);

	// Convert store object to Set for backwards compatibility - memoized to prevent infinite loops
	const completedChapters = useMemo(() => {
		const entries = Object.entries(videoChapterCompletion);
		return new Set(
			entries
				.filter(([_, completed]) => completed)
				.map(([chapterId, _]) => chapterId),
		);
	}, [videoChapterCompletion]);

	// Reset sync flag when video changes
	useEffect(() => {
		hasSyncedProgress.current = false;
		// eslint-disable-next-line react-hooks/exhaustive-deps
		// video?.uuid is intentionally the only dependency - we want to reset when video changes
	}, [video?.uuid]);

	// Fetch API chapters
	useEffect(() => {
		if (!video?.uuid) return;

		async function fetchApiChapters() {
			setIsLoadingChapters(true);
			try {
				const chapters = await getVideoChapters(video.uuid);
				setApiChapters(chapters || []);

				if (chapters && chapters.length > 0) {
					// Update completed chapters based on chapter status from API
					const completed = {};
					for (const chapter of chapters) {
						if (chapter.status === "done") {
							completed[chapter.id] = true;
						}
					}
					updateVideoChapterCompletion(video.uuid, completed);
				} else {
					// No API chapters, try to migrate from localStorage for description-based chapters
					migrateVideoChaptersFromStorage(
						video.uuid,
						updateVideoChapterCompletion,
					);
				}
			} catch (error) {
				console.error("Failed to fetch video chapters:", error);
				// Fall back to description extraction and try to migrate from localStorage
				setApiChapters([]);
				migrateVideoChaptersFromStorage(
					video.uuid,
					updateVideoChapterCompletion,
				);
			} finally {
				setIsLoadingChapters(false);
			}
		}

		fetchApiChapters();
	}, [video?.uuid]);

	// Extract chapters from description as fallback
	useEffect(() => {
		if (video?.description && apiChapters.length === 0) {
			const extractedChapters = extractChapters(video.description);
			setChapters(extractedChapters);

			// Migrate from localStorage
			if (extractedChapters.length > 0) {
				migrateVideoChaptersFromStorage(
					video.uuid,
					updateVideoChapterCompletion,
				);
			}
		} else if (apiChapters.length > 0) {
			// Convert API chapters to the expected format
			const formattedChapters = apiChapters.map((chapter) => ({
				id: chapter.id,
				timestamp: chapter.startTime,
				timeStr: formatTime(chapter.startTime),
				title: chapter.title,
				chapter_id: chapter.id,
			}));
			setChapters(formattedChapters);
		}
	}, [
		video?.description,
		apiChapters,
		video?.uuid,
		updateVideoChapterCompletion,
	]);

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

	const extractChapters = (description) => {
		if (!description) return [];

		const timestampRegex =
			/(?:^|\n)(?:[^\d]*)?(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]?\s*(.+?)(?=\n|$)/gm;

		const chapters = [];
		let match;

		match = timestampRegex.exec(description);
		while (match !== null) {
			const timeStr = match[1];
			const title = match[2].trim();

			const parts = timeStr.split(":").map(Number);
			let timestamp = 0;

			if (parts.length === 3) {
				timestamp = parts[0] * 3600 + parts[1] * 60 + parts[2];
			} else if (parts.length === 2) {
				timestamp = parts[0] * 60 + parts[1];
			}

			const cleanTitle = title
				.replace(/^[^\w\s]+\s*/, "")
				.replace(/^\([^)]+\)\s*/, "")
				.trim();

			if (cleanTitle && timestamp >= 0) {
				chapters.push({
					id: `chapter-${timestamp}`,
					timestamp,
					timeStr,
					title: cleanTitle,
				});
			}

			match = timestampRegex.exec(description);
		}

		return chapters.sort((a, b) => a.timestamp - b.timestamp);
	};

	const handleChapterClick = (chapter) => {
		if (onSeek) {
			onSeek(chapter.timestamp);
		}
	};

	const toggleChapterCompletion = async (chapter) => {
		const chapterId = chapter.id || chapter.chapter_id;
		const isCompleted = completedChapters.has(chapterId);
		const newStatus = isCompleted ? "not_started" : "done";

		// Optimistic update to store
		setVideoChapterStatus(video.uuid, chapterId, !isCompleted);

		// Update via API if this is an API chapter
		if (apiChapters.length > 0 && chapter.chapter_id) {
			try {
				await updateVideoChapterStatus(
					video.uuid,
					chapter.chapter_id,
					newStatus,
				);
				toast({
					title: "Chapter updated",
					description: `Chapter marked as ${newStatus.replace("_", " ")}`,
				});
			} catch (error) {
				// Revert optimistic update
				setVideoChapterStatus(video.uuid, chapterId, isCompleted);

				toast({
					title: "Error",
					description: "Failed to update chapter status",
					variant: "destructive",
				});
			}
		} else {
			// This is a description-based chapter, sync to backend
			try {
				// Sync to backend for homepage progress
				const currentCompletion = getVideoChapterCompletion(video.uuid);
				const currentCompleted = Object.entries(currentCompletion)
					.filter(([_, completed]) => completed)
					.map(([chapterId, _]) => chapterId);
				const totalChapters = chapters.length;

				if (totalChapters > 0) {
					// Don't await - let it sync in background
					syncVideoChapterProgress(
						video.uuid,
						currentCompleted,
						totalChapters,
					).catch((error) => {
						console.error("Failed to sync chapter progress to backend:", error);
						// Don't show error to user, this is just for homepage sync
					});
				}

				toast({
					title: "Chapter updated",
					description: `Chapter marked as ${newStatus.replace("_", " ")}`,
				});
			} catch (error) {
				// Revert optimistic update
				setVideoChapterStatus(video.uuid, chapterId, isCompleted);

				toast({
					title: "Error",
					description: "Failed to save chapter progress",
					variant: "destructive",
				});
			}
		}
	};

	const handleExtractChapters = async () => {
		setIsExtracting(true);
		try {
			const result = await extractVideoChapters(video.uuid);
			toast({
				title: "Chapters extracted",
				description: `Successfully extracted ${result.count || 0} chapters`,
			});

			// Refresh chapters
			const chapters = await getVideoChapters(video.uuid);
			setApiChapters(chapters || []);
		} catch (error) {
			toast({
				title: "Error",
				description: "Failed to extract chapters",
				variant: "destructive",
			});
		} finally {
			setIsExtracting(false);
		}
	};

	// Helper function to format seconds to time string
	const formatTime = (seconds) => {
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const secs = Math.floor(seconds % 60);

		if (hours > 0) {
			return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
		}
		return `${minutes}:${secs.toString().padStart(2, "0")}`;
	};

	const getProgress = () => {
		if (chapters.length === 0) return 0;
		return Math.round((completedChapters.size / chapters.length) * 100);
	};

	if (!video) return null;

	return (
		<SidebarContainer>
			<ProgressIndicator
				progress={getProgress()}
				variant="video"
				suffix="Watched"
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
						<p className="text-sm">No chapters found</p>
						<p className="text-xs mt-2">
							Chapters are extracted from the video description
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
					</div>
				) : (
					<div className="space-y-2">
						<h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-2">
							Chapters
						</h4>
						{chapters.map((chapter, index) => {
							const isCompleted = completedChapters.has(chapter.id);
							const isActive = activeChapter === index;

							return (
								<div
									key={chapter.id}
									className={`rounded-2xl border ${
										isActive ? "border-violet-200 bg-violet-50/50" : "border-border bg-white"
									} shadow-sm overflow-hidden`}
								>
									<div className="flex items-center gap-3 px-4 py-3">
										<CompletionCheckbox
											isCompleted={isCompleted}
											onClick={() => toggleChapterCompletion(chapter)}
											variant="video"
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
													isCompleted
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

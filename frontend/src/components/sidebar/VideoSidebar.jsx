import { useSidebar } from "@/features/navigation/SidebarContext";
import { useToast } from "@/hooks/use-toast";
import {
	extractVideoChapters,
	getVideoChapters,
	syncVideoChapterProgress,
	updateVideoChapterStatus,
} from "@/services/videosService";
import { Clock, Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import CompletionCheckbox from "./CompletionCheckbox";
import ProgressIndicator from "./ProgressIndicator";
import SidebarContainer from "./SidebarContainer";
import SidebarNav from "./SidebarNav";

// Load completed chapters from localStorage
const loadCompletedChaptersFromStorage = (videoUuid) => {
	try {
		const saved = localStorage.getItem(`video_chapters_${videoUuid}`);
		return saved ? new Set(JSON.parse(saved)) : new Set();
	} catch (error) {
		console.error("Failed to load completed chapters from storage:", error);
		return new Set();
	}
};

// Save completed chapters to localStorage
const saveCompletedChaptersToStorage = (videoUuid, completedSet) => {
	try {
		localStorage.setItem(
			`video_chapters_${videoUuid}`,
			JSON.stringify([...completedSet]),
		);
	} catch (error) {
		console.error("Failed to save completed chapters to storage:", error);
	}
};

export function VideoSidebar({ video, currentTime, onSeek }) {
	const { isOpen } = useSidebar();
	const [chapters, setChapters] = useState([]);
	const [apiChapters, setApiChapters] = useState([]);
	const [completedChapters, setCompletedChapters] = useState(new Set());
	const [activeChapter, setActiveChapter] = useState(null);
	const [isLoadingChapters, setIsLoadingChapters] = useState(false);
	const [isExtracting, setIsExtracting] = useState(false);
	const { toast } = useToast();

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
					const completed = new Set();
					for (const chapter of chapters) {
						if (chapter.status === "done") {
							completed.add(chapter.id);
						}
					}
					setCompletedChapters(completed);
				} else {
					// No API chapters, load from localStorage for description-based chapters
					const savedCompleted = loadCompletedChaptersFromStorage(video.uuid);
					setCompletedChapters(savedCompleted);
				}
			} catch (error) {
				console.error("Failed to fetch video chapters:", error);
				// Fall back to description extraction and load from localStorage
				setApiChapters([]);
				const savedCompleted = loadCompletedChaptersFromStorage(video.uuid);
				setCompletedChapters(savedCompleted);
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

			// Sync existing localStorage progress to backend
			if (extractedChapters.length > 0) {
				const savedCompleted = loadCompletedChaptersFromStorage(video.uuid);
				if (savedCompleted.size > 0) {
					// Sync existing progress to backend
					syncVideoChapterProgress(
						video.uuid,
						[...savedCompleted],
						extractedChapters.length,
					).catch((error) => {
						console.error(
							"Failed to sync existing chapter progress to backend:",
							error,
						);
					});
				}
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
	}, [video?.description, apiChapters, video?.uuid]);

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

		// Optimistic update
		const newCompletedChapters = new Set(completedChapters);
		if (isCompleted) {
			newCompletedChapters.delete(chapterId);
		} else {
			newCompletedChapters.add(chapterId);
		}
		setCompletedChapters(newCompletedChapters);

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
				setCompletedChapters(completedChapters);

				toast({
					title: "Error",
					description: "Failed to update chapter status",
					variant: "destructive",
				});
			}
		} else {
			// This is a description-based chapter, save to localStorage and sync to backend
			try {
				saveCompletedChaptersToStorage(video.uuid, newCompletedChapters);

				// Sync to backend for homepage progress
				const completedIds = [...newCompletedChapters];
				const totalChapters = chapters.length;

				if (totalChapters > 0) {
					// Don't await - let it sync in background
					syncVideoChapterProgress(
						video.uuid,
						completedIds,
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
				setCompletedChapters(completedChapters);

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
			<ProgressIndicator progress={getProgress()} />

			{/* Video info */}
			<div
				className={`px-4 py-3 border-b border-zinc-200 transition-opacity duration-300 ${
					isOpen ? "opacity-100" : "opacity-0"
				}`}
			>
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
							className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
						>
							<Download className="w-4 h-4" />
							{isExtracting ? "Extracting..." : "Extract Chapters"}
						</button>
					</div>
				) : (
					<div className="space-y-2">
						<div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
							<div className="p-3">
								<h4 className="text-sm font-semibold text-zinc-700 mb-2 flex items-center">
									<FileText className="w-4 h-4 mr-2" />
									Chapters
								</h4>
								<div className="space-y-1">
									{chapters.map((chapter, index) => {
										const isCompleted = completedChapters.has(chapter.id);
										const isActive = activeChapter === index;

										return (
											<div
												key={chapter.id}
												className={`flex items-start gap-3 p-2 rounded-lg transition-all duration-200 ${
													isActive ? "bg-red-50" : "hover:bg-zinc-50"
												}`}
											>
												<CompletionCheckbox
													isCompleted={isCompleted}
													onClick={() => toggleChapterCompletion(chapter)}
												/>

												<div className="flex-1 min-w-0">
													<button
														type="button"
														onClick={() => handleChapterClick(chapter)}
														className="w-full text-left"
													>
														<div className="flex items-center gap-2">
															<span
																className={`text-xs font-mono ${
																	isActive ? "text-red-600" : "text-zinc-500"
																}`}
															>
																{chapter.timeStr}
															</span>
															<h5
																className={`text-sm font-medium truncate ${
																	isCompleted
																		? "text-emerald-700"
																		: isActive
																			? "text-red-900"
																			: "text-zinc-700"
																}`}
															>
																{chapter.title}
															</h5>
														</div>

														{isActive && currentTime !== undefined && (
															<div className="mt-2">
																<div className="h-1 bg-zinc-200 rounded-full overflow-hidden">
																	<div
																		className="h-full bg-red-500 transition-all duration-300"
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
							</div>
						</div>
					</div>
				)}
			</SidebarNav>

			{/* Footer with video duration */}
			<div
				className={`px-4 py-3 border-t border-zinc-200 bg-zinc-50 transition-opacity duration-300 ${
					isOpen ? "opacity-100" : "opacity-0"
				}`}
			>
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

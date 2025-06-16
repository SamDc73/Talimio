import { VideoHeader } from "@/components/header/VideoHeader";
import { VideoSidebar } from "@/components/sidebar";
import { useToast } from "@/hooks/use-toast";
import { videoApi } from "@/services/videoApi";
import useAppStore from "@/stores/useAppStore";
import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import "@justinribeiro/lite-youtube";
import "./VideoViewer.css";

/**
 * Enhanced VideoViewer using Zustand for state management
 * Replaces direct localStorage usage with unified store
 */
function VideoViewerContentV2() {
	const { videoId } = useParams();
	const navigate = useNavigate();
	const { toast } = useToast();
	const isOpen = useAppStore((state) => state.preferences.sidebarOpen);
	const toggleSidebar = useAppStore((state) => state.toggleSidebar);
	const [video, setVideo] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const playerRef = useRef(null);

	// Zustand store selectors
	const videoProgress = useAppStore((state) => state.getVideoProgress(videoId));
	const updateVideoProgress = useAppStore((state) => state.updateVideoProgress);
	const setAppLoading = useAppStore((state) => state.setLoading);
	const addError = useAppStore((state) => state.addError);

	// Local state derived from store
	const [currentTime, setCurrentTime] = useState(
		videoProgress.currentTime || 0,
	);

	/**
	 * Load video data and initialize progress
	 */
	useEffect(() => {
		const loadVideo = async () => {
			if (!videoId) {
				setError("No video ID provided");
				setLoading(false);
				return;
			}

			try {
				setLoading(true);
				setAppLoading("video-fetch", true);
				setError(null);

				console.log("Loading video with ID:", videoId);
				const data = await videoApi.getVideo(videoId);
				console.log("Video loaded:", data);
				setVideo(data);

				// Initialize video duration in store if not already set
				if (!videoProgress.duration && data.duration) {
					updateVideoProgress(videoId, {
						duration: data.duration,
						totalDuration: data.duration,
					});
				}

				// Use stored progress or server progress
				const serverProgress =
					data.progress?.lastPosition || data.lastPosition || 0;
				const localProgress = videoProgress.currentTime || 0;

				// Use more recent progress
				const initialTime =
					localProgress > serverProgress ? localProgress : serverProgress;
				setCurrentTime(initialTime);
			} catch (err) {
				console.error("Failed to load video:", err);
				setError(err.message || "Failed to load video");
				addError(`Failed to load video: ${err.message}`);
				toast({
					title: "Error",
					description: err.message || "Failed to load video. Please try again.",
					variant: "destructive",
				});
			} finally {
				setLoading(false);
				setAppLoading("video-fetch", false);
			}
		};

		loadVideo();
	}, [
		videoId,
		toast,
		updateVideoProgress,
		addError,
		setAppLoading,
		videoProgress.currentTime,
		videoProgress.duration,
	]);

	/**
	 * Handle progress updates with store synchronization
	 */
	const handleProgressUpdate = useCallback(
		async (newCurrentTime) => {
			if (!video) return;

			const progressData = {
				currentTime: Math.floor(newCurrentTime),
				lastPosition: Math.floor(newCurrentTime),
				duration: video.duration,
				lastAccessed: Date.now(),
			};

			// Update store immediately
			updateVideoProgress(videoId, progressData);

			// Also update local state for immediate UI feedback
			setCurrentTime(newCurrentTime);
		},
		[video, videoId, updateVideoProgress],
	);

	/**
	 * Set up YouTube player communication
	 */
	useEffect(() => {
		if (!video || !playerRef.current) return;

		const handleLiteYoutubeActivate = () => {
			// Player is activated (user clicked play)
			const iframe = playerRef.current.querySelector("iframe");
			if (iframe) {
				// Set up postMessage communication with the YouTube iframe
				const intervalId = setInterval(() => {
					iframe.contentWindow?.postMessage(
						JSON.stringify({
							event: "listening",
							id: 1,
							channel: "widget",
						}),
						"*",
					);
				}, 1000);

				// Handle messages from YouTube iframe
				const handleMessage = (event) => {
					if (event.origin !== "https://www.youtube.com") return;

					try {
						const data = JSON.parse(event.data);
						if (
							data.event === "infoDelivery" &&
							data.info &&
							data.info.currentTime !== undefined
						) {
							const newTime = Math.floor(data.info.currentTime);

							// Auto-save progress every 10 seconds of playback
							if (newTime > 0 && newTime % 10 === 0) {
								handleProgressUpdate(newTime);
							} else {
								// Update local state for immediate feedback
								setCurrentTime(newTime);
							}
						}
					} catch (e) {
						// Ignore non-JSON messages
					}
				};

				window.addEventListener("message", handleMessage);

				return () => {
					clearInterval(intervalId);
					window.removeEventListener("message", handleMessage);
				};
			}
		};

		// Listen for when lite-youtube activates
		playerRef.current.addEventListener(
			"liteYoutubeActivate",
			handleLiteYoutubeActivate,
		);

		return () => {
			playerRef.current?.removeEventListener(
				"liteYoutubeActivate",
				handleLiteYoutubeActivate,
			);
		};
	}, [video, handleProgressUpdate]);

	/**
	 * Save progress on page unload using beacon API
	 */
	useEffect(() => {
		const saveProgressOnUnload = () => {
			if (currentTime > 0 && video) {
				// Use sendBeacon for reliable delivery during page unload
				const data = JSON.stringify({
					lastPosition: Math.floor(currentTime),
				});
				navigator.sendBeacon(
					`/api/v1/videos/${videoId}/progress`,
					new Blob([data], { type: "application/json" }),
				);
			}
		};

		const handleBeforeUnload = () => {
			saveProgressOnUnload();
		};

		window.addEventListener("beforeunload", handleBeforeUnload);

		return () => {
			window.removeEventListener("beforeunload", handleBeforeUnload);
			// Also save progress when component unmounts
			saveProgressOnUnload();
		};
	}, [currentTime, video, videoId]);

	/**
	 * Handle seeking to specific chapter/timestamp
	 */
	const handleSeekToChapter = useCallback(
		(timestamp) => {
			const iframe = playerRef.current?.querySelector("iframe");
			if (iframe?.contentWindow) {
				// Use postMessage to control YouTube player
				iframe.contentWindow.postMessage(
					JSON.stringify({
						event: "command",
						func: "seekTo",
						args: [timestamp, true],
					}),
					"*",
				);

				// Update both local state and store
				setCurrentTime(timestamp);
				handleProgressUpdate(timestamp);
			}
		},
		[handleProgressUpdate],
	);

	/**
	 * Calculate progress percentage
	 */
	const progressPercentage =
		video?.duration > 0 ? Math.round((currentTime / video.duration) * 100) : 0;

	/**
	 * Render loading state
	 */
	if (loading) {
		return (
			<div className={`h-screen ${isOpen ? "sidebar-open" : ""}`}>
				<VideoHeader />
				<div className="content-with-sidebar">
					<div className="video-loading">
						<Loader2 className="h-8 w-8 animate-spin" />
						<p>Loading video...</p>
					</div>
				</div>
			</div>
		);
	}

	/**
	 * Render error state
	 */
	if (error || !video) {
		return (
			<div className={`h-screen ${isOpen ? "sidebar-open" : ""}`}>
				<VideoHeader />
				<div className="content-with-sidebar">
					<div className="video-error">
						<p>{error || "Video not found"}</p>
						<button
							type="button"
							onClick={() => navigate("/")}
							className="mt-4"
						>
							Back to Home
						</button>
					</div>
				</div>
			</div>
		);
	}

	return (
		<div className="flex h-screen bg-background">
			<VideoHeader
				video={video}
				currentTime={currentTime}
				progressPercentage={progressPercentage}
				onToggleSidebar={toggleSidebar}
				isSidebarOpen={isOpen}
			/>
			<VideoSidebar
				video={video}
				currentTime={currentTime}
				onSeek={handleSeekToChapter}
				progressPercentage={progressPercentage}
			/>
			<main
				className={`flex-1 transition-all duration-300 ${isOpen ? "ml-80" : "ml-0"} pt-16`}
			>
				<div className="video-player-section">
					<div className="video-player">
						<lite-youtube
							ref={playerRef}
							videoid={video.youtubeId}
							videotitle={video.title}
							posterquality="hqdefault"
							params="rel=0&modestbranding=1&enablejsapi=1&iv_load_policy=3&cc_load_policy=0&fs=0&playsinline=1&disablekb=0"
							autoload
							nocookie
							privacy
						>
							{video.thumbnailUrl && (
								<img slot="image" src={video.thumbnailUrl} alt={video.title} />
							)}
						</lite-youtube>
					</div>

					<div className="video-info">
						<h1 className="video-title">{video.title}</h1>
						<div className="video-metadata">
							<span className="video-channel">{video.channel}</span>
							<span className="video-separator">•</span>
							<span className="video-duration">
								{formatDuration(video.duration)}
							</span>
							<span className="video-separator">•</span>
							<span className="video-progress">
								{formatDuration(currentTime)} / {formatDuration(video.duration)}{" "}
								({progressPercentage}%)
							</span>
							{video.publishedAt && (
								<>
									<span className="video-separator">•</span>
									<span className="video-date">
										{new Date(video.publishedAt).toLocaleDateString()}
									</span>
								</>
							)}
						</div>
						{video.description && (
							<div className="video-description">
								<h3>Description</h3>
								<p>{video.description}</p>
							</div>
						)}
					</div>
				</div>
			</main>
		</div>
	);
}

/**
 * Format duration in HH:MM:SS or MM:SS format
 */
function formatDuration(seconds) {
	if (!seconds) return "Unknown duration";

	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = seconds % 60;

	if (hours > 0) {
		return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
	}
	return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Main VideoViewer component
 */
export default function VideoViewerV2() {
	return <VideoViewerContentV2 />;
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import ErrorBoundary from "@/components/ErrorBoundary";
import RoadmapPromptModal from "@/features/roadmap/RoadmapPromptModal";
import logger from "@/utils/logger";

// Debug logging for Radix UI component initialization
if (import.meta.env.VITE_DEBUG_MODE === "true") {
	logger.debug("Initializing Radix UI components in HomePage");
}

import { AnimatePresence, motion } from "framer-motion";
import {
	Archive,
	ArrowUpDown,
	BookOpen,
	Calendar,
	CalendarDays,
	Check,
	ChevronDown,
	ChevronUp,
	Clock,
	FileText,
	GraduationCap,
	Layers,
	MoreHorizontal,
	Pause,
	Pin,
	Plus,
	Search,
	SlidersHorizontal,
	Sparkles,
	Tag,
	TimerOff,
	X,
	Youtube,
} from "lucide-react";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { ConfirmationDialog } from "@/components/ConfirmationDialog";
import { MainHeader } from "@/components/header/MainHeader";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { RadioGroup, RadioGroupItem } from "@/components/radio-group";
import { Separator } from "@/components/separator";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetFooter,
	SheetHeader,
	SheetTitle,
} from "@/components/sheet";
import TagEditModal from "@/components/TagEditModal";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/tooltip";
import { useToast } from "@/hooks/use-toast";
import { fetchContentData, processContentData } from "@/lib/api";
import { api } from "@/lib/apiClient";
import { archiveContent, unarchiveContent } from "@/services/contentService";
import { deleteApi } from "@/services/deleteApi";
import { videoApi } from "@/services/videoApi";
import useAppStore from "@/stores/useAppStore";

const VARIANTS = {
	course: {
		label: "Course",
		icon: Sparkles,
		badge: "bg-course/10 text-course-text",
		grad: "from-course to-course-accent",
	},
	book: {
		label: "PDF",
		icon: FileText,
		badge: "bg-book/10 text-book-text",
		grad: "from-book to-book-accent",
	},
	youtube: {
		label: "Video",
		icon: Youtube,
		badge: "bg-video/10 text-video-text",
		grad: "from-video to-video-accent",
	},
	flashcards: {
		label: "Flashcards",
		icon: Layers,
		badge: "bg-flashcard/10 text-flashcard-text",
		grad: "from-flashcard to-flashcard-accent",
	},
	roadmap: {
		label: "Course",
		icon: Sparkles,
		badge: "bg-course/10 text-course-text",
		grad: "from-course to-course-accent",
	},
};

const STATES = [
	{
		key: "overdue",
		bg: "bg-overdue/10",
		txt: "text-overdue-text",
		icon: TimerOff,
		msg: "You're late – jump back in",
	},
	{
		key: "today",
		bg: "bg-due-today/10",
		txt: "text-due-today-text",
		icon: Clock,
		msg: "Due today — quick session",
	},
	{
		key: "upcoming",
		bg: "bg-upcoming/10",
		txt: "text-upcoming-text",
		icon: Calendar,
		msg: (d) =>
			`Next check‑in ${d.toLocaleDateString("en-US", { weekday: "long" })}`,
	},
];

const TagChip = ({ tag, contentType }) => (
	<div
		className={`text-xs font-medium px-2 py-1 rounded-full ${
			contentType === "course"
				? "bg-course/10 text-course-text"
				: contentType === "book"
					? "bg-book/10 text-book-text"
					: contentType === "video"
						? "bg-video/10 text-video-text"
						: contentType === "flashcard"
							? "bg-flashcard/10 text-flashcard-text"
							: "bg-muted text-muted-foreground"
		}`}
	>
		{tag}
	</div>
);

const DueDateChip = ({
	dueDate,
	isPaused,
	progress,
	type,
	dueCount = 0,
	overdue = 0,
	onSnooze,
}) => {
	if (
		progress === 100 ||
		(type === "flashcards" && dueCount === 0 && overdue === 0)
	)
		return (
			<motion.div
				initial={{ opacity: 0, scale: 0.9 }}
				animate={{ opacity: 1, scale: 1 }}
				className="bg-completed/10 text-completed-text text-xs font-medium px-2 py-1 rounded-full flex items-center gap-2 whitespace-nowrap"
			>
				<Check className="h-3 w-3" />
				<span>Great streak!</span>
			</motion.div>
		);
	if (isPaused)
		return (
			<motion.div
				initial={{ opacity: 0, scale: 0.9 }}
				animate={{ opacity: 1, scale: 1 }}
				className="bg-paused/10 text-paused-text text-xs font-medium px-2 py-1 rounded-full flex items-center gap-2 whitespace-nowrap"
			>
				<Pause className="h-3 w-3" />
				<span>On hold – resume when free</span>
			</motion.div>
		);
	if (!dueDate) return null;
	const diffHrs = (new Date(dueDate) - Date.now()) / 36e5;
	const stateIdx = diffHrs < 0 ? 0 : diffHrs < 24 ? 1 : 2;
	const state = STATES[stateIdx];
	const base = `${state.bg} ${state.txt} text-xs font-medium px-2 py-1 rounded-full flex items-center gap-2 whitespace-nowrap`;
	const msg =
		typeof state.msg === "function" ? state.msg(new Date(dueDate)) : state.msg;
	return (
		<div className="flex items-center gap-2">
			<motion.div
				initial={{ opacity: 0, scale: 0.9 }}
				animate={{ opacity: 1, scale: 1 }}
				className={base}
			>
				<state.icon className="h-3 w-3" />
				<span>{msg}</span>
			</motion.div>
			{state.btn && (
				<Button
					onClick={onSnooze}
					variant="outline"
					size="sm"
					className="h-6 text-xs px-3"
				>
					Reschedule
				</Button>
			)}
		</div>
	);
};

const BaseCard = ({
	item,
	pinned,
	onTogglePin,
	onDelete,
	onArchive,
	onTagsUpdated,
	index,
	onClick,
}) => {
	const [hover, setHover] = useState(false);
	const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
	const [showTagEditModal, setShowTagEditModal] = useState(false);
	const [isArchiving, setIsArchiving] = useState(false);
	const { toast } = useToast();
	const bookProgressStats = useAppStore((state) =>
		item.type === "book" ? state.books.progressStats[item.id] : null,
	);
	const videoProgress = useAppStore((state) =>
		item.type === "youtube" ? state.videos.progress[item.uuid] : null,
	);

	// Always log archive state for debugging
	// console.log(`🃏 BaseCard for "${item.title}":`, {
	// 	archived: item.archived,
	// 	type: item.type,
	// 	id: item.id || item.uuid,
	// });

	const V = VARIANTS[item.type];
	const isFlashcard = item.type === "flashcards";
	const isBook = item.type === "book";

	const progressValue = useMemo(() => {
		if (isFlashcard) {
			return item.totalCards > 0
				? ((item.totalCards - (item.due || 0) - (item.overdue || 0)) /
						item.totalCards) *
						100
				: 0;
		}
		if (isBook) {
			// Use live progress stats from the store
			if (bookProgressStats) {
				return bookProgressStats.percentage;
			}
			// Fallback to initial item progress if stats are not yet available
			return item.progress || 0;
		}
		if (item.type === "youtube") {
			if (videoProgress && videoProgress.duration > 0) {
				return (videoProgress.currentTime / videoProgress.duration) * 100;
			}
			// Fallback to initial item progress
			return item.progress || 0;
		}
		// For courses and other types, use the progress from the item prop
		return item.progress || item.completionPercentage || 0;
	}, [item, isFlashcard, isBook, bookProgressStats, videoProgress]);

	const handleDeleteClick = () => {
		setShowDeleteConfirm(true);
	};

	const handleConfirmDelete = async () => {
		try {
			const itemType =
				item.type === "youtube"
					? "video"
					: item.type === "flashcards"
						? "flashcard"
						: item.type;
			await deleteApi.deleteItem(itemType, item.id || item.uuid);
			if (onDelete) {
				onDelete(item.id || item.uuid, itemType);
			}
		} catch (error) {
			console.error("Failed to delete item:", error);
		}
	};

	const handleArchive = async () => {
		if (isArchiving) return;

		setIsArchiving(true);
		const contentType = item.type === "flashcards" ? "flashcards" : item.type;
		const isArchived = item.archived || false;

		console.log("📋 Archive operation starting:", {
			itemId: item.id || item.uuid,
			itemTitle: item.title,
			contentType,
			currentArchivedState: isArchived,
			willArchive: !isArchived,
		});

		try {
			if (isArchived) {
				console.log(`🔓 Unarchiving ${contentType}: ${item.title}`);
				await unarchiveContent(contentType, item.id || item.uuid);
				toast({
					title: "Content Unarchived",
					description: `${item.title} has been unarchived successfully.`,
				});
			} else {
				console.log(`📦 Archiving ${contentType}: ${item.title}`);
				await archiveContent(contentType, item.id || item.uuid);
				toast({
					title: "Content Archived",
					description: `${item.title} has been archived successfully.`,
				});
			}

			console.log("✅ Archive operation completed successfully");

			// Notify parent component to refresh content
			if (onArchive) {
				console.log("🔄 Calling onArchive callback to refresh content");
				onArchive(item.id || item.uuid, contentType, !isArchived);
			}
		} catch (error) {
			console.error("❌ Archive operation failed:", error);
			toast({
				title: "Error",
				description: `Failed to ${item.archived ? "unarchive" : "archive"} content. Please try again.`,
				variant: "destructive",
			});
		} finally {
			setIsArchiving(false);
		}
	};

	const handleEditTags = () => {
		setShowTagEditModal(true);
	};

	return (
		<div>
			<motion.div
				layout
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.4, delay: 0.1 * index }}
				whileHover={{ y: -5, transition: { duration: 0.2 } }}
				className={`bg-white rounded-2xl overflow-hidden relative flex flex-col h-full cursor-pointer ${
					pinned
						? "shadow-md border-2 border-primary/10 bg-primary/5"
						: "shadow-sm hover:shadow-md border border-border"
				}`}
				onMouseEnter={() => setHover(true)}
				onMouseLeave={() => setHover(false)}
				onClick={onClick}
			>
				{pinned && (
					<div className="absolute top-0 left-6 w-6 h-1 bg-primary rounded-b-full" />
				)}
				<div className="p-6 flex flex-col justify-between h-full">
					<div className="flex justify-between items-start mb-4">
						<div
							className={`${V.badge} text-xs font-medium px-3 py-1 rounded-full flex items-center gap-2`}
						>
							<V.icon className="h-3 w-3" />
							<span>{V.label}</span>
						</div>
					</div>
					<h3 className="text-xl font-display font-bold text-foreground hover:underline line-clamp-2 mb-1">
						{item.title}
					</h3>

					{/* Video metadata */}
					{item.type === "youtube" && (
						<p className="text-muted-foreground text-sm mb-4">
							by {item.channelName || item.channel || "Unknown Channel"} •{" "}
							{formatDuration(item.duration)}
						</p>
					)}

					{/* Book metadata */}
					{item.type === "book" && (
						<p className="text-muted-foreground text-sm mb-4">
							by {item.author || "Unknown Author"} •{" "}
							{item.pageCount || item.pages || "Unknown"} pages
						</p>
					)}

					{/* Description for other types */}
					{item.type !== "youtube" &&
						item.type !== "book" &&
						item.description && (
							<p className="text-muted-foreground text-sm line-clamp-2 mb-4">
								{item.description}
							</p>
						)}

					<div className="flex flex-wrap items-center gap-2 mb-3">
						{item.tags?.slice(0, 2).map((t) => (
							<TagChip key={t} tag={t} contentType={item.type} />
						))}
						{item.tags?.length > 2 && (
							<span className="inline-flex text-xs font-medium bg-muted text-muted-foreground px-2 py-0.5 rounded">
								+{item.tags.length - 2}
							</span>
						)}
						<DueDateChip
							dueDate={item.dueDate}
							isPaused={item.isPaused}
							progress={progressValue}
							type={item.type}
							dueCount={item.due || item.dueCount}
							overdue={item.overdue}
							onSnooze={(e) => {
								e.stopPropagation();
								alert(`Rescheduled: ${item.title}`);
							}}
						/>
					</div>
					<div>
						{isFlashcard && (
							<div className="flex justify-between text-xs text-muted-foreground mb-2">
								<span>
									{item.overdue > 0 && (
										<>
											<span className="text-overdue-text font-medium">
												{item.overdue} overdue
											</span>
											<span className="text-muted-foreground mx-1">•</span>
										</>
									)}
									<span>{item.totalCards || item.cardCount || 0} cards</span>
								</span>
							</div>
						)}
						{!isFlashcard && progressValue != null && progressValue !== "" && (
							<div className="flex justify-between text-xs text-muted-foreground mb-2">
								<span>{Math.round(progressValue)}%</span>
							</div>
						)}
						<div className="w-full bg-muted rounded-full h-2">
							<motion.div
								initial={{ width: 0 }}
								animate={{ width: `${progressValue}%` }}
								transition={{ duration: 0.6 }}
								className={`h-2 rounded-full bg-gradient-to-r ${V.grad}`}
							/>
						</div>
					</div>
				</div>
				{hover && (
					<div className="absolute top-4 right-4 z-10">
						<Popover>
							<PopoverTrigger asChild onClick={(e) => e.stopPropagation()}>
								<Button
									variant="ghost"
									size="icon"
									className="h-10 w-10 rounded-full"
								>
									<MoreHorizontal className="h-4 w-4" />
								</Button>
							</PopoverTrigger>
							<PopoverContent align="end" className="w-40 p-0">
								<div className="flex flex-col text-sm">
									{[
										"Pin",
										"Edit Tags",
										"Archive",
										"sep",
										"Pause",
										"Delete",
									].map((action) =>
										action === "sep" ? (
											<Separator key="separator" />
										) : (
											<Button
												key={action}
												variant="ghost"
												size="sm"
												className={`justify-start flex items-center gap-2 ${
													action === "Delete"
														? "text-red-600 hover:bg-red-50"
														: ""
												}`}
												onClick={(e) => {
													e.stopPropagation();
													if (action === "Pin") onTogglePin();
													else if (action === "Delete") handleDeleteClick();
													else if (action === "Archive") handleArchive();
													else if (action === "Pause")
														console.log("Pause functionality - placeholder");
													else if (action === "Edit Tags") handleEditTags();
												}}
												disabled={action === "Archive" && isArchiving}
											>
												{action === "Pin" && <Pin className="h-4 w-4" />}
												{action === "Edit Tags" && <Tag className="h-4 w-4" />}
												{action === "Archive" && (
													<Archive className="h-4 w-4" />
												)}
												{action === "Pause" && <Pause className="h-4 w-4" />}
												{action === "Delete" && <X className="h-4 w-4" />}
												{action === "Pin"
													? pinned
														? "Unpin"
														: "Pin"
													: action === "Archive"
														? isArchiving
															? "Processing..."
															: item.archived
																? "Unarchive"
																: "Archive"
														: action}
											</Button>
										),
									)}
								</div>
							</PopoverContent>
						</Popover>
					</div>
				)}
			</motion.div>

			<ConfirmationDialog
				open={showDeleteConfirm}
				onOpenChange={setShowDeleteConfirm}
				title="Delete Item"
				description="This action cannot be undone. This item will be permanently removed from your library."
				itemName={item.title}
				onConfirm={handleConfirmDelete}
			/>

			<TagEditModal
				open={showTagEditModal}
				onOpenChange={setShowTagEditModal}
				contentType={
					item.type === "youtube"
						? "video"
						: item.type === "flashcards"
							? "flashcard"
							: item.type
				}
				contentId={item.id || item.uuid}
				contentTitle={item.title}
				onTagsUpdated={onTagsUpdated}
			/>
		</div>
	);
};

function formatDuration(seconds) {
	if (!seconds) return "Unknown duration";

	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = Math.round(seconds % 60);

	if (hours > 0) {
		return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
	}
	return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export default function HomePage() {
	if (import.meta.env.VITE_DEBUG_MODE === "true") {
		console.log("[Debug] Rendering HomePage component");
	}
	const { toast } = useToast();
	const _navigate = useNavigate();
	const [searchQuery, setSearchQuery] = useState("");
	const [isGenerateMode, setIsGenerateMode] = useState(false);
	const [isGenerating, setIsGenerating] = useState(false);
	const [showUploadDialog, setShowUploadDialog] = useState(false);
	const [showYoutubeDialog, setShowYoutubeDialog] = useState(false);
	const [selectedFile, setSelectedFile] = useState(null);
	const [bookTitle, setBookTitle] = useState("");
	const [bookAuthor, setBookAuthor] = useState("");
	const [isExtractingMetadata, setIsExtractingMetadata] = useState(false);
	const [isUploadingBook, setIsUploadingBook] = useState(false);
	const [youtubeUrl, setYoutubeUrl] = useState("");
	const [isAddingVideo, setIsAddingVideo] = useState(false);
	const [isFabExpanded, setIsFabExpanded] = useState(false);
	const [showFlashcardDialog, setShowFlashcardDialog] = useState(false);
	const [newDeckTitle, setNewDeckTitle] = useState("");
	const [newDeckDescription, setNewDeckDescription] = useState("");
	const [newCards, setNewCards] = useState("");
	const [isYoutubeMode, setIsYoutubeMode] = useState(false);
	const [activeFilter, setActiveFilter] = useState("all");
	const [activeSort, setActiveSort] = useState("last-accessed");
	const [sortDirection, setSortDirection] = useState("desc");
	const [archiveFilter, setArchiveFilter] = useState("active"); // "active", "archived", "all"
	const [tagFilter, setTagFilter] = useState("");
	const [contentItems, setContentItems] = useState([]);
	const [filterOptions, setFilterOptions] = useState([]);
	const [sortOptions, setSortOptions] = useState([]);
	const [isLoading, setIsLoading] = useState(true);
	const [pins, setPins] = useState({});
	const [showAll, setShowAll] = useState(false);
	const [showRoadmapModal, setShowRoadmapModal] = useState(false);

	// Load content data function - memoized with useCallback to prevent recreating on every render
	const loadContentData = useCallback(async () => {
		setIsLoading(true);
		try {
			// Include archived content if we're showing archived or all content
			const includeArchived =
				archiveFilter === "archived" || archiveFilter === "all";
			console.log(
				`🔄 Loading content data with archiveFilter: ${archiveFilter}, includeArchived: ${includeArchived}`,
			);

			const data = await fetchContentData(includeArchived);
			console.log("📦 Raw API data received:", data);

			const {
				content,
				filterOptions: options,
				sortOptions: sortOpts,
			} = processContentData(data);

			console.log("⚙️ Processed content:", content);
			console.log("📊 Archive status breakdown:", {
				total: content.length,
				archived: content.filter((item) => item.archived).length,
				active: content.filter((item) => !item.archived).length,
			});

			// Batch process tags to avoid too many concurrent requests
			// Process in chunks of 5 to prevent overwhelming the browser
			const BATCH_SIZE = 5;
			const transformedContent = [];

			for (let i = 0; i < content.length; i += BATCH_SIZE) {
				const batch = content.slice(i, i + BATCH_SIZE);
				const batchResults = await Promise.all(
					batch.map(async (item) => {
						// Load tags from tag associations for each item
						let tags = [];
						try {
							const contentType =
								item.type === "youtube"
									? "video"
									: item.type === "flashcards"
										? "flashcard"
										: item.type === "course"
											? "roadmap" // Map course to roadmap for tags API
											: item.type;
							const contentId = item.id || item.uuid;
							if (contentId && contentType) {
								const response = await fetch(
									`/api/tags/${contentType}/${contentId}/tags`,
								);
								if (response.ok) {
									const tagData = await response.json();
									tags = tagData.map((tag) => tag.name);
								}
							}
						} catch (error) {
							console.log(`Could not load tags for ${item.title}:`, error);
						}

						return {
							...item,
							tags, // Use tags from tag associations instead of book endpoint
							// Add mock due dates and states for demonstration
							dueDate:
								Math.random() > 0.7
									? new Date(
											Date.now() +
												(Math.random() * 7 - 2) * 24 * 60 * 60 * 1000,
										).toISOString()
									: null,
							isPaused: Math.random() > 0.9,
							// For flashcards, map the existing fields
							totalCards: item.cardCount,
							due: item.dueCount || Math.floor(Math.random() * 10),
							overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
						};
					}),
				);
				transformedContent.push(...batchResults);
			}

			const courseItems = transformedContent.filter(
				(item) => item.type === "course",
			);
			if (courseItems.length > 0) {
				// Use Promise.allSettled to handle individual API failures gracefully
				const courseProgressPromises = courseItems.map((course) =>
					api.get(`/courses/${course.id}/progress`).catch((error) => {
						console.error(
							`Failed to fetch progress for course ${course.id}:`,
							error,
						);
						// Return a default progress object for failed requests
						return {
							completion_percentage: 0,
							total_lessons: 0,
							completed_lessons: 0,
							error: true,
						};
					}),
				);
				const courseProgresses = await Promise.all(courseProgressPromises);

				console.log("🎯 Course progress API responses:", courseProgresses);

				const coursesWithProgress = courseItems.map((course, index) => ({
					...course,
					progress: courseProgresses[index].completion_percentage || 0, // Fixed: Remove .data since apiClient returns direct JSON
				}));

				const contentWithProgress = transformedContent.map((item) => {
					if (item.type === "course") {
						const courseWithProgress = coursesWithProgress.find(
							(c) => c.id === item.id,
						);
						return courseWithProgress || item;
					}
					return item;
				});
				setContentItems(contentWithProgress);
			} else {
				setContentItems(transformedContent);
			}

			// Map the filter options with their icons
			setFilterOptions(
				options.map((option) => {
					const getIcon = () => {
						switch (option.icon) {
							case "Search":
								return <Search className="h-4 w-4 mr-2" />;
							case "BookOpen":
								return <BookOpen className="h-4 w-4 mr-2" />;
							case "FileText":
								return <FileText className="h-4 w-4 mr-2" />;
							case "Youtube":
								return <Youtube className="h-4 w-4 mr-2" />;
							case "Layers":
								return <Layers className="h-4 w-4 mr-2" />;
							default:
								return <Search className="h-4 w-4 mr-2" />;
						}
					};

					return {
						...option,
						icon: getIcon(),
					};
				}),
			);

			// Map the sort options with their icons
			setSortOptions(
				sortOpts.map((option) => {
					const getIcon = () => {
						switch (option.icon) {
							case "Clock":
								return <Clock className="h-4 w-4 mr-2" />;
							case "CalendarDays":
								return <CalendarDays className="h-4 w-4 mr-2" />;
							case "ArrowUpDown":
								return <ArrowUpDown className="h-4 w-4 mr-2" />;
							case "FileText":
								return <FileText className="h-4 w-4 mr-2" />;
							default:
								return <Clock className="h-4 w-4 mr-2" />;
						}
					};

					return {
						...option,
						icon: getIcon(),
					};
				}),
			);

			// Initialize pins state
			const initialPins = {};
			for (const item of transformedContent) {
				if (!initialPins[item.type]) initialPins[item.type] = [];
			}
			setPins(initialPins);
		} catch (error) {
			console.error("Error loading content data:", error);
			toast({
				title: "Error",
				description: "Failed to load content. Please refresh the page.",
				variant: "destructive",
			});
		} finally {
			setIsLoading(false);
		}
	}, [archiveFilter, toast]);

	// Fetch content data on component mount and when archive filter changes
	useEffect(() => {
		loadContentData();
	}, [archiveFilter, loadContentData]);

	// Listen for course progress updates with throttling to prevent cascading updates
	useEffect(() => {
		let refreshTimeout = null;

		const handleCourseProgressRefresh = async (event) => {
			// Clear any pending refresh
			if (refreshTimeout) {
				clearTimeout(refreshTimeout);
			}

			// Throttle refresh to prevent cascading updates and infinite loops
			refreshTimeout = setTimeout(async () => {
				const { courseId } = event.detail;
				console.log(
					`🔄 Course progress refresh triggered for course ${courseId}`,
				);

				// Refetch the specific course's progress and update only that course in contentItems
				try {
					const response = await api.get(`/courses/${courseId}/progress`);
					const updatedProgress = response.completion_percentage || 0;

					// Update only the specific course in contentItems
					setContentItems((prevItems) =>
						prevItems.map((item) =>
							item.type === "course" && item.id === courseId
								? { ...item, progress: updatedProgress }
								: item,
						),
					);
				} catch (error) {
					console.error(
						`Failed to refresh progress for course ${courseId}:`,
						error,
					);
				}
			}, 500); // 500ms throttle to prevent rapid refreshes
		};

		// Add event listener
		window.addEventListener(
			"courseProgressRefresh",
			handleCourseProgressRefresh,
		);

		// Cleanup
		return () => {
			if (refreshTimeout) {
				clearTimeout(refreshTimeout);
			}
			window.removeEventListener(
				"courseProgressRefresh",
				handleCourseProgressRefresh,
			);
		};
	}, []);

	// Also listen for course progress updates (when progress is explicitly set) with throttling
	useEffect(() => {
		let updateTimeout = null;

		const handleCourseProgressUpdate = (event) => {
			// Clear any pending update
			if (updateTimeout) {
				clearTimeout(updateTimeout);
			}

			// Throttle updates to prevent cascading updates and infinite loops
			updateTimeout = setTimeout(() => {
				const { courseId, progressStats } = event.detail;
				console.log(
					`📊 Course progress updated for course ${courseId}:`,
					progressStats,
				);

				// Update the specific course in contentItems with the new progress
				setContentItems((prevItems) =>
					prevItems.map((item) =>
						item.type === "course" && item.id === courseId
							? { ...item, progress: progressStats.completion_percentage || 0 }
							: item,
					),
				);
			}, 300); // 300ms throttle for updates
		};

		// Add event listener
		window.addEventListener("courseProgressUpdate", handleCourseProgressUpdate);

		// Cleanup
		return () => {
			if (updateTimeout) {
				clearTimeout(updateTimeout);
			}
			window.removeEventListener(
				"courseProgressUpdate",
				handleCourseProgressUpdate,
			);
		};
	}, []);

	// Apply filters and sorting with memoization to prevent infinite re-renders
	const filteredAndSortedContent = useMemo(() => {
		return (Array.isArray(contentItems) ? contentItems : [])
			.filter((item) => {
				// Apply content type filter
				if (activeFilter === "all") return true;
				if (activeFilter === "course")
					return item.type === "course" || item.type === "roadmap";
				return item.type === activeFilter;
			})
			.filter((item) => {
				// Apply archive filter
				const isArchived = Boolean(item.archived);
				if (archiveFilter === "active") return !isArchived;
				if (archiveFilter === "archived") return isArchived;
				return true; // "all" shows both archived and active
			})
			.filter((item) => {
				if (!searchQuery) return true;

				const query = searchQuery.toLowerCase();
				const title = item.title.toLowerCase();
				const tags = item.tags
					? item.tags.some((tag) => tag.toLowerCase().includes(query))
					: false;

				if (item.type === "course") {
					return (
						title.includes(query) ||
						item.description.toLowerCase().includes(query) ||
						tags
					);
				}
				if (item.type === "book") {
					return (
						title.includes(query) ||
						item.author?.toLowerCase().includes(query) ||
						tags
					);
				}
				if (item.type === "youtube") {
					const channelName = item.channelName || item.channel || "";
					return (
						title.includes(query) ||
						channelName?.toLowerCase().includes(query) ||
						tags
					);
				}
				if (item.type === "flashcards") {
					return (
						title.includes(query) ||
						item.description.toLowerCase().includes(query) ||
						tags
					);
				}
				return true;
			})
			.filter((item) => {
				// Apply tag filter
				if (!tagFilter) return true;

				return item.tags?.some((tag) =>
					tag.toLowerCase().includes(tagFilter.toLowerCase()),
				);
			})
			.sort((a, b) => {
				const direction = sortDirection === "asc" ? 1 : -1;

				switch (activeSort) {
					case "last-accessed":
						return (
							direction *
							(new Date(a.lastAccessedDate).getTime() -
								new Date(b.lastAccessedDate).getTime())
						);
					case "created":
						return (
							direction *
							(new Date(a.createdDate).getTime() -
								new Date(b.createdDate).getTime())
						);
					case "progress":
						return direction * (a.progress - b.progress);
					case "title":
						return direction * a.title.localeCompare(b.title);
					default:
						return 0;
				}
			});
	}, [
		contentItems,
		activeFilter,
		archiveFilter,
		searchQuery,
		tagFilter,
		sortDirection,
		activeSort,
	]);

	// Removed debug logging for performance

	const handleGenerateCourse = async () => {
		if (!searchQuery.trim()) return;

		setIsGenerating(true);

		try {
			const _response = await api.post("/assistant/generate-course", {
				topic: searchQuery,
				level: "beginner",
			});

			toast({
				title: "Course Generated!",
				description: `Successfully created a course on "${searchQuery}".`,
			});

			setSearchQuery("");
			setIsGenerateMode(false);

			// Refresh content list
			const data = await fetchContentData();
			const { content } = processContentData(data);
			setContentItems(
				content.map((item) => ({
					...item,
					dueDate:
						Math.random() > 0.7
							? new Date(
									Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000,
								).toISOString()
							: null,
					isPaused: Math.random() > 0.9,
					totalCards: item.cardCount,
					due: item.dueCount || Math.floor(Math.random() * 10),
					overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
				})),
			);
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to generate course. Please try again.",
				variant: "destructive",
			});
		} finally {
			setIsGenerating(false);
		}
	};

	const toggleSortDirection = () => {
		setSortDirection(sortDirection === "asc" ? "desc" : "asc");
	};

	const getActiveFilterLabel = () => {
		return (
			filterOptions.find((option) => option.id === activeFilter)?.label ||
			"All Content"
		);
	};

	const getActiveSortLabel = () => {
		return (
			sortOptions.find((option) => option.id === activeSort)?.label ||
			"Last Opened"
		);
	};

	// Handle roadmap creation success
	const handleRoadmapCreated = async (_newRoadmap) => {
		try {
			// Refresh content list to include the new roadmap
			await loadContentData();
			toast({
				title: "Course Created!",
				description: "Your new course has been created successfully.",
			});
		} catch (error) {
			console.error("Error refreshing content after roadmap creation:", error);
			toast({
				title: "Error",
				description: "Failed to refresh content list. Please reload the page.",
				variant: "destructive",
			});
		}
	};

	const togglePin = (type, id) =>
		setPins((p) => ({
			...p,
			[type]: p[type].includes(id)
				? p[type].filter((x) => x !== id)
				: [...p[type], id],
		}));

	const priority = useCallback((i) => {
		if (
			i.progress === 100 ||
			(i.type === "flashcards" && i.due === 0 && i.overdue === 0)
		)
			return 5;
		if (i.isPaused) return 3;
		if (!i.dueDate) return 4;
		const h = (new Date(i.dueDate) - Date.now()) / 36e5;
		return h < 0 ? 1 : h < 24 ? 2 : 4;
	}, []);

	const unpinned = filteredAndSortedContent.filter(
		(i) => !pins[i.type]?.includes(i.id),
	);
	const visible = showAll ? unpinned : unpinned.slice(0, 3);

	const [celebrate, setCelebrate] = useState(false);
	useEffect(() => {
		if (unpinned.length && unpinned.every((i) => priority(i) === 5)) {
			setCelebrate(true);
			const t = setTimeout(() => setCelebrate(false), 5000);
			return () => clearTimeout(t);
		}
	}, [unpinned, priority]);

	const handleCardClick = (item) => {
		// Navigate to the appropriate page based on item type
		if (item.type === "course" || item.type === "roadmap") {
			// Use the new course routes for both course and roadmap types
			_navigate(`/course/${item.id}`);
		} else if (item.type === "youtube") {
			_navigate(`/videos/${item.uuid || item.id}`);
		} else if (item.type === "book") {
			_navigate(`/books/${item.id}`);
		} else if (item.type === "flashcards") {
			_navigate(`/flashcards/${item.id}`);
		}
	};

	const handleDeleteItem = (itemId, itemType) => {
		// Remove the item from content state
		setContentItems((prevContent) =>
			prevContent.filter((item) => item.id !== itemId && item.uuid !== itemId),
		);

		// Remove from pins if it was pinned
		setPins((prevPins) => {
			const newPins = { ...prevPins };
			for (const type of Object.keys(newPins)) {
				newPins[type] = newPins[type].filter((id) => id !== itemId);
			}
			return newPins;
		});

		// Show success toast
		toast({
			title: "Item deleted",
			description: `${itemType} has been successfully deleted.`,
		});
	};

	const handleArchiveItem = async (itemId, contentType, newArchivedState) => {
		// Refresh content to get updated state
		console.log("🔄 handleArchiveItem called:", {
			itemId,
			contentType,
			newArchivedState,
			currentArchiveFilter: archiveFilter,
		});

		try {
			// Include archived content if we're showing archived or all content
			const includeArchived =
				archiveFilter === "archived" || archiveFilter === "all";
			console.log(
				`📡 Refreshing content with includeArchived: ${includeArchived}`,
			);

			const data = await fetchContentData(includeArchived);
			console.log("📦 Refresh - Raw API data:", data);

			const {
				content,
				filterOptions: options,
				sortOptions: sortOpts,
			} = processContentData(data);

			console.log("⚙️ Refresh - Processed content:", content);

			// Transform data to match new structure (same as initial load)
			const transformedContent = content.map((item) => ({
				...item,
				// Add mock due dates and states for demonstration
				dueDate:
					Math.random() > 0.7
						? new Date(
								Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000,
							).toISOString()
						: null,
				isPaused: Math.random() > 0.9,
				// For flashcards, map the existing fields
				totalCards: item.cardCount,
				due: item.dueCount || Math.floor(Math.random() * 10),
				overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
			}));

			setContentItems(transformedContent);
			setFilterOptions(options);
			setSortOptions(sortOpts);
		} catch (error) {
			console.error("Failed to refresh content after archive:", error);
		}
	};

	const handleTagsUpdated = async (itemId, _contentType, newTags) => {
		// Update the specific item's tags in the content list
		setContentItems((prevItems) => {
			return prevItems.map((item) => {
				if (item.id === itemId || item.uuid === itemId) {
					return {
						...item,
						tags: newTags,
					};
				}
				return item;
			});
		});
	};

	const renderCard = (item, i) => (
		<BaseCard
			key={item.id}
			item={item}
			index={i}
			pinned={pins[item.type]?.includes(item.id)}
			onTogglePin={() => togglePin(item.type, item.id)}
			onDelete={handleDeleteItem}
			onArchive={handleArchiveItem}
			onTagsUpdated={handleTagsUpdated}
			onClick={() => handleCardClick(item)}
		/>
	);

	const pinnedItems = Object.entries(pins).flatMap(([type, ids]) =>
		filteredAndSortedContent.filter(
			(x) => x.type === type && ids.includes(x.id),
		),
	);

	const handleFileChange = async (e) => {
		const file = e.target.files?.[0];
		if (file) {
			setSelectedFile(file);
			setIsExtractingMetadata(true);

			// Extract metadata from the file
			try {
				const formData = new FormData();
				formData.append("file", file);

				const response = await fetch("/api/v1/books/extract-metadata", {
					method: "POST",
					body: formData,
				});

				if (!response.ok) {
					throw new Error(`HTTP error! status: ${response.status}`);
				}

				const metadata = await response.json();

				// Pre-populate fields with extracted metadata
				if (metadata.title) {
					setBookTitle(metadata.title);
				}
				if (metadata.author) {
					setBookAuthor(metadata.author);
				}
				toast({
					title: "Metadata Extracted",
					description:
						"Book information has been auto-populated. You can edit if needed.",
				});
			} catch (error) {
				console.error("Failed to extract metadata:", error);
				// If extraction fails, use filename as title
				const titleFromFilename = file.name.replace(/\.[^/.]+$/, "");
				setBookTitle(titleFromFilename);
			} finally {
				setIsExtractingMetadata(false);
			}
		}
	};

	const handleUpload = async () => {
		if (!selectedFile || !bookTitle.trim() || !bookAuthor.trim()) return;

		setIsUploadingBook(true);
		try {
			const formData = new FormData();
			formData.append("file", selectedFile);
			formData.append("title", bookTitle);
			formData.append("author", bookAuthor);
			formData.append("tags", JSON.stringify([]));

			const response = await fetch("/api/v1/books", {
				method: "POST",
				body: formData,
			});

			if (!response.ok) {
				const errorData = await response.json();
				if (response.status === 409) {
					// Duplicate file error
					toast({
						title: "Duplicate Book",
						description:
							errorData.detail || "This book already exists in your library.",
						variant: "destructive",
					});
					return;
				}
				throw new Error(
					errorData.detail || `HTTP error! status: ${response.status}`,
				);
			}

			// Parse the response to get the book data
			const bookData = await response.json();

			// Close the dialog first
			setShowUploadDialog(false);
			setSelectedFile(null);
			setBookTitle("");
			setBookAuthor("");

			toast({
				title: "Book Uploaded!",
				description: `"${bookTitle}" by ${bookAuthor} has been added to your library.`,
			});

			// Small delay to ensure dialog closes before navigation
			setTimeout(() => {
				_navigate(`/books/${bookData.id}`);
			}, 100);
		} catch (error) {
			setIsUploadingBook(false);
			toast({
				title: "Error",
				description:
					error.message || "Failed to upload book. Please try again.",
				variant: "destructive",
			});
		}
	};

	const handleYoutubeAdd = async () => {
		if (
			!youtubeUrl.trim() ||
			(!youtubeUrl.includes("youtube.com") && !youtubeUrl.includes("youtu.be"))
		) {
			toast({
				title: "Invalid URL",
				description: "Please enter a valid YouTube URL",
				variant: "destructive",
			});
			return;
		}

		if (isAddingVideo) return; // Prevent duplicate submissions

		setIsAddingVideo(true);
		try {
			const response = await videoApi.createVideo(youtubeUrl);

			toast({
				title: response.alreadyExists ? "Video Found!" : "Video Added!",
				description: response.alreadyExists
					? `"${response.title}" was already in your library.`
					: `"${response.title}" has been added to your library.`,
			});

			setYoutubeUrl("");
			setSearchQuery("");
			setShowYoutubeDialog(false);
			setIsYoutubeMode(false);

			// Navigate to the video page
			_navigate(`/videos/${response.uuid}`);

			// Refresh content list
			const data = await fetchContentData();
			const { content } = processContentData(data);
			setContentItems(
				content.map((item) => ({
					...item,
					dueDate:
						Math.random() > 0.7
							? new Date(
									Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000,
								).toISOString()
							: null,
					isPaused: Math.random() > 0.9,
					totalCards: item.cardCount,
					due: item.dueCount || Math.floor(Math.random() * 10),
					overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
				})),
			);
		} catch (error) {
			toast({
				title: "Error",
				description: error.message || "Failed to add video. Please try again.",
				variant: "destructive",
			});
		} finally {
			setIsAddingVideo(false);
		}
	};

	const handleCreateDeck = async () => {
		if (!newDeckTitle.trim()) return;

		try {
			// Create the deck first
			const deckResponse = await api.post("/flashcards", {
				title: newDeckTitle,
				description: newDeckDescription || "",
			});

			// If cards were provided, add them to the deck
			if (newCards.trim()) {
				const cards = newCards.split("\n").filter((line) => line.trim());
				const cardData = cards.map((line) => {
					const [front, back] = line.split("|").map((s) => s.trim());
					return { front: front || line, back: back || "" };
				});

				if (cardData.length > 0) {
					await api.post(`/flashcards/${deckResponse.id}/cards`, {
						cards: cardData,
					});
				}
			}

			toast({
				title: "Deck Created!",
				description: `"${newDeckTitle}" has been created with ${newCards.split("\n").filter(Boolean).length} cards.`,
			});

			setNewDeckTitle("");
			setNewDeckDescription("");
			setNewCards("");
			setShowFlashcardDialog(false);

			// Refresh content list
			const data = await fetchContentData();
			const { content } = processContentData(data);
			setContentItems(
				content.map((item) => ({
					...item,
					dueDate:
						Math.random() > 0.7
							? new Date(
									Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000,
								).toISOString()
							: null,
					isPaused: Math.random() > 0.9,
					totalCards: item.cardCount,
					due: item.dueCount || Math.floor(Math.random() * 10),
					overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
				})),
			);
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to create flashcard deck. Please try again.",
				variant: "destructive",
			});
		}
	};

	return (
		<ErrorBoundary>
			<TooltipProvider>
				<ErrorBoundary>
					<div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
						<MainHeader transparent />
						<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 pt-28">
							<motion.div
								initial={{ opacity: 0, y: -20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ duration: 0.5 }}
								className="text-center mb-6"
							>
								<h1 className="text-4xl md:text-5xl font-display font-bold bg-clip-text text-transparent bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 mb-4 tracking-tight">
									Welcome Back!
								</h1>
								<p className="text-lg text-muted-foreground max-w-2xl mx-auto">
									Ready to continue your journey? Pick up where you left off or
									explore something new today.
								</p>
							</motion.div>

							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ duration: 0.5, delay: 0.1 }}
								className="max-w-2xl mx-auto mb-6"
							>
								<div className="bg-white rounded-2xl shadow-sm p-2 border border-border transition-all hover:shadow-md">
									<div className="flex items-center">
										<div
											className={`flex-1 flex items-center gap-2 px-3 py-2 rounded-xl transition-all ${
												isGenerateMode
													? "bg-course/10"
													: isYoutubeMode
														? "bg-video/10"
														: ""
											}`}
										>
											{isGenerateMode ? (
												<Sparkles className="text-course" size={20} />
											) : isYoutubeMode ? (
												<Youtube className="text-video" size={20} />
											) : (
												<Search className="text-muted-foreground" size={20} />
											)}
											<Input
												type="text"
												placeholder={
													isGenerateMode
														? "What do you want to learn about?"
														: isYoutubeMode
															? "Paste a YouTube URL or search for videos..."
															: "Search your courses and books..."
												}
												className="border-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent"
												value={searchQuery}
												onChange={(e) => setSearchQuery(e.target.value)}
											/>
											{searchQuery && (
												<Button
													variant="ghost"
													size="icon"
													onClick={() => setSearchQuery("")}
													className="h-8 w-8"
												>
													<X className="h-4 w-4" />
												</Button>
											)}
										</div>

										<div className="flex items-center gap-2 pl-2">
											<div className="h-8 w-px bg-border" />
											{isGenerateMode ? (
												<>
													<Button
														variant="ghost"
														size="sm"
														onClick={() => setIsGenerateMode(false)}
														className="text-muted-foreground"
													>
														Cancel
													</Button>
													<Button
														size="sm"
														onClick={handleGenerateCourse}
														disabled={!searchQuery.trim() || isGenerating}
														className="bg-course hover:bg-course-accent text-white"
													>
														{isGenerating ? "Generating..." : "Generate"}
													</Button>
												</>
											) : isYoutubeMode ? (
												<>
													<Button
														variant="ghost"
														size="sm"
														onClick={() => setIsYoutubeMode(false)}
														className="text-muted-foreground"
													>
														Cancel
													</Button>
													<Button
														size="sm"
														onClick={() => {
															if (searchQuery.trim()) {
																setYoutubeUrl(searchQuery);
																handleYoutubeAdd();
																setIsYoutubeMode(false);
															}
														}}
														disabled={!searchQuery.trim()}
														className="bg-video hover:bg-video-accent text-white"
													>
														Add Video
													</Button>
												</>
											) : (
												<>
													{searchQuery && (
														<Button
															variant="ghost"
															size="sm"
															onClick={() => setSearchQuery("")}
															className="text-muted-foreground"
														>
															Clear
														</Button>
													)}
													<Button
														onClick={() => setShowRoadmapModal(true)}
														size="sm"
														className="bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white flex items-center gap-1"
													>
														<Sparkles className="h-3.5 w-3.5" />
														Generate Roadmap
													</Button>
													<Popover>
														<PopoverTrigger asChild>
															<Button
																variant="outline"
																size="sm"
																className="flex items-center gap-1"
															>
																<SlidersHorizontal className="h-3.5 w-3.5 mr-1" />
																Filters
															</Button>
														</PopoverTrigger>
														<PopoverContent className="w-80" align="end">
															<div className="space-y-4">
																<div>
																	<h4 className="font-medium mb-2 text-sm">
																		Content Type
																	</h4>
																	<RadioGroup
																		value={activeFilter}
																		onValueChange={setActiveFilter}
																		className="flex flex-col gap-2"
																	>
																		{filterOptions.map((option) => (
																			<div
																				key={option.id}
																				className="flex items-center space-x-2"
																			>
																				<RadioGroupItem
																					value={option.id}
																					id={`filter-${option.id}`}
																				/>
																				<Label
																					htmlFor={`filter-${option.id}`}
																					className="flex items-center cursor-pointer"
																				>
																					{option.icon}
																					{option.label}
																				</Label>
																			</div>
																		))}
																	</RadioGroup>
																</div>

																<Separator />

																<div>
																	<h4 className="font-medium text-sm mb-2">
																		Archive Status
																	</h4>
																	<RadioGroup
																		value={archiveFilter}
																		onValueChange={setArchiveFilter}
																		className="flex flex-col gap-2"
																	>
																		<div className="flex items-center space-x-2">
																			<RadioGroupItem
																				value="active"
																				id="archive-active"
																			/>
																			<Label
																				htmlFor="archive-active"
																				className="cursor-pointer"
																			>
																				Active Content
																			</Label>
																		</div>
																		<div className="flex items-center space-x-2">
																			<RadioGroupItem
																				value="archived"
																				id="archive-archived"
																			/>
																			<Label
																				htmlFor="archive-archived"
																				className="cursor-pointer"
																			>
																				Archived Content
																			</Label>
																		</div>
																		<div className="flex items-center space-x-2">
																			<RadioGroupItem
																				value="all"
																				id="archive-all"
																			/>
																			<Label
																				htmlFor="archive-all"
																				className="cursor-pointer"
																			>
																				All Content
																			</Label>
																		</div>
																	</RadioGroup>
																</div>

																<Separator />

																<div>
																	<h4 className="font-medium text-sm mb-2">
																		Filter by Tag
																	</h4>
																	<Input
																		placeholder="Filter by tag..."
																		value={tagFilter}
																		onChange={(e) =>
																			setTagFilter(e.target.value)
																		}
																		className="text-sm"
																	/>
																</div>

																<Separator />

																<div>
																	<div className="flex justify-between items-center mb-2">
																		<h4 className="font-medium text-sm">
																			Sort By
																		</h4>
																		<Button
																			variant="ghost"
																			size="sm"
																			onClick={toggleSortDirection}
																			className="h-8 px-2 text-xs"
																		>
																			{sortDirection === "desc"
																				? "Newest First"
																				: "Oldest First"}
																		</Button>
																	</div>
																	<RadioGroup
																		value={activeSort}
																		onValueChange={setActiveSort}
																		className="flex flex-col gap-2"
																	>
																		{sortOptions.map((option) => (
																			<div
																				key={option.id}
																				className="flex items-center space-x-2"
																			>
																				<RadioGroupItem
																					value={option.id}
																					id={`sort-${option.id}`}
																				/>
																				<Label
																					htmlFor={`sort-${option.id}`}
																					className="flex items-center cursor-pointer"
																				>
																					{option.icon}
																					{option.label}
																				</Label>
																			</div>
																		))}
																	</RadioGroup>
																</div>
															</div>
														</PopoverContent>
													</Popover>
												</>
											)}
										</div>
									</div>
								</div>
							</motion.div>

							<motion.div
								initial={{ opacity: 0, y: 10 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ duration: 0.3, delay: 0.2 }}
								className="max-w-2xl mx-auto mb-8 flex flex-wrap items-center gap-2"
							>
								{activeFilter !== "all" && (
									<Badge variant="outline" className="bg-white">
										{getActiveFilterLabel()}
										<Button
											variant="ghost"
											size="sm"
											onClick={() => setActiveFilter("all")}
											className="h-4 w-4 p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
										>
											<X className="h-3 w-3" />
											<span className="sr-only">Remove filter</span>
										</Button>
									</Badge>
								)}

								{archiveFilter !== "active" && (
									<Badge variant="outline" className="bg-white">
										{archiveFilter === "archived"
											? "Archived Content"
											: "All Content"}
										<Button
											variant="ghost"
											size="sm"
											onClick={() => setArchiveFilter("active")}
											className="h-4 w-4 p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
										>
											<X className="h-3 w-3" />
											<span className="sr-only">Reset archive filter</span>
										</Button>
									</Badge>
								)}

								{activeSort !== "last-accessed" && (
									<Badge variant="outline" className="bg-white">
										Sorted by: {getActiveSortLabel()}
										<Button
											variant="ghost"
											size="sm"
											onClick={() => setActiveSort("last-accessed")}
											className="h-4 w-4 p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
										>
											<X className="h-3 w-3" />
											<span className="sr-only">Remove sort</span>
										</Button>
									</Badge>
								)}

								{sortDirection !== "desc" && (
									<Badge variant="outline" className="bg-white">
										{sortDirection === "asc" ? "Oldest First" : "Newest First"}
										<Button
											variant="ghost"
											size="sm"
											onClick={() => setSortDirection("desc")}
											className="h-4 w-4 p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
										>
											<X className="h-3 w-3" />
											<span className="sr-only">Remove sort direction</span>
										</Button>
									</Badge>
								)}

								{tagFilter && (
									<Badge variant="outline" className="bg-white">
										Tag: {tagFilter}
										<Button
											variant="ghost"
											size="sm"
											onClick={() => setTagFilter("")}
											className="h-4 w-4 p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
										>
											<X className="h-3 w-3" />
											<span className="sr-only">Remove tag filter</span>
										</Button>
									</Badge>
								)}

								{(activeFilter !== "all" ||
									activeSort !== "last-accessed" ||
									sortDirection !== "desc" ||
									tagFilter) && (
									<Button
										variant="ghost"
										size="sm"
										onClick={() => {
											setActiveFilter("all");
											setActiveSort("last-accessed");
											setSortDirection("desc");
											setTagFilter("");
										}}
										className="text-xs text-muted-foreground h-7 px-2 ml-auto"
									>
										Reset All
									</Button>
								)}
							</motion.div>

							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ duration: 0.5, delay: 0.3 }}
							>
								<AnimatePresence>
									{pinnedItems.length > 0 && (
										<motion.section
											initial={{ opacity: 0, height: 0 }}
											animate={{ opacity: 1, height: "auto" }}
											exit={{ opacity: 0, height: 0 }}
											className="mb-8"
										>
											<div className="flex items-center gap-2 mb-4">
												<Pin className="h-4 w-4 text-primary" />
												<h2 className="text-xl font-semibold">Pinned</h2>
											</div>
											<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
												{pinnedItems.map(renderCard)}
											</div>
											<div className="border-b border-border my-8" />
										</motion.section>
									)}
								</AnimatePresence>

								<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
									{isLoading ? (
										// Show skeleton cards while loading
										Array.from({ length: 6 }).map(() => (
											<div key={crypto.randomUUID()} className="animate-pulse">
												<div className="bg-gray-200 dark:bg-gray-700 rounded-xl h-64" />
											</div>
										))
									) : filteredAndSortedContent.length > 0 ? (
										visible.map(renderCard)
									) : (
										<div className="col-span-full text-center py-12">
											<p className="text-muted-foreground">
												No content found matching your criteria.
											</p>
											<div className="flex justify-center gap-4 mt-4 flex-wrap">
												<Button
													variant="outline"
													onClick={() => setIsGenerateMode(true)}
												>
													Generate a new course
												</Button>
												<Button
													variant="outline"
													onClick={() => {
														setShowUploadDialog(true);
														setSelectedFile(null);
														setBookTitle("");
														setBookAuthor("");
														setIsExtractingMetadata(false);
													}}
												>
													Upload a new book
												</Button>
												<Button
													variant="outline"
													onClick={() => setShowYoutubeDialog(true)}
												>
													Add YouTube video
												</Button>
												<Button
													variant="outline"
													onClick={() => setShowFlashcardDialog(true)}
												>
													Create flashcards
												</Button>
											</div>
										</div>
									)}
								</div>

								{!isLoading && unpinned.length > 3 && (
									<div className="mt-6 text-center">
										<Button
											variant="outline"
											onClick={() => setShowAll(!showAll)}
											className="h-10 min-w-[120px] flex items-center gap-2"
										>
											{showAll ? (
												<>
													<ChevronUp className="h-4 w-4" />
													Show Less
												</>
											) : (
												<>
													<ChevronDown className="h-4 w-4" />
													See {unpinned.length - 3} More
												</>
											)}
										</Button>
									</div>
								)}

								{!isLoading && filteredAndSortedContent.length === 0 && (
									<div className="text-center py-12">
										<div className="inline-block bg-emerald-50 p-4 rounded-full mb-4">
											<Check className="h-8 w-8 text-emerald-600" />
										</div>
										<h3 className="text-xl font-display font-bold text-emerald-700 mb-2">
											All Caught Up!
										</h3>
										<p className="text-muted-foreground">
											You've completed all your learning tasks. Great job!
										</p>
									</div>
								)}
							</motion.div>
						</div>
						{celebrate && (
							<div className="fixed inset-0 pointer-events-none z-50">
								{Array.from({ length: 100 }).map(() => (
									<div
										key={crypto.randomUUID()}
										className="absolute animate-confetti"
										style={{
											left: `${Math.random() * 100}%`,
											top: "-5%",
											width: `${Math.random() * 10 + 5}px`,
											height: `${Math.random() * 10 + 5}px`,
											background: [
												"#ff0000",
												"#00ff00",
												"#0000ff",
												"#ffff00",
												"#ff00ff",
												"#00ffff",
												"#ff8000",
												"#8000ff",
											][Math.floor(Math.random() * 8)],
											transform: `rotate(${Math.random() * 360}deg)`,
											animationDuration: `${Math.random() * 3 + 2}s`,
											animationDelay: `${Math.random() * 2}s`,
										}}
									/>
								))}
							</div>
						)}

						{/* FAB */}
						<div className="fixed bottom-8 right-8 z-50">
							<AnimatePresence>
								{isFabExpanded && (
									<motion.div
										initial={{ opacity: 0, y: 20 }}
										animate={{ opacity: 1, y: 0 }}
										exit={{ opacity: 0, y: 20 }}
										transition={{ duration: 0.2 }}
										className="flex flex-col items-center gap-3 mb-4"
									>
										<Tooltip>
											<TooltipTrigger asChild>
												<Button
													variant="secondary"
													className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
													onClick={() => {
														setIsGenerateMode(true);
														setIsFabExpanded(false);
														// Focus on search input after a short delay
														setTimeout(() => {
															const searchInput =
																document.querySelector('input[type="text"]');
															if (searchInput) searchInput.focus();
														}, 100);
													}}
												>
													<GraduationCap className="h-6 w-6" />
												</Button>
											</TooltipTrigger>
											<TooltipContent side="left">
												<p>Generate Course</p>
											</TooltipContent>
										</Tooltip>
										<Tooltip>
											<TooltipTrigger asChild>
												<Button
													variant="secondary"
													className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
													onClick={() => {
														setShowRoadmapModal(true);
														setIsFabExpanded(false);
													}}
												>
													<Sparkles className="h-6 w-6" />
												</Button>
											</TooltipTrigger>
											<TooltipContent side="left">
												<p>Generate Roadmap</p>
											</TooltipContent>
										</Tooltip>
										<Tooltip>
											<TooltipTrigger asChild>
												<Button
													variant="secondary"
													className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
													onClick={() => {
														setShowUploadDialog(true);
														setSelectedFile(null);
														setBookTitle("");
														setBookAuthor("");
														setIsExtractingMetadata(false);
														setIsFabExpanded(false);
													}}
												>
													<BookOpen className="h-6 w-6" />
												</Button>
											</TooltipTrigger>
											<TooltipContent side="left">
												<p>Upload Book</p>
											</TooltipContent>
										</Tooltip>
										<Tooltip>
											<TooltipTrigger asChild>
												<Button
													variant="secondary"
													className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
													onClick={() => {
														setShowYoutubeDialog(true);
														setIsFabExpanded(false);
													}}
												>
													<Youtube className="h-6 w-6" />
												</Button>
											</TooltipTrigger>
											<TooltipContent side="left">
												<p>Add YouTube Video</p>
											</TooltipContent>
										</Tooltip>
										<Tooltip>
											<TooltipTrigger asChild>
												<Button
													variant="secondary"
													className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
													onClick={() => {
														setShowFlashcardDialog(true);
														setIsFabExpanded(false);
													}}
												>
													<Layers className="h-6 w-6" />
												</Button>
											</TooltipTrigger>
											<TooltipContent side="left">
												<p>Create Flashcards</p>
											</TooltipContent>
										</Tooltip>
									</motion.div>
								)}
							</AnimatePresence>
							<Button
								className="rounded-full h-16 w-16 shadow-lg"
								onClick={() => setIsFabExpanded(!isFabExpanded)}
							>
								<motion.div
									animate={{ rotate: isFabExpanded ? 45 : 0 }}
									transition={{ duration: 0.3 }}
								>
									<Plus
										className={`h-8 w-8 transition-transform duration-300 ${isFabExpanded ? "rotate-45" : ""}`}
									/>
								</motion.div>
							</Button>
						</div>

						{/* Upload Book Dialog */}
						<Sheet
							open={showUploadDialog}
							onOpenChange={(open) => {
								if (!isUploadingBook) setShowUploadDialog(open);
							}}
						>
							<SheetContent side="bottom" className="sm:max-w-lg mx-auto">
								{isUploadingBook && (
									<div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 rounded-lg">
										<div className="flex flex-col items-center gap-4">
											<div className="animate-spin rounded-full h-10 w-10 border-b-2 border-book" />
											<p className="text-lg font-medium">
												Uploading your book...
											</p>
										</div>
									</div>
								)}
								<SheetHeader>
									<SheetTitle>Upload a Book</SheetTitle>
									<SheetDescription>
										Upload a PDF, EPUB, or other supported document to start
										learning.
									</SheetDescription>
								</SheetHeader>
								<div className="py-4 space-y-4">
									<div className="grid w-full max-w-sm items-center gap-1.5">
										<Label htmlFor="book-file">Book File</Label>
										<Input
											id="book-file"
											type="file"
											accept=".pdf,.epub,.mobi,.azw3"
											onChange={handleFileChange}
										/>
									</div>
									{isExtractingMetadata && (
										<div className="flex items-center gap-2 text-sm text-muted-foreground">
											<div className="animate-spin rounded-full h-4 w-4 border-b-2 border-book" />
											<span>Extracting metadata...</span>
										</div>
									)}
									{selectedFile && (
										<div className="space-y-2">
											<div className="grid w-full max-w-sm items-center gap-1.5">
												<Label htmlFor="book-title">Title</Label>
												<Input
													id="book-title"
													type="text"
													value={bookTitle}
													onChange={(e) => setBookTitle(e.target.value)}
												/>
											</div>
											<div className="grid w-full max-w-sm items-center gap-1.5">
												<Label htmlFor="book-author">Author</Label>
												<Input
													id="book-author"
													type="text"
													value={bookAuthor}
													onChange={(e) => setBookAuthor(e.target.value)}
												/>
											</div>
										</div>
									)}
								</div>
								<SheetFooter>
									<Button
										onClick={handleUpload}
										disabled={
											!selectedFile || !bookTitle.trim() || !bookAuthor.trim()
										}
									>
										Upload Book
									</Button>
								</SheetFooter>
							</SheetContent>
						</Sheet>

						{/* Add YouTube Video Dialog */}
						<Sheet
							open={showYoutubeDialog}
							onOpenChange={(open) => {
								if (!isAddingVideo) setShowYoutubeDialog(open);
							}}
						>
							<SheetContent side="bottom" className="sm:max-w-lg mx-auto">
								{isAddingVideo && (
									<div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 rounded-lg">
										<div className="flex flex-col items-center gap-4">
											<div className="animate-spin rounded-full h-10 w-10 border-b-2 border-video" />
											<p className="text-lg font-medium">
												Adding your video...
											</p>
										</div>
									</div>
								)}
								<SheetHeader>
									<SheetTitle>Add YouTube Video</SheetTitle>
									<SheetDescription>
										Enter a YouTube URL to add it to your library.
									</SheetDescription>
								</SheetHeader>
								<div className="py-4">
									<Input
										type="url"
										placeholder="https://www.youtube.com/watch?v=..."
										value={youtubeUrl}
										onChange={(e) => setYoutubeUrl(e.target.value)}
									/>
								</div>
								<SheetFooter>
									<Button
										onClick={handleYoutubeAdd}
										disabled={!youtubeUrl.trim() || isAddingVideo}
									>
										{isAddingVideo ? "Adding..." : "Add Video"}
									</Button>
								</SheetFooter>
							</SheetContent>
						</Sheet>

						{/* Create Flashcard Deck Dialog */}
						<Sheet
							open={showFlashcardDialog}
							onOpenChange={setShowFlashcardDialog}
						>
							<SheetContent side="bottom" className="sm:max-w-lg mx-auto">
								<SheetHeader>
									<SheetTitle>Create Flashcard Deck</SheetTitle>
									<SheetDescription>
										Create a new deck of flashcards. You can add cards now or
										later.
									</SheetDescription>
								</SheetHeader>
								<div className="py-4 space-y-4">
									<Input
										placeholder="Deck Title"
										value={newDeckTitle}
										onChange={(e) => setNewDeckTitle(e.target.value)}
									/>
									<Input
										placeholder="Deck Description (optional)"
										value={newDeckDescription}
										onChange={(e) => setNewDeckDescription(e.target.value)}
									/>
									<textarea
										placeholder="Add cards (one per line, front|back)"
										value={newCards}
										onChange={(e) => setNewCards(e.target.value)}
										className="w-full h-32 p-2 border rounded-md"
									/>
								</div>
								<SheetFooter>
									<Button
										onClick={handleCreateDeck}
										disabled={!newDeckTitle.trim()}
									>
										Create Deck
									</Button>
								</SheetFooter>
							</SheetContent>
						</Sheet>

						<RoadmapPromptModal
							isOpen={showRoadmapModal}
							onClose={() => {
								setShowRoadmapModal(false);
								handleRoadmapCreated();
							}}
						/>
					</div>
				</ErrorBoundary>
			</TooltipProvider>
		</ErrorBoundary>
	);
}

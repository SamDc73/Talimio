import { motion } from "framer-motion";
import { useState, useMemo } from "react";
import {
	Archive,
	MoreHorizontal,
	Pause,
	Pin,
	Tag,
	X,
} from "lucide-react";
import { Button } from "@/components/button";
import { ConfirmationDialog } from "@/components/ConfirmationDialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { Separator } from "@/components/separator";
import { useToast } from "@/hooks/use-toast";
import useAppStore from "@/stores/useAppStore";
import { deleteApi } from "@/services/deleteApi";
import { archiveContent, unarchiveContent } from "@/services/contentService";
import DueDateChip from "@/features/home/components/DueDateChip";
import TagChip from "@/features/home/components/TagChip";
import TagEditModal from "@/features/home/components/TagEditModal";
import { VARIANTS } from "@/features/home/utils/contentConstants";

function formatDuration(seconds) {
	if (!seconds) return "Unknown duration";
	const minutes = Math.floor(seconds / 60);
	const hours = Math.floor(minutes / 60);
	const remainingMinutes = minutes % 60;
	if (hours > 0) {
		return `${hours}h ${remainingMinutes}m`;
	}
	return `${minutes}m`;
}

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

export default BaseCard;
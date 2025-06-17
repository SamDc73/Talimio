import { ConfirmationDialog } from "@/components/ConfirmationDialog";
import { Button } from "@/components/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { useToast } from "@/hooks/use-toast";
import { archiveContent, unarchiveContent } from "@/services/contentService";
import {
	Archive,
	ArchiveRestore,
	MoreHorizontal,
	PauseCircle,
	PlayCircle,
	Trash2,
} from "lucide-react";
import { useState } from "react";

export function KebabMenu({
	onMouseEnter,
	onMouseLeave,
	showMenu = false,
	onDelete,
	onArchive,
	itemType,
	itemId,
	itemTitle = "",
	isArchived = false,
	isPaused = false,
}) {
	const [open, setOpen] = useState(false);
	const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
	const [isArchiving, setIsArchiving] = useState(false);
	const { toast } = useToast();

	const handleDeleteClick = () => {
		setShowDeleteConfirm(true);
		setOpen(false);
	};

	const handleConfirmDelete = async () => {
		if (onDelete) {
			await onDelete(itemType, itemId);
		}
	};

	const handleArchive = async () => {
		if (isArchiving) return;

		setIsArchiving(true);
		setOpen(false);

		try {
			if (isArchived) {
				await unarchiveContent(itemType, itemId);
				toast({
					title: "Content Unarchived",
					description: `${itemTitle} has been unarchived successfully.`,
				});
			} else {
				await archiveContent(itemType, itemId);
				toast({
					title: "Content Archived",
					description: `${itemTitle} has been archived successfully.`,
				});
			}

			// Notify parent component to refresh content
			if (onArchive) {
				onArchive(itemType, itemId, !isArchived);
			}
		} catch (error) {
			console.error("Archive operation failed:", error);
			toast({
				title: "Error",
				description: `Failed to ${isArchived ? "unarchive" : "archive"} content. Please try again.`,
				variant: "destructive",
			});
		} finally {
			setIsArchiving(false);
		}
	};

	const handleTogglePause = () => {
		console.log(`${isPaused ? "Resume" : "Pause"} functionality - placeholder`);
		setOpen(false);
	};

	return (
		<div
			className="absolute top-3 right-3 z-10"
			onMouseEnter={onMouseEnter}
			onMouseLeave={onMouseLeave}
		>
			<Popover open={open} onOpenChange={setOpen}>
				<PopoverTrigger asChild>
					<Button
						variant="ghost"
						size="icon"
						className={`h-10 w-10 rounded-full shadow-sm flex items-center justify-center transition-opacity duration-200 ${
							showMenu ? "opacity-100" : "opacity-0"
						}`}
					>
						<MoreHorizontal className="h-4 w-4" />
					</Button>
				</PopoverTrigger>
				<PopoverContent className="w-40 p-0" align="end">
					<div className="flex flex-col">
						<Button
							variant="ghost"
							size="sm"
							className="justify-start font-normal"
						>
							Pin
						</Button>
						<Button
							variant="ghost"
							size="sm"
							className="justify-start font-normal"
						>
							Edit Tags
						</Button>
						<Button
							variant="ghost"
							size="sm"
							className="justify-start font-normal flex items-center gap-2"
							onClick={handleArchive}
							disabled={isArchiving}
						>
							{isArchived ? (
								<ArchiveRestore className="h-4 w-4" />
							) : (
								<Archive className="h-4 w-4" />
							)}
							{isArchiving
								? "Processing..."
								: isArchived
									? "Unarchive"
									: "Archive"}
						</Button>
						<Button
							variant="ghost"
							size="sm"
							className="justify-start font-normal flex items-center gap-2"
							onClick={handleTogglePause}
						>
							{isPaused ? (
								<PlayCircle className="h-4 w-4" />
							) : (
								<PauseCircle className="h-4 w-4" />
							)}
							{isPaused ? "Resume" : "Pause"}
						</Button>
						<Button
							variant="ghost"
							size="sm"
							className="justify-start font-normal text-red-600 hover:text-red-700 hover:bg-red-50 flex items-center gap-2"
							onClick={handleDeleteClick}
						>
							<Trash2 className="h-4 w-4" />
							Delete
						</Button>
					</div>
				</PopoverContent>
			</Popover>

			<ConfirmationDialog
				open={showDeleteConfirm}
				onOpenChange={setShowDeleteConfirm}
				title="Delete Item"
				description="This action cannot be undone. This item will be permanently removed from your library."
				itemName={itemTitle}
				onConfirm={handleConfirmDelete}
			/>
		</div>
	);
}

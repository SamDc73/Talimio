import { motion } from "framer-motion"
import { Archive, MoreHorizontal, Pin, Tag, X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/Button"
import { ConfirmationDialog } from "@/components/ConfirmationDialog"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/Popover"
import { Separator } from "@/components/Separator"
import TagChip from "@/features/home/components/TagChip"
import TagEditModal from "@/features/home/components/TagEditModal"
import { useArchiveContent, useDeleteContent } from "@/features/home/hooks/useContentQueries"
import { VARIANTS } from "@/features/home/utils/contentConstants"

function formatDuration(seconds) {
	if (!seconds) return "Unknown duration"
	const minutes = Math.floor(seconds / 60)
	const hours = Math.floor(minutes / 60)
	const remainingMinutes = minutes % 60
	if (hours > 0) {
		return `${hours}h ${remainingMinutes}m`
	}
	return `${minutes}m`
}

function ContentCard({ item, pinned, onTogglePin, onDelete, onArchive, onTagsUpdated, index, onClick }) {
	const [hover, setHover] = useState(false)
	const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
	const [showTagEditModal, setShowTagEditModal] = useState(false)

	// Use React Query mutations
	const deleteContentMutation = useDeleteContent()
	const archiveContentMutation = useArchiveContent()

	// Use unified API progress data - extract percentage from progress object
	const progressValue =
		typeof item.progress === "object" && item.progress !== null ? (item.progress.percentage ?? 0) : item.progress || 0

	const handleDeleteClick = () => {
		setShowDeleteConfirm(true)
	}

	const getActionLabel = (action) => {
		if (action === "Pin") return pinned ? "Unpin" : "Pin"
		if (action === "Archive") {
			if (archiveContentMutation.isPending) return "Processing..."
			return item.archived ? "Unarchive" : "Archive"
		}
		return action
	}

	const handleConfirmDelete = () => {
		// Close dialog immediately for instant feedback
		setShowDeleteConfirm(false)

		// Use React Query mutation (handles optimistic update, backend call, notifications)
		deleteContentMutation.mutate({
			itemId: item.id,
			itemType: item.type,
		})

		// Notify parent if provided (e.g., to clear pins)
		if (onDelete) {
			onDelete(item.id, item.type)
		}
	}

	const handleArchive = () => {
		// Prevent multiple clicks
		if (archiveContentMutation.isPending) return

		// Use React Query mutation
		archiveContentMutation.mutate({
			item,
			archive: !item.archived,
		})

		// Notify parent if provided
		if (onArchive) {
			onArchive(item.id, item.type, !item.archived)
		}
	}

	const handleEditTags = () => {
		setShowTagEditModal(true)
	}

	return (
		<div>
			<motion.div
				layout
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				exit={{ opacity: 0, scale: 0.8, transition: { duration: 0.2 } }}
				transition={{ duration: 0.4, delay: 0.1 * index }}
				whileHover={{ y: -5, transition: { duration: 0.2 } }}
				className={`bg-background rounded-2xl overflow-hidden relative flex flex-col h-full cursor-pointer ${
					pinned
						? "shadow-md border-2 border-green-500/10 bg-green-500/5"
						: "shadow-sm hover:shadow-md border border-border"
				}`}
				onMouseEnter={() => setHover(true)}
				onMouseLeave={() => setHover(false)}
				onClick={onClick}
			>
				{pinned && <div className="absolute top-0 left-6 w-6 h-1 bg-green-500 rounded-b-full" />}
				<div className="p-6 flex flex-col justify-between h-full">
					<div className="flex justify-between items-start mb-4">
						<div
							className={`${VARIANTS[item.type].badge} text-xs font-medium px-3 py-1 rounded-full flex items-center gap-2`}
						>
							{(() => {
								const V = VARIANTS[item.type]
								const Icon = V.icon
								return (
									<>
										<Icon className="size-3 " />
										<span>{V.label}</span>
									</>
								)
							})()}
						</div>
					</div>
					<h3 className="text-xl font-bold text-foreground hover:underline line-clamp-2 mb-1">{item.title}</h3>

					{/* Video metadata */}
					{item.type === "video" && (
						<p className="text-muted-foreground text-sm mb-4">
							by {item.channel || "Unknown Channel"} • {formatDuration(item.duration)}
						</p>
					)}

					{/* Book metadata */}
					{item.type === "book" && (
						<p className="text-muted-foreground text-sm mb-4">
							by {item.author || "Unknown Author"} • {item.pageCount || "Unknown"} pages
						</p>
					)}

					{/* Description for other types */}
					{item.type !== "video" && item.type !== "book" && item.description && (
						<p className="text-muted-foreground text-sm line-clamp-2 mb-4">{item.description}</p>
					)}

					<div className="flex flex-wrap items-center gap-2 mb-3">
						{item.tags?.slice(0, 2).map((t) => (
							<TagChip key={t} tag={t} contentType={item.type} />
						))}
						{item.tags?.length > 2 && (
							<span className="inline-flex text-xs font-medium bg-muted text-muted-foreground px-2 py-0.5 rounded-sm">
								+{item.tags.length - 2}
							</span>
						)}
					</div>
					<div>
						<div className="flex justify-between text-xs text-muted-foreground mb-2">
							<span>{Math.round(progressValue)}%</span>
						</div>
						<div className="w-full bg-muted rounded-full h-2 overflow-hidden">
							<div
								style={{ width: `${progressValue}%` }}
								className={`h-full bg-linear-to-r ${VARIANTS[item.type].grad} rounded-full transition-all duration-500`}
							/>
						</div>
					</div>
				</div>
				{hover && (
					<div className="absolute top-4 right-4 z-10">
						<Popover>
							<PopoverTrigger asChild onClick={(e) => e.stopPropagation()}>
								<Button variant="ghost" size="icon" className="size-10  rounded-full">
									<MoreHorizontal className="size-4 " />
								</Button>
							</PopoverTrigger>
							<PopoverContent align="end" className="w-40 p-0">
								<div className="flex flex-col text-sm">
									{["Pin", "Edit Tags", "Archive", "sep", "Delete"].map((action) =>
										action === "sep" ? (
											<Separator key="separator" />
										) : (
											<Button
												key={action}
												variant="ghost"
												size="sm"
												className={`justify-start flex items-center gap-2 ${action === "Delete" ? "text-destructive hover:bg-destructive/10" : ""}`}
												onClick={(e) => {
													e.stopPropagation()
													switch (action) {
														case "Pin": {
															onTogglePin()
															break
														}
														case "Delete": {
															handleDeleteClick()
															break
														}
														case "Archive": {
															handleArchive()
															break
														}
														case "Edit Tags": {
															handleEditTags()
															break
														}
													}
												}}
												disabled={action === "Archive" && archiveContentMutation.isPending}
											>
												{action === "Pin" && <Pin className="size-4 " />}
												{action === "Edit Tags" && <Tag className="size-4 " />}
												{action === "Archive" && <Archive className="size-4 " />}
												{action === "Delete" && <X className="size-4 " />}
												{getActionLabel(action)}
											</Button>
										)
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
				contentType={item.type}
				contentId={item.id}
				contentTitle={item.title}
				onTagsUpdated={onTagsUpdated}
			/>
		</div>
	)
}

export default ContentCard

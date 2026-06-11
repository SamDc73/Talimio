import { useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Archive, MoreHorizontal, Pin, Tag, X } from "lucide-react"
import { useState } from "react"
import { getBookAttachmentConflict } from "@/api/contentApi"
import { Button } from "@/components/Button"
import { ConfirmationDialog } from "@/components/ConfirmationDialog"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/Popover"
import { Separator } from "@/components/Separator"
import TagChip from "@/features/home/components/TagChip"
import TagEditModal from "@/features/home/components/TagEditModal"
import { useArchiveContent, useDeleteContent } from "@/features/home/hooks/use-content-queries"
import { VARIANTS } from "@/features/home/utils/contentConstants"
import { contentKeys } from "@/lib/content-query-cache"

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

function ContentCard({ item, pinned, onTogglePin, onDelete, onTagsUpdated, index, onClick }) {
	const [hover, setHover] = useState(false)
	const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
	const [attachmentConflict, setAttachmentConflict] = useState(null)
	const [showTagEditModal, setShowTagEditModal] = useState(false)

	// Use React Query mutations
	const deleteContentMutation = useDeleteContent()
	const archiveContentMutation = useArchiveContent()
	const queryClient = useQueryClient()

	const progressValue = item.progress ?? 0
	const isArchived = item.status === "archived"

	const handleDeleteClick = () => {
		setShowDeleteConfirm(true)
	}

	const getActionLabel = (action) => {
		if (action === "Pin") return pinned ? "Unpin" : "Pin"
		if (action === "Archive") {
			if (archiveContentMutation.isPending) return "Processing..."
			return isArchived ? "Unarchive" : "Archive"
		}
		return action
	}

	const resolveCourseTitles = (courseIds) => {
		const titlesById = new Map()
		for (const [, data] of queryClient.getQueriesData({ queryKey: contentKeys.all })) {
			const items = data?.items || data?.pages?.flatMap((page) => page?.items || []) || []
			for (const cached of items) {
				if (cached?.type === "course" && cached?.id) {
					titlesById.set(String(cached.id), cached.title)
				}
			}
		}
		return courseIds.map((courseId) => titlesById.get(String(courseId))).filter(Boolean)
	}

	const handleConfirmDelete = () => {
		// Close dialog immediately for instant feedback
		setShowDeleteConfirm(false)

		// Use React Query mutation (handles optimistic update, backend call, notifications)
		deleteContentMutation.mutate(
			{
				itemId: item.id,
				itemType: item.type,
			},
			{
				onError: (error) => {
					// Books attached to courses return 409; surface the cascade confirm.
					const conflict = getBookAttachmentConflict(error)
					if (conflict) {
						setAttachmentConflict({
							...conflict,
							courseTitles: resolveCourseTitles(conflict.courseIds),
						})
					}
				},
			}
		)

		// Notify parent if provided (e.g., to clear pins)
		if (onDelete) {
			onDelete(item.id, item.type)
		}
	}

	const handleConfirmForceDelete = () => {
		setAttachmentConflict(null)
		deleteContentMutation.mutate({
			itemId: item.id,
			itemType: item.type,
			force: true,
		})
		if (onDelete) {
			onDelete(item.id, item.type)
		}
	}

	const attachmentConflictDescription = (() => {
		if (!attachmentConflict) return ""
		const count = attachmentConflict.attachmentCount
		const titles = attachmentConflict.courseTitles || []
		const courseLabel =
			titles.length > 0
				? `${count} course${count === 1 ? "" : "s"} (${titles.join(", ")})`
				: `${count} course${count === 1 ? "" : "s"}`
		return `This book is attached to ${courseLabel}. Deleting will remove it from all of them, along with its file and embeddings.`
	})()

	const handleArchive = () => {
		// Prevent multiple clicks
		if (archiveContentMutation.isPending) return

		// Use React Query mutation
		archiveContentMutation.mutate({
			item,
			archive: !isArchived,
		})
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
				transition={{ duration: 0.4, delay: Math.min(index, 3) * 0.04 }}
				whileHover={{ y: -5, transition: { duration: 0.2 } }}
				className={`group bg-background rounded-2xl overflow-hidden relative flex flex-col h-full cursor-pointer ${
					pinned ? "shadow-md border-2 border-primary/15 bg-primary/5" : "shadow-sm hover:shadow-md"
				}`}
				onMouseEnter={() => setHover(true)}
				onMouseLeave={() => setHover(false)}
				onClick={onClick}
			>
				{pinned && <div className="absolute top-0 left-lg h-3xs w-lg rounded-b-full bg-primary" />}
				<div className="flex h-full flex-col p-lg">
					<div className="mb-md flex">
						<div
							className={`${VARIANTS[item.type].badge} flex items-center gap-2xs rounded-full px-sm py-2xs text-xs font-medium`}
						>
							{(() => {
								const V = VARIANTS[item.type]
								const Icon = V.icon
								return (
									<>
										<Icon className="size-md" />
										<span>{V.label}</span>
									</>
								)
							})()}
						</div>
					</div>

					{/* Group title + subtitle so the gap below holds when there's no subtitle */}
					<div className="mb-md">
						<h3 className="line-clamp-2 text-xl font-bold text-foreground group-hover:underline">{item.title}</h3>

						{/* Video metadata */}
						{item.type === "video" && (
							<p className="mt-3xs text-sm text-muted-foreground">
								by {item.channel || "Unknown Channel"} • {formatDuration(item.duration)}
							</p>
						)}

						{/* Book metadata */}
						{item.type === "book" && (
							<p className="mt-3xs text-sm text-muted-foreground">
								by {item.author || "Unknown Author"} • {item.pageCount || "Unknown"} pages
							</p>
						)}

						{/* Description for other types */}
						{item.type !== "video" && item.type !== "book" && item.description && (
							<p className="mt-3xs line-clamp-2 text-sm text-muted-foreground">{item.description}</p>
						)}
					</div>

					<div className="mb-xs flex flex-wrap items-center gap-2xs">
						{item.tags?.slice(0, 2).map((t) => (
							<TagChip key={t} tag={t} contentType={item.type} />
						))}
						{item.tags?.length > 2 && (
							<span className="inline-flex rounded-full bg-muted px-xs py-3xs text-xs font-medium text-muted-foreground">
								+{item.tags.length - 2}
							</span>
						)}
					</div>
					<div className="mt-auto">
						<div className="mb-2xs text-xs text-muted-foreground">{Math.round(progressValue)}%</div>
						<div className="h-2xs w-full overflow-hidden rounded-full bg-muted">
							<div
								style={{ width: `${progressValue}%` }}
								className={`h-full bg-linear-to-r ${VARIANTS[item.type].grad} rounded-full transition-all duration-500`}
							/>
						</div>
					</div>
				</div>
				{hover && (
					<div className="absolute top-md right-md z-10">
						<Popover>
							<PopoverTrigger asChild onClick={(e) => e.stopPropagation()}>
								<Button variant="ghost" size="icon" className="size-xl rounded-full">
									<MoreHorizontal className="size-md" />
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
												className={`justify-start flex items-center gap-xs ${action === "Delete" ? "text-destructive hover:bg-destructive/10" : ""}`}
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
												{action === "Pin" && <Pin className="size-md" />}
												{action === "Edit Tags" && <Tag className="size-md" />}
												{action === "Archive" && <Archive className="size-md" />}
												{action === "Delete" && <X className="size-md" />}
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

			<ConfirmationDialog
				open={Boolean(attachmentConflict)}
				onOpenChange={(open) => !open && setAttachmentConflict(null)}
				title="Book is attached to courses"
				description={attachmentConflictDescription}
				confirmText="Delete anyway"
				onConfirm={handleConfirmForceDelete}
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

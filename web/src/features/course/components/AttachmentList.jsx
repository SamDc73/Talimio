/**
 * AttachmentList Component
 *
 * Lists the books attached to a course. Unlinking removes the book from this
 * course only — the book stays in the library with its file and embeddings.
 */

import { Archive, BookOpen, Unlink } from "lucide-react"
import { Button } from "@/components/Button"
import { Card } from "@/components/Card"
import AttachmentStatusBadge from "@/features/course/components/AttachmentStatusBadge"

function AttachmentList({ attachments, onDetach, detachingId = null, isLoading = false, emptyState = null }) {
	if (isLoading) {
		return (
			<Card>
				<div className="p-6 space-y-3">
					{[0, 1, 2].map((row) => (
						<div key={row} className="h-12 rounded-md bg-muted animate-pulse" />
					))}
				</div>
			</Card>
		)
	}

	if (!attachments || attachments.length === 0) {
		return emptyState
	}

	return (
		<Card>
			<ul className="divide-y divide-border">
				{attachments.map((attachment) => (
					<li key={attachment.id} className="flex items-center justify-between gap-4 px-4 py-3">
						<div className="flex min-w-0 items-center gap-3">
							<div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted">
								<BookOpen className="size-4 text-muted-foreground" />
							</div>
							<div className="min-w-0">
								<p className="truncate text-sm font-medium text-foreground">{attachment.title}</p>
								<p className="text-xs text-muted-foreground">
									Attached {attachment.createdAt ? new Date(attachment.createdAt).toLocaleDateString() : ""}
								</p>
							</div>
							{attachment.archived && (
								<span
									title="Archived in your library; it still grounds this course"
									className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground"
								>
									<Archive className="size-3" />
									Archived
								</span>
							)}
						</div>

						<div className="flex shrink-0 items-center gap-3">
							<AttachmentStatusBadge ragStatus={attachment.ragStatus} />
							<Button
								variant="ghost"
								size="sm"
								onClick={() => onDetach(attachment)}
								disabled={detachingId === attachment.id}
								title="Remove from this course (the book stays in your library)"
							>
								<Unlink className="size-4 mr-1.5" />
								Unlink
							</Button>
						</div>
					</li>
				))}
			</ul>
		</Card>
	)
}

export default AttachmentList

/**
 * DocumentsView Component — course attachments panel.
 *
 * Courses ground themselves in library books through attachments:
 * - Lists attached books with embedding status
 * - Attach picker over the user's library
 * - Unlink removes the link only; the book stays in the library
 */

import { BookOpen, CheckCircle2, Plus } from "lucide-react"
import { useMemo, useState } from "react"
import { Button } from "@/components/Button"
import { Card } from "@/components/Card"
import { ConfirmationDialog } from "@/components/ConfirmationDialog"
import {
	isAttachmentProcessing,
	useAttachBooks,
	useCourseAttachments,
	useDetachAttachment,
} from "@/features/course/api/attachmentsApi"
import { useCourseContext } from "@/features/course/CourseContext"
import AttachBooksModal from "@/features/course/components/AttachBooksModal"
import AttachmentList from "@/features/course/components/AttachmentList"
import logger from "@/lib/logger"

function DocumentsView() {
	const { courseId } = useCourseContext()
	const [showAttachModal, setShowAttachModal] = useState(false)
	const [pendingDetach, setPendingDetach] = useState(null)

	const { data: attachments = [], isLoading } = useCourseAttachments(courseId)
	const attachBooks = useAttachBooks(courseId)
	const detachAttachment = useDetachAttachment(courseId)

	const attachedBookIds = useMemo(() => attachments.map((attachment) => attachment.bookId), [attachments])

	const groundingStatus = useMemo(() => {
		if (attachments.length === 0) {
			return { status: "none", message: "No books attached" }
		}
		if (attachments.some((attachment) => isAttachmentProcessing(attachment))) {
			return { status: "processing", message: "Books are being embedded..." }
		}
		const readyCount = attachments.filter((attachment) => attachment.ragStatus === "completed").length
		if (readyCount === attachments.length) {
			return { status: "ready", message: "All attached books are searchable" }
		}
		return { status: "partial", message: `${readyCount}/${attachments.length} books searchable` }
	}, [attachments])

	const statusIndicatorClass = {
		ready: "bg-completed",
		processing: "bg-upcoming animate-pulse",
		partial: "bg-due-today",
		none: "bg-muted-foreground/60",
	}[groundingStatus.status]

	const handleAttach = async (bookIds) => {
		try {
			await attachBooks.mutateAsync(bookIds)
			logger.track("books_attached", { courseId, count: bookIds.length })
		} catch (error) {
			logger.error("Failed to attach books", error, { courseId })
			throw error
		}
	}

	const handleConfirmDetach = async () => {
		const attachment = pendingDetach
		setPendingDetach(null)
		if (!attachment) return
		try {
			await detachAttachment.mutateAsync(attachment.id)
			logger.track("book_detached", { courseId, attachmentId: attachment.id })
		} catch (error) {
			logger.error("Failed to detach book", error, { courseId, attachmentId: attachment.id })
		}
	}

	return (
		<div className="flex-1 flex flex-col h-full bg-muted/20">
			{/* Header */}
			<div className="bg-card border-b border-border px-6 py-4">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-xl font-semibold text-foreground">Course Books</h1>
						<p className="text-sm text-muted-foreground mt-1">
							Attach books from your library to ground lessons, search, and the assistant
						</p>
					</div>

					<Button onClick={() => setShowAttachModal(true)} size="sm">
						<Plus className="size-4 mr-2" />
						Attach Books
					</Button>
				</div>
			</div>

			{/* Main Content */}
			<div className="flex-1 p-6 overflow-auto">
				<div className="max-w-6xl mx-auto space-y-6">
					{/* Grounding Status Card */}
					<Card>
						<div className="p-4">
							<div className="flex items-center justify-between">
								<div className="flex items-center space-x-3">
									<div className={`size-3 rounded-full ${statusIndicatorClass}`} />
									<div>
										<h3 className="text-sm font-medium text-foreground">Source Grounding</h3>
										<p className="text-sm text-muted-foreground">{groundingStatus.message}</p>
									</div>
								</div>

								{groundingStatus.status === "ready" && <CheckCircle2 className="size-5 text-completed" />}
								{groundingStatus.status === "processing" && (
									<div className="size-5 border-2 border-upcoming border-t-transparent rounded-full animate-spin" />
								)}
							</div>
						</div>
					</Card>

					{/* Attachments List */}
					<AttachmentList
						attachments={attachments}
						isLoading={isLoading}
						onDetach={(attachment) => setPendingDetach(attachment)}
						detachingId={detachAttachment.isPending ? detachAttachment.variables : null}
						emptyState={
							<div className="text-center py-12">
								<div className="size-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
									<BookOpen className="size-8 text-muted-foreground" />
								</div>
								<h3 className="text-lg font-medium text-foreground mb-2">No books attached</h3>
								<p className="mx-auto mb-6 max-w-container-md text-muted-foreground">
									Attach books from your library to enable grounded lesson generation and source-cited assistant
									answers.
								</p>
								<Button onClick={() => setShowAttachModal(true)}>
									<Plus className="size-4 mr-2" />
									Attach Your First Book
								</Button>
							</div>
						}
					/>
				</div>
			</div>

			{/* Attach Picker */}
			<AttachBooksModal
				isOpen={showAttachModal}
				onClose={() => setShowAttachModal(false)}
				attachedBookIds={attachedBookIds}
				onAttach={handleAttach}
				isAttaching={attachBooks.isPending}
			/>

			{/* Unlink Confirmation */}
			<ConfirmationDialog
				open={Boolean(pendingDetach)}
				onOpenChange={(open) => !open && setPendingDetach(null)}
				title="Remove book from this course?"
				description={`"${pendingDetach?.title ?? ""}" will no longer ground this course. The book stays in your library with its file and embeddings.`}
				confirmText="Remove from course"
				cancelText="Keep"
				onConfirm={handleConfirmDetach}
			/>
		</div>
	)
}

export default DocumentsView

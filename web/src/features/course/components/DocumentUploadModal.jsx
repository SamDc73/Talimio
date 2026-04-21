import { AlertTriangle, CheckCircle2 } from "lucide-react"
import { useCallback, useState } from "react"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogTitle } from "@/components/Dialog"
import { useDocumentsService } from "../api/documentsApi"
import { DocumentStatusProgress } from "./DocumentStatusBadge"
import DocumentUploader from "./DocumentUploader"

function DocumentUploadModal({ isOpen, onClose, courseId, onDocumentsUploaded = null, maxFiles = 5 }) {
	const [documents, setDocuments] = useState([])
	const [isUploading, setIsUploading] = useState(false)
	const [uploadResults, setUploadResults] = useState(null)

	const documentsService = useDocumentsService(courseId)

	const handleDocumentsChange = useCallback((newDocuments) => {
		setDocuments(newDocuments)
		setUploadResults(null)
	}, [])

	const handleUpload = async () => {
		if (documents.length === 0) {
			return
		}

		setIsUploading(true)
		setUploadResults(null)

		try {
			const processingDocs = documents.map((doc) => ({
				...doc,
				status: "processing",
			}))
			setDocuments(processingDocs)

			const results = await documentsService.uploadMultipleDocuments(documents.map((doc, index) => ({ ...doc, index })))

			setUploadResults(results)

			const updatedDocs = documents.map((doc) => {
				const result = results.results.find((r) => r.originalIndex === doc.index)
				const error = results.errors.find((e) => e.originalIndex === doc.index)

				if (result) {
					return { ...doc, status: "embedded", id: result.id }
				}
				if (error) {
					return { ...doc, status: "failed", error: error.error }
				}
				return doc
			})

			setDocuments(updatedDocs)

			if (results.errors.length === 0) {
				setTimeout(() => {
					handleClose()
				}, 2000)
			}

			if (onDocumentsUploaded && results.results.length > 0) {
				onDocumentsUploaded(results.results)
			}
		} catch (error) {
			const failedDocs = documents.map((doc) => ({
				...doc,
				status: "failed",
				error: error.message || "Upload failed",
			}))
			setDocuments(failedDocs)
		} finally {
			setIsUploading(false)
		}
	}

	const handleClose = () => {
		if (!isUploading) {
			setDocuments([])
			setUploadResults(null)
			onClose()
		}
	}

	const handleRetryFailed = () => {
		const failedDocs = documents.filter((doc) => doc.status === "failed")
		if (failedDocs.length > 0) {
			const resetDocs = documents.map((doc) =>
				doc.status === "failed" ? { ...doc, status: "pending", error: undefined } : doc
			)
			setDocuments(resetDocs)
			setUploadResults(null)
		}
	}

	const handleOpenChange = (nextOpen) => {
		if (!nextOpen) {
			handleClose()
		}
	}

	const hasDocuments = documents.length > 0
	const hasFailedDocuments = documents.some((doc) => doc.status === "failed")
	const hasSuccessfulDocuments = documents.some((doc) => doc.status === "embedded")
	const allCompleted =
		documents.length > 0 && documents.every((doc) => doc.status === "embedded" || doc.status === "failed")
	const uploadErrors = Array.isArray(uploadResults?.errors) ? uploadResults.errors : []

	return (
		<Dialog open={isOpen} onOpenChange={handleOpenChange}>
			<DialogContent className="max-w-3xl gap-0 p-0 max-h-[90vh] overflow-y-auto">
				<div className="flex items-center border-b border-border p-6 pr-14">
					<DialogTitle className="text-xl font-semibold text-foreground">Add Documents to Course</DialogTitle>
				</div>

				<div className="p-6">
					<div className="mb-6">
						<DocumentUploader
							onDocumentsChange={handleDocumentsChange}
							initialDocuments={documents}
							maxFiles={maxFiles}
							disabled={isUploading}
							showPreview={true}
						/>
					</div>

					{isUploading && documents.length > 0 && (
						<div className="mb-6 space-y-3">
							<h3 className="text-sm font-medium text-foreground">Upload Progress</h3>
							{documents.map((doc) => (
								<div key={doc.id} className="bg-muted/40 dark:bg-background/70 rounded-lg p-3">
									<div className="flex items-center justify-between mb-2">
										<span className="text-sm font-medium text-foreground truncate">{doc.title}</span>
									</div>
									<DocumentStatusProgress status={doc.status} />
									{doc.error && <p className="mt-1 text-xs text-destructive">{doc.error}</p>}
								</div>
							))}
						</div>
					)}

					{uploadResults && allCompleted && (
						<div className="mb-6">
							{uploadResults.results.length > 0 && (
								<div className="mb-3 rounded-lg border border-completed/30 bg-completed/10 p-4">
									<div className="flex items-center space-x-2">
										<CheckCircle2 className="size-5 text-completed" />
										<p className="text-sm font-medium text-completed">
											{uploadResults.results.length} document(s) uploaded successfully
										</p>
									</div>
								</div>
							)}

							{uploadErrors.length > 0 && (
								<div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 dark:bg-destructive/5">
									<div className="mb-2 flex items-center space-x-2">
										<AlertTriangle className="size-5 text-destructive" />
										<p className="text-sm font-medium text-destructive">
											{uploadErrors.length} document(s) failed to upload
										</p>
									</div>
									<div className="space-y-1">
										{uploadErrors.map((error) => (
											<p
												key={`${error.document?.id ?? error.document?.title ?? "document"}-${error.originalIndex ?? error.error}`}
												className="text-xs text-destructive/90"
											>
												• {error.document.title}: {error.error}
											</p>
										))}
									</div>
								</div>
							)}
						</div>
					)}

					{!isUploading && !uploadResults && (
						<div className="mb-6 rounded-lg border border-upcoming/20 bg-upcoming/10 p-4">
							<p className="text-sm text-upcoming-text">
								<strong>Document Integration:</strong> Uploaded documents will be processed and integrated into the
								course's RAG system, making them searchable during lessons and assistant conversations.
							</p>
						</div>
					)}
				</div>

				<div className="flex justify-end space-x-3 p-6 border-t border-border">
					<Button type="button" variant="outline" onClick={handleClose} disabled={isUploading}>
						{allCompleted && hasSuccessfulDocuments ? "Close" : "Cancel"}
					</Button>

					{hasFailedDocuments && !isUploading && (
						<Button
							type="button"
							variant="outline"
							onClick={handleRetryFailed}
							className="border-due-today/40 text-due-today-text hover:bg-due-today/10"
						>
							Retry Failed
						</Button>
					)}

					{!allCompleted && (
						<Button
							type="button"
							onClick={handleUpload}
							disabled={!hasDocuments || isUploading}
							className="min-w-[120px]"
						>
							{isUploading ? (
								<div className="flex items-center space-x-2">
									<div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									<span>Uploading...</span>
								</div>
							) : (
								`Upload ${documents.length} Document${documents.length === 1 ? "" : "s"}`
							)}
						</Button>
					)}
				</div>
			</DialogContent>
		</Dialog>
	)
}

export default DocumentUploadModal

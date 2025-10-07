/**
 * DocumentUploadModal Component
 *
 * Modal for adding documents to an existing course:
 * - Reuses DocumentUploader component
 * - Handles upload progress and status
 * - Provides immediate feedback
 * - Auto-closes on successful upload
 * - Error handling and retry options
 */

import { AlertTriangle, CheckCircle2, X } from "lucide-react"
import { useCallback, useState } from "react"
import { Button } from "@/components/button"
import { useDocumentsService } from "../api/documentsApi"
import { DocumentStatusProgress } from "./DocumentStatusBadge"
import DocumentUploader from "./DocumentUploader"

function DocumentUploadModal({ isOpen, onClose, courseId, onDocumentsUploaded = null, maxFiles = 5 }) {
	const [documents, setDocuments] = useState([])
	const [isUploading, setIsUploading] = useState(false)
	const [uploadResults, setUploadResults] = useState(null)
	const [_uploadProgress, setUploadProgress] = useState({})

	const documentsService = useDocumentsService(courseId)

	// Handle document changes from uploader
	const handleDocumentsChange = useCallback((newDocuments) => {
		setDocuments(newDocuments)
		setUploadResults(null) // Clear previous results
	}, [])

	// Handle upload process
	const handleUpload = async () => {
		if (documents.length === 0) {
			return
		}

		setIsUploading(true)
		setUploadResults(null)

		try {
			// Update document status to processing for UI feedback
			const processingDocs = documents.map((doc) => ({
				...doc,
				status: "processing",
			}))
			setDocuments(processingDocs)

			// Upload documents
			const results = await documentsService.uploadMultipleDocuments(documents.map((doc, index) => ({ ...doc, index })))

			setUploadResults(results)

			// Update document status based on results
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

			// Show success/error toast
			if (results.errors.length === 0) {
				// Auto-close modal after successful upload
				setTimeout(() => {
					handleClose()
				}, 2000)
			} else if (results.results.length === 0) {
			} else {
			}

			// Notify parent component
			if (onDocumentsUploaded && results.results.length > 0) {
				onDocumentsUploaded(results.results)
			}
		} catch (error) {
			// Update all documents to failed status
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

	// Handle modal close
	const handleClose = () => {
		if (!isUploading) {
			setDocuments([])
			setUploadResults(null)
			setUploadProgress({})
			onClose()
		}
	}

	// Handle retry for failed documents
	const handleRetryFailed = () => {
		const failedDocs = documents.filter((doc) => doc.status === "failed")
		if (failedDocs.length > 0) {
			// Reset failed documents to pending
			const resetDocs = documents.map((doc) =>
				doc.status === "failed" ? { ...doc, status: "pending", error: undefined } : doc
			)
			setDocuments(resetDocs)
			setUploadResults(null)
		}
	}

	if (!isOpen) return null

	const hasDocuments = documents.length > 0
	const hasFailedDocuments = documents.some((doc) => doc.status === "failed")
	const hasSuccessfulDocuments = documents.some((doc) => doc.status === "embedded")
	const allCompleted =
		documents.length > 0 && documents.every((doc) => doc.status === "embedded" || doc.status === "failed")

	return (
		<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
			<div className="bg-white dark:bg-gray-800 rounded-lg max-w-3xl w-full mx-4 shadow-xl max-h-[90vh] overflow-y-auto">
				{/* Header */}
				<div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
					<h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Add Documents to Course</h2>
					<button
						type="button"
						onClick={handleClose}
						disabled={isUploading}
						className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors disabled:opacity-50"
					>
						<X className="h-6 w-6" />
					</button>
				</div>

				{/* Content */}
				<div className="p-6">
					{/* Document Uploader */}
					<div className="mb-6">
						<DocumentUploader
							onDocumentsChange={handleDocumentsChange}
							initialDocuments={documents}
							maxFiles={maxFiles}
							disabled={isUploading}
							showPreview={true}
						/>
					</div>

					{/* Upload Progress */}
					{isUploading && documents.length > 0 && (
						<div className="mb-6 space-y-3">
							<h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Upload Progress</h3>
							{documents.map((doc) => (
								<div key={doc.id} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
									<div className="flex items-center justify-between mb-2">
										<span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{doc.title}</span>
									</div>
									<DocumentStatusProgress status={doc.status} />
									{doc.error && <p className="text-xs text-red-600 mt-1">{doc.error}</p>}
								</div>
							))}
						</div>
					)}

					{/* Upload Results Summary */}
					{uploadResults && allCompleted && (
						<div className="mb-6">
							{uploadResults.results.length > 0 && (
								<div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 mb-3">
									<div className="flex items-center space-x-2">
										<CheckCircle2 className="w-5 h-5 text-green-600" />
										<p className="text-sm font-medium text-green-800 dark:text-green-300">
											{uploadResults.results.length} document(s) uploaded successfully
										</p>
									</div>
								</div>
							)}

							{uploadResults.errors.length > 0 && (
								<div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
									<div className="flex items-center space-x-2 mb-2">
										<AlertTriangle className="w-5 h-5 text-red-600" />
										<p className="text-sm font-medium text-red-800 dark:text-red-300">
											{uploadResults.errors.length} document(s) failed to upload
										</p>
									</div>
									<div className="space-y-1">
										{uploadResults.errors.map((error, index) => (
											<p key={`${error.document.title}-${index}`} className="text-xs text-red-700 dark:text-red-400">
												• {error.document.title}: {error.error}
											</p>
										))}
									</div>
								</div>
							)}
						</div>
					)}

					{/* Info Section */}
					{!isUploading && !uploadResults && (
						<div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
							<p className="text-sm text-blue-700 dark:text-blue-300">
								<strong>Document Integration:</strong> Uploaded documents will be processed and integrated into the
								course's RAG system, making them searchable during lessons and assistant conversations.
							</p>
						</div>
					)}
				</div>

				{/* Actions */}
				<div className="flex justify-end space-x-3 p-6 border-t border-gray-200 dark:border-gray-700">
					<Button type="button" variant="outline" onClick={handleClose} disabled={isUploading}>
						{allCompleted && hasSuccessfulDocuments ? "Close" : "Cancel"}
					</Button>

					{hasFailedDocuments && !isUploading && (
						<Button
							type="button"
							variant="outline"
							onClick={handleRetryFailed}
							className="text-orange-600 border-orange-600 hover:bg-orange-50"
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
									<div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
									<span>Uploading...</span>
								</div>
							) : (
								`Upload ${documents.length} Document${documents.length !== 1 ? "s" : ""}`
							)}
						</Button>
					)}
				</div>
			</div>
		</div>
	)
}

export default DocumentUploadModal

/**
 * DocumentsView Component
 *
 * Main view for managing course documents in the documents tab:
 * - Lists all course documents with status
 * - Upload new documents functionality
 * - Document search and filtering
 * - Document management actions
 * - RAG integration status
 */

import { CheckCircle2, Plus, RefreshCw, Search } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Button } from "@/components/Button"
import { Card } from "@/components/Card"
import DocumentList from "@/features/course/components/DocumentList"
import { DocumentStatusSummary } from "@/features/course/components/DocumentStatusBadge"
import DocumentUploadModal from "@/features/course/components/DocumentUploadModal"
import logger from "@/lib/logger"
import { usePolling } from "../hooks/usePolling"
import { useDocumentsService } from "../api/documentsApi"

const POLLING_INTERVAL = 5000 // 5 seconds

function DocumentsView({ courseId }) {
	const [documents, setDocuments] = useState([])
	const [isLoading, setIsLoading] = useState(true)
	const [isRefreshing, setIsRefreshing] = useState(false)
	const [showUploadModal, setShowUploadModal] = useState(false)
	const [_selectedDocument, setSelectedDocument] = useState(null)

	const documentsService = useDocumentsService(courseId)

	// Use refs to maintain stable references
	const documentsServiceRef = useRef(documentsService)

	// Update refs when dependencies change
	useEffect(() => {
		documentsServiceRef.current = documentsService
	}, [documentsService])

	// Stable loadDocuments function that won't cause re-renders
	const loadDocuments = useCallback(
		async (showRefreshIndicator = false) => {
			try {
				if (showRefreshIndicator) {
					setIsRefreshing(true)
				} else {
					setIsLoading(true)
				}

				const response = await documentsServiceRef.current.fetchDocuments({
					limit: 50,
				})

				if (response?.documents) {
					setDocuments(response.documents)
				} else {
					setDocuments([])
				}
			} catch (error) {
				logger.error("Failed to load documents", error, { courseId })
			} finally {
				setIsLoading(false)
				setIsRefreshing(false)
			}
		},
		[courseId] // courseId is used in the catch block
	)

	const { startPolling, stopPolling } = usePolling(() => loadDocuments(true), POLLING_INTERVAL, [loadDocuments])

	const documentsProcessing = useMemo(() => {
		return documents.some((doc) => doc?.status === "processing" || doc?.status === "pending")
	}, [documents])

	useEffect(() => {
		if (courseId) {
			loadDocuments()
		}
	}, [courseId, loadDocuments]) // loadDocuments is now stable

	useEffect(() => {
		if (documentsProcessing) {
			startPolling()
		} else {
			stopPolling()
		}

		return () => {
			stopPolling()
		}
	}, [documentsProcessing, startPolling, stopPolling])

	const handleDocumentsUploaded = useCallback(
		async (uploadedDocuments) => {
			setDocuments((prev) => [...uploadedDocuments, ...prev])
			logger.track("documents_uploaded", {
				courseId,
				count: uploadedDocuments.length,
			})
			startPolling()
		},
		[startPolling, courseId]
	)

	const handleRemoveDocument = useCallback(async (document) => {
		if (!window.confirm(`Are you sure you want to remove "${document.title}"? This action cannot be undone.`)) {
			return
		}

		try {
			await documentsServiceRef.current.deleteDocument(document.id)
			setDocuments((prev) => prev.filter((doc) => doc.id !== document.id))
			logger.track("document_deleted", {
				documentId: document.id,
				title: document.title,
			})
		} catch (error) {
			logger.error("Failed to remove document", error, {
				documentId: document.id,
			})
			// Could show an error modal or alert here if needed
		}
	}, [])

	const handleViewDocument = useCallback((document) => {
		setSelectedDocument(document)
		logger.track("document_view_attempted", {
			documentId: document.id,
		})
		// Feature not implemented yet - could show a modal explaining this
	}, [])

	const handleDownloadDocument = useCallback((document) => {
		logger.track("document_download_attempted", {
			documentId: document.id,
		})
		// Feature not implemented yet - could show a modal explaining this
	}, [])

	const ragStatus = useMemo(() => {
		const totalDocs = documents.length
		const readyDocs = documents.filter((doc) => documentsService.isDocumentReady(doc)).length

		if (totalDocs === 0) {
			return {
				status: "none",
				message: "No documents uploaded",
			}
		}

		if (documentsProcessing) {
			return {
				status: "processing",
				message: "Documents processing...",
			}
		}

		if (readyDocs === totalDocs) {
			return {
				status: "ready",
				message: "RAG system ready",
			}
		}

		return {
			status: "partial",
			message: `${readyDocs}/${totalDocs} documents ready`,
		}
	}, [documents, documentsProcessing, documentsService])

	const ragStatusIndicatorClass = useMemo(() => {
		switch (ragStatus.status) {
			case "ready":
				return "bg-completed"
			case "processing":
				return "bg-upcoming animate-pulse"
			case "partial":
				return "bg-due-today"
			default:
				return "bg-muted-foreground/60"
		}
	}, [ragStatus.status])

	return (
		<div className="flex-1 flex flex-col h-full bg-muted/20">
			{/* Header */}
			<div className="bg-card border-b border-border px-6 py-4">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-xl font-semibold text-foreground">Course Documents</h1>
						<p className="text-sm text-muted-foreground mt-1">
							Manage documents that enhance this course with RAG capabilities
						</p>
					</div>

					<div className="flex items-center space-x-3">
						<Button variant="outline" size="sm" onClick={() => loadDocuments(true)} disabled={isRefreshing}>
							<RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`} />
							Refresh
						</Button>

						<Button onClick={() => setShowUploadModal(true)} size="sm">
							<Plus className="w-4 h-4 mr-2" />
							Add Documents
						</Button>
					</div>
				</div>
			</div>

			{/* Main Content */}
			<div className="flex-1 p-6 overflow-auto">
				<div className="max-w-6xl mx-auto space-y-6">
					{/* RAG Status Card */}
					<Card>
						<div className="p-4">
							<div className="flex items-center justify-between">
								<div className="flex items-center space-x-3">
									<div className={`w-3 h-3 rounded-full ${ragStatusIndicatorClass}`} />

									<div>
										<h3 className="text-sm font-medium text-foreground">RAG Integration Status</h3>
										<p className="text-sm text-muted-foreground">{ragStatus.message}</p>
									</div>
								</div>

								{ragStatus.status === "ready" && <CheckCircle2 className="w-5 h-5 text-completed" />}

								{ragStatus.status === "processing" && (
									<div className="w-5 h-5 border-2 border-upcoming border-t-transparent rounded-full animate-spin" />
								)}
							</div>

							{documents.length > 0 && (
								<div className="mt-3 pt-3 border-t border-border">
									<DocumentStatusSummary documents={documents} />
								</div>
							)}
						</div>
					</Card>

					{/* Documents List */}
					<DocumentList
						documents={documents}
						onRemoveDocument={handleRemoveDocument}
						onViewDocument={handleViewDocument}
						onDownloadDocument={handleDownloadDocument}
						isLoading={isLoading}
						emptyMessage={
							<div className="text-center py-12">
								<div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
									<Search className="w-8 h-8 text-muted-foreground" />
								</div>
								<h3 className="text-lg font-medium text-foreground mb-2">No documents yet</h3>
								<p className="text-muted-foreground mb-6 max-w-md mx-auto">
									Upload documents to enable RAG-powered features like intelligent lesson generation and context-aware
									assistant responses.
								</p>
								<Button onClick={() => setShowUploadModal(true)}>
									<Plus className="w-4 h-4 mr-2" />
									Upload First Document
								</Button>
							</div>
						}
						showActions={true}
						showSearch={true}
						showFilter={true}
						showSorting={true}
					/>

					{/* Help Section */}
					{documents.length === 0 && (
						<Card>
							<div className="p-6">
								<h3 className="text-lg font-medium text-foreground mb-4">About Document-Enhanced Learning</h3>
								<div className="grid md:grid-cols-2 gap-6">
									<div>
										<h4 className="font-medium text-foreground mb-2">What you can upload:</h4>
										<ul className="text-sm text-muted-foreground space-y-1">
											<li>• PDF documents and research papers</li>
											<li>• Web articles and documentation URLs</li>
											<li>• Course materials and textbooks</li>
											<li>• Reference guides and manuals</li>
										</ul>
									</div>
									<div>
										<h4 className="font-medium text-foreground mb-2">RAG Benefits:</h4>
										<ul className="text-sm text-muted-foreground space-y-1">
											<li>• AI lessons generated from your content</li>
											<li>• Assistant answers with document citations</li>
											<li>• Personalized learning based on materials</li>
											<li>• Smart content discovery and search</li>
										</ul>
									</div>
								</div>
							</div>
						</Card>
					)}
				</div>
			</div>

			{/* Upload Modal */}
			<DocumentUploadModal
				isOpen={showUploadModal}
				onClose={() => setShowUploadModal(false)}
				courseId={courseId}
				onDocumentsUploaded={handleDocumentsUploaded}
				maxFiles={5}
			/>
		</div>
	)
}

export default DocumentsView

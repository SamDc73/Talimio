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
import { Button } from "../../../components/button"
import { Card } from "../../../components/card"
import { useToast } from "../../../hooks/use-toast"
import { usePolling } from "../../../hooks/usePolling"
import { useDocumentsService } from "../api/documentsApi"
import DocumentList from "../components/DocumentList"
import { DocumentStatusSummary } from "../components/DocumentStatusBadge"
import DocumentUploadModal from "../components/DocumentUploadModal"

const POLLING_INTERVAL = 5000 // 5 seconds

function DocumentsView({ courseId }) {
	const [documents, setDocuments] = useState([])
	const [isLoading, setIsLoading] = useState(true)
	const [isRefreshing, setIsRefreshing] = useState(false)
	const [showUploadModal, setShowUploadModal] = useState(false)
	const [_selectedDocument, setSelectedDocument] = useState(null)

	const documentsService = useDocumentsService(courseId)
	const { toast } = useToast()

	// Use refs to maintain stable references
	const documentsServiceRef = useRef(documentsService)
	const toastRef = useRef(toast)

	// Update refs when dependencies change
	useEffect(() => {
		documentsServiceRef.current = documentsService
		toastRef.current = toast
	}, [documentsService, toast])

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
				toastRef.current({
					title: "Failed to load documents",
					description: error.message || "Unable to fetch course documents. Please try again.",
					variant: "destructive",
				})
			} finally {
				setIsLoading(false)
				setIsRefreshing(false)
			}
		},
		[] // No dependencies - uses refs instead
	)

	const { startPolling, stopPolling } = usePolling(() => loadDocuments(true), POLLING_INTERVAL, [loadDocuments])

	const documentsProcessing = useMemo(() => {
		return documents.some((doc) => documentsService.isDocumentProcessing(doc))
	}, [documents, documentsService])

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
			toastRef.current({
				title: "Documents uploaded!",
				description: `${uploadedDocuments.length} document(s) added to the course.`,
			})
			startPolling()
		},
		[startPolling]
	)

	const handleRemoveDocument = useCallback(async (document) => {
		if (!window.confirm(`Are you sure you want to remove "${document.title}"? This action cannot be undone.`)) {
			return
		}

		try {
			await documentsServiceRef.current.deleteDocument(document.id)
			setDocuments((prev) => prev.filter((doc) => doc.id !== document.id))
			toastRef.current({
				title: "Document removed",
				description: `"${document.title}" has been removed from the course.`,
			})
		} catch (error) {
			toastRef.current({
				title: "Failed to remove document",
				description: error.message || "Unable to remove document. Please try again.",
				variant: "destructive",
			})
		}
	}, [])

	const handleViewDocument = useCallback((document) => {
		setSelectedDocument(document)
		toastRef.current({
			title: "Document view",
			description: "Document preview will be available in a future update.",
		})
	}, [])

	const handleDownloadDocument = useCallback((_document) => {
		toastRef.current({
			title: "Download requested",
			description: "Document download will be available in a future update.",
		})
	}, [])

	const ragStatus = useMemo(() => {
		const totalDocs = documents.length
		const readyDocs = documents.filter((doc) => documentsService.isDocumentReady(doc)).length

		if (totalDocs === 0) {
			return {
				status: "none",
				message: "No documents uploaded",
				color: "gray",
			}
		} else if (documentsProcessing) {
			return {
				status: "processing",
				message: "Documents processing...",
				color: "blue",
			}
		} else if (readyDocs === totalDocs) {
			return { status: "ready", message: "RAG system ready", color: "green" }
		} else {
			return {
				status: "partial",
				message: `${readyDocs}/${totalDocs} documents ready`,
				color: "orange",
			}
		}
	}, [documents, documentsService, documentsProcessing])

	return (
		<div className="flex-1 flex flex-col h-full bg-gray-50">
			{/* Header */}
			<div className="bg-white border-b border-gray-200 px-6 py-4">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-xl font-semibold text-gray-900">Course Documents</h1>
						<p className="text-sm text-gray-600 mt-1">
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
									<div
										className={`w-3 h-3 rounded-full ${
											ragStatus.color === "green"
												? "bg-green-500"
												: ragStatus.color === "blue"
													? "bg-blue-500 animate-pulse"
													: ragStatus.color === "orange"
														? "bg-orange-500"
														: "bg-gray-400"
										}`}
									/>
									<div>
										<h3 className="text-sm font-medium text-gray-900">RAG Integration Status</h3>
										<p className="text-sm text-gray-600">{ragStatus.message}</p>
									</div>
								</div>

								{ragStatus.status === "ready" && <CheckCircle2 className="w-5 h-5 text-green-500" />}

								{ragStatus.status === "processing" && (
									<div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
								)}
							</div>

							{documents.length > 0 && (
								<div className="mt-3 pt-3 border-t border-gray-200">
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
								<div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
									<Search className="w-8 h-8 text-gray-400" />
								</div>
								<h3 className="text-lg font-medium text-gray-900 mb-2">No documents yet</h3>
								<p className="text-gray-600 mb-6 max-w-md mx-auto">
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
								<h3 className="text-lg font-medium text-gray-900 mb-4">About Document-Enhanced Learning</h3>
								<div className="grid md:grid-cols-2 gap-6">
									<div>
										<h4 className="font-medium text-gray-900 mb-2">What you can upload:</h4>
										<ul className="text-sm text-gray-600 space-y-1">
											<li>• PDF documents and research papers</li>
											<li>• Web articles and documentation URLs</li>
											<li>• Course materials and textbooks</li>
											<li>• Reference guides and manuals</li>
										</ul>
									</div>
									<div>
										<h4 className="font-medium text-gray-900 mb-2">RAG Benefits:</h4>
										<ul className="text-sm text-gray-600 space-y-1">
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

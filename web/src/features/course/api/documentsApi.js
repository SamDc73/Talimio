/**
 * Documents API Service - RAG Document Management
 *
 * This service provides access to the RAG document endpoints for:
 * - Uploading documents (PDF files and URLs) to courses
 * - Managing document lists and status
 * - Searching documents with RAG
 * - Document deletion and metadata retrieval
 */

import { useMemo } from "react"
import { api } from "@/lib/apiClient"
import { useApi } from "../../../hooks/use-api"

/**
 * Hook for document operations
 * @param {string} courseId
 */
export function useDocumentsService(courseId = null) {
	// Document endpoints
	const getDocuments = useApi("/courses/{courseId}/documents")
	const searchDocuments = useApi("/courses/{courseId}/search", {
		method: "POST",
	})
	const getDocument = useApi("/documents/{documentId}")
	const deleteDocument = useApi("/documents/{documentId}", {
		method: "DELETE",
	})

	return useMemo(
		() => ({
			// ========== DOCUMENT UPLOAD OPERATIONS ==========

			/**
			 * Upload a PDF file to a course
			 * @param {File} file - PDF file to upload
			 * @param {string} title - Document title
			 * @param {Function} onProgress - Progress callback (optional)
			 * @returns {Promise<Object>} The uploaded document data
			 */
			async uploadPDFDocument(file, title, _onProgress = null) {
				if (!courseId) throw new Error("Course ID required")
				const formData = new FormData()
				formData.append("file", file)
				formData.append("document_type", "pdf")
				formData.append("title", title)

				return api.post(`/courses/${courseId}/documents`, formData)
			},

			/**
			 * Upload a URL as a document to a course
			 * @param {string} url - URL to process as document
			 * @param {string} title - Document title
			 * @returns {Promise<Object>} The uploaded document data
			 */
			async uploadURLDocument(url, title) {
				if (!courseId) throw new Error("Course ID required")
				const formData = new FormData()
				formData.append("url", url)
				formData.append("document_type", "url")
				formData.append("title", title)

				return api.post(`/courses/${courseId}/documents`, formData)
			},

			/**
			 * Upload multiple documents at once
			 * @param {Array} documents - Array of document objects with {file?, url?, title, type}
			 * @returns {Promise<Array>} Array of upload results
			 */
			async uploadMultipleDocuments(documents) {
				if (!courseId) throw new Error("Course ID required")

				const results = []
				const errors = []

				for (const doc of documents) {
					try {
						let result
						if (doc.type === "pdf" && doc.file) {
							result = await this.uploadPDFDocument(doc.file, doc.title)
						} else if (doc.type === "url" && doc.url) {
							result = await this.uploadURLDocument(doc.url, doc.title)
						} else {
							throw new Error("Invalid document format")
						}
						results.push({ ...result, originalIndex: doc.index })
					} catch (error) {
						errors.push({
							error: error.message,
							document: doc,
							originalIndex: doc.index,
						})
					}
				}

				return { results, errors }
			},

			// ========== DOCUMENT RETRIEVAL OPERATIONS ==========

			/**
			 * Get all documents for a course with pagination
			 * @param {Object} options - Query options
			 * @param {number} options.skip - Pagination offset (default: 0)
			 * @param {number} options.limit - Items per page (default: 20)
			 * @returns {Promise<Object>} Document list with pagination
			 */
			async fetchDocuments(options = {}) {
				if (!courseId) throw new Error("Course ID required")

				const { skip = 0, limit = 20 } = options
				const queryParams = { skip, limit }

				return await getDocuments.execute(null, {
					pathParams: { courseId: courseId },
					queryParams,
				})
			},

			/**
			 * Get a specific document by ID
			 * @param {string|number} documentId - Document ID
			 * @returns {Promise<Object>} Document details
			 */
			async fetchDocument(documentId) {
				if (!documentId) throw new Error("Document ID required")

				return await getDocument.execute(null, {
					pathParams: { documentId },
				})
			},

			/**
			 * Poll document status until processing is complete
			 * @param {string|number} documentId - Document ID
			 * @param {number} maxAttempts - Maximum polling attempts (default: 30)
			 * @param {number} interval - Poll interval in milliseconds (default: 2000)
			 * @returns {Promise<Object>} Final document status
			 */
			async pollDocumentStatus(documentId, maxAttempts = 30, interval = 2000) {
				let attempts = 0

				while (attempts < maxAttempts) {
					try {
						const document = await this.fetchDocument(documentId)

						// Check if processing is complete
						if (document.status === "embedded" || document.status === "failed") {
							return document
						}

						// Wait before next poll
						await new Promise((resolve) => setTimeout(resolve, interval))
						attempts++
					} catch (error) {
						attempts++

						if (attempts >= maxAttempts) {
							throw error
						}

						// Wait before retry
						await new Promise((resolve) => setTimeout(resolve, interval))
					}
				}

				throw new Error("Document processing timeout")
			},

			// ========== DOCUMENT SEARCH OPERATIONS ==========

			/**
			 * Search documents using RAG (vector similarity search)
			 * @param {string} query - Search query
			 * @param {number} topK - Number of results to return (default: 5)
			 * @returns {Promise<Object>} Search results with similarity scores
			 */
			async searchDocuments(query, topK = 5) {
				if (!courseId) throw new Error("Course ID required")
				if (!query?.trim()) throw new Error("Search query required")

				const searchData = {
					query: query.trim(),
					top_k: topK,
				}

				return await searchDocuments.execute(searchData, {
					pathParams: { courseId: courseId },
				})
			},

			// ========== DOCUMENT DELETION OPERATIONS ==========

			/**
			 * Delete a document
			 * @param {string|number} documentId - Document ID
			 * @returns {Promise<Object>} Deletion confirmation
			 */
			async deleteDocument(documentId) {
				if (!documentId) throw new Error("Document ID required")

				return await deleteDocument.execute(null, {
					pathParams: { documentId },
				})
			},

			/**
			 * Delete multiple documents
			 * @param {Array<string|number>} documentIds - Array of document IDs
			 * @returns {Promise<Object>} Deletion results
			 */
			async deleteMultipleDocuments(documentIds) {
				const results = []
				const errors = []

				for (const documentId of documentIds) {
					try {
						const result = await this.deleteDocument(documentId)
						results.push({ documentId, ...result })
					} catch (error) {
						errors.push({ documentId, error: error.message })
					}
				}

				return { results, errors }
			},

			// ========== UTILITY METHODS ==========

			/**
			 * Check if a document is ready for use (embedded status)
			 * @param {Object} document - Document object
			 * @returns {boolean} True if document is ready
			 */
			isDocumentReady(document) {
				return document?.status === "embedded"
			},

			/**
			 * Check if a document failed processing
			 * @param {Object} document - Document object
			 * @returns {boolean} True if document failed
			 */
			isDocumentFailed(document) {
				return document?.status === "failed"
			},

			/**
			 * Check if a document is still processing
			 * @param {Object} document - Document object
			 * @returns {boolean} True if document is processing
			 */
			isDocumentProcessing(document) {
				return document?.status === "processing" || document?.status === "pending"
			},

			/**
			 * Get document status display text
			 * @param {Object} document - Document object
			 * @returns {string} Human-readable status
			 */
			getDocumentStatusText(document) {
				switch (document?.status) {
					case "pending": {
						return "Pending"
					}
					case "processing": {
						return "Processing"
					}
					case "embedded": {
						return "Ready"
					}
					case "failed": {
						return "Failed"
					}
					default: {
						return "Unknown"
					}
				}
			},

			// ========== LOADING STATES AND ERRORS ==========

			/**
			 * Check if any operation is loading
			 */
			get isLoading() {
				return getDocuments.isLoading || searchDocuments.isLoading || getDocument.isLoading || deleteDocument.isLoading
			},

			/**
			 * Get any error that occurred
			 */
			get error() {
				return getDocuments.error || searchDocuments.error || getDocument.error || deleteDocument.error
			},
		}),
		[
			courseId,
			deleteDocument.error,
			deleteDocument.execute,
			deleteDocument.isLoading,
			getDocument.error,
			getDocument.execute,
			getDocument.isLoading,
			getDocuments.error,
			getDocuments.execute,
			getDocuments.isLoading,
			searchDocuments.error,
			searchDocuments.execute,
			searchDocuments.isLoading,
		] // Only courseId affects the service methods
	)
}

/**
 * Convenience hook for global document operations (no specific courseId)
 */
export function useDocumentsGlobalService() {
	return useDocumentsService()
}

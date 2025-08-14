/**
 * Document Utility Functions
 *
 * Pure utility functions for document status and processing checks.
 * Separated from components for better Fast Refresh compatibility.
 */

/**
 * Utility function to get status display text
 */
export const getStatusText = (status) => {
	const statusConfig = {
		pending: "Pending",
		processing: "Processing",
		embedded: "Ready",
		failed: "Failed",
	}

	return statusConfig[status] || "Unknown"
}

/**
 * Utility function to check if document is ready
 */
export const isDocumentReady = (document) => {
	return document?.status === "embedded"
}

/**
 * Utility function to check if document is processing
 */
export const isDocumentProcessing = (document) => {
	return document?.status === "processing" || document?.status === "pending"
}

/**
 * Utility function to check if document failed
 */
export const isDocumentFailed = (document) => {
	return document?.status === "failed"
}

import { ErrorBoundary } from "react-error-boundary"

/**
 * Error fallback component for PDF viewer
 * Handles PDF.js specific errors and provides retry functionality
 */
function PDFErrorFallback({ error, resetErrorBoundary }) {
	// Don't show error UI for PDF.js StrictMode errors
	if (
		error?.message?.includes("can't define property") ||
		error?.message?.includes("Object is not extensible") ||
		error?.name === "AbortException" ||
		error?.message?.includes("cancelled")
	) {
		// Automatically retry for these transient errors
		resetErrorBoundary()
		return null
	}

	return (
		<div className="pdf-error-boundary p-4 border border-red-500/20 rounded bg-red-500/5">
			<h3 className="text-lg font-semibold text-red-500 mb-2">PDF Loading Error</h3>
			<p className="text-sm text-gray-100-foreground mb-3">
				There was an issue loading the PDF. This might be a temporary problem.
			</p>
			<button
				type="button"
				onClick={resetErrorBoundary}
				className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-500/90"
			>
				Try Again
			</button>
		</div>
	)
}

/**
 * PDF Error Boundary wrapper using react-error-boundary
 * React 19 compliant - no class components
 */
function PDFErrorBoundary({ children }) {
	return (
		<ErrorBoundary
			FallbackComponent={PDFErrorFallback}
			onError={(error, _errorInfo) => {
				// Only log non-PDF.js StrictMode errors
				if (
					!error?.message?.includes("can't define property") &&
					!error?.message?.includes("Object is not extensible") &&
					error?.name !== "AbortException" &&
					!error?.message?.includes("cancelled")
				) {
				}
			}}
			onReset={() => {
				// Could clear any cached state here if needed
			}}
		>
			{children}
		</ErrorBoundary>
	)
}

export default PDFErrorBoundary

import { ErrorBoundary } from "react-error-boundary"

/**
 * Error fallback component for EPUB viewer
 * Handles EPUB.js specific errors and provides retry functionality
 */
function EPUBErrorFallback({ error, resetErrorBoundary }) {
	// Don't show error UI for EPUB.js StrictMode errors
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
		<div className="epub-error-boundary p-4 border border-destructive/20 rounded bg-destructive/5">
			<h3 className="text-lg font-semibold text-destructive mb-2">EPUB Loading Error</h3>
			<p className="text-sm text-muted-foreground mb-3">
				There was an issue loading the EPUB. This might be a temporary problem.
			</p>
			<button
				type="button"
				onClick={resetErrorBoundary}
				className="px-3 py-1 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90"
			>
				Try Again
			</button>
		</div>
	)
}

/**
 * EPUB Error Boundary wrapper using react-error-boundary
 * React 19 compliant - no class components
 */
function EPUBErrorBoundary({ children }) {
	return (
		<ErrorBoundary
			FallbackComponent={EPUBErrorFallback}
			onError={(error, _errorInfo) => {
				// Only log non-EPUB.js StrictMode errors
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

export default EPUBErrorBoundary

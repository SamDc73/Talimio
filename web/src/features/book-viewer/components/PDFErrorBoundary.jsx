import React from "react";

class PDFErrorBoundary extends React.Component {
	constructor(props) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error) {
		// Check if this is a PDF.js React StrictMode error
		if (
			error?.message?.includes("can't define property") ||
			error?.message?.includes("Object is not extensible") ||
			error?.name === "AbortException" ||
			error?.message?.includes("cancelled")
		) {
			console.warn(
				"[PDF.js] React StrictMode compatibility issue (suppressed):",
				error.message,
			);
			return { hasError: false }; // Don't render error UI for these
		}

		return { hasError: true, error };
	}

	componentDidCatch(error, errorInfo) {
		// Handle PDF.js specific errors
		if (
			error?.message?.includes("can't define property") ||
			error?.message?.includes("Object is not extensible") ||
			error?.name === "AbortException" ||
			error?.message?.includes("cancelled")
		) {
			console.warn(
				"[PDF.js] React StrictMode compatibility issue (suppressed):",
				error.message,
			);
			return;
		}

		// Log other errors normally
		console.error("PDF Error Boundary caught an error:", error, errorInfo);
		this.setState({ error, hasError: true });
	}

	render() {
		if (this.state.hasError) {
			return (
				<div className="pdf-error-boundary p-4 border border-destructive/20 rounded bg-destructive/5">
					<h3 className="text-lg font-semibold text-destructive mb-2">
						PDF Loading Error
					</h3>
					<p className="text-sm text-muted-foreground mb-3">
						There was an issue loading the PDF. This might be a temporary
						problem.
					</p>
					<button
						type="button"
						onClick={() => this.setState({ hasError: false, error: null })}
						className="px-3 py-1 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90"
					>
						Try Again
					</button>
				</div>
			);
		}

		return this.props.children;
	}
}

export default PDFErrorBoundary;

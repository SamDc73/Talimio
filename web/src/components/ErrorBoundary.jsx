import React from "react";

class ErrorBoundary extends React.Component {
	constructor(props) {
		super(props);
		this.state = { hasError: false, error: null, errorInfo: null };
	}

	static getDerivedStateFromError(_error) {
		return { hasError: true };
	}

	componentDidCatch(error, errorInfo) {
		console.error("ErrorBoundary caught an error:", error, errorInfo);
		this.setState({
			error: error,
			errorInfo: errorInfo,
		});
	}

	render() {
		if (this.state.hasError) {
			return (
				<div className="error-boundary p-4 m-4 border border-destructive rounded bg-destructive/10">
					<h2 className="text-xl font-bold text-destructive mb-2">
						Something went wrong
					</h2>
					<p className="text-sm text-muted-foreground mb-3">
						Don't worry - this error has been contained and won't break the rest
						of the app.
					</p>
					<button
						type="button"
						onClick={() =>
							this.setState({ hasError: false, error: null, errorInfo: null })
						}
						className="px-3 py-1 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90 mb-3"
					>
						Try Again
					</button>
					<details className="whitespace-pre-wrap text-sm text-destructive">
						<summary className="cursor-pointer hover:text-destructive/80">
							Technical Details
						</summary>
						<div className="mt-2 pt-2 border-t">
							{this.state.error?.toString()}
							<br />
							{this.state.errorInfo?.componentStack}
						</div>
					</details>
				</div>
			);
		}

		return this.props.children;
	}
}

export default ErrorBoundary;

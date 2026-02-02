import React from "react"
import logger from "@/lib/logger"

class ErrorBoundary extends React.Component {
	constructor(props) {
		super(props)
		this.state = { hasError: false, error: null, errorInfo: null }
	}

	static getDerivedStateFromError(_error) {
		return { hasError: true }
	}

	componentDidCatch(error, errorInfo) {
		this.setState({
			error: error,
			errorInfo: errorInfo,
		})

		logger.error("React Error Boundary caught error", error, {
			componentStack: errorInfo.componentStack,
			props: this.props,
		})
	}

	render() {
		if (this.state.hasError) {
			return (
				<div className="m-4 rounded-sm border border-destructive bg-destructive/10 p-4">
					<h2 className="text-xl font-bold text-destructive mb-2">Something went wrong</h2>
					<p className="text-sm text-muted-foreground mb-3">
						Don't worry - this error has been contained and won't break the rest of the app.
					</p>
					<button
						type="button"
						onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
						className="mb-3 rounded-sm bg-completed px-3 py-1 text-sm text-completed-text hover:bg-completed/90"
					>
						Try Again
					</button>
					<details className="whitespace-pre-wrap text-sm text-destructive">
						<summary className="cursor-pointer hover:text-destructive/80">Technical Details</summary>
						<div className="mt-2 pt-2 border-t">
							{this.state.error?.toString()}
							<br />
							{this.state.errorInfo?.componentStack}
						</div>
					</details>
				</div>
			)
		}

		return this.props.children
	}
}

export default ErrorBoundary

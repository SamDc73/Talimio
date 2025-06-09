import React from "react";

class ErrorBoundary extends React.Component {
	constructor(props) {
		super(props);
		this.state = { hasError: false, error: null, errorInfo: null };
	}

	static getDerivedStateFromError(error) {
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
				<div className="error-boundary p-4 m-4 border border-red-500 rounded bg-red-50">
					<h2 className="text-xl font-bold text-red-700 mb-2">
						Something went wrong
					</h2>
					<details className="whitespace-pre-wrap text-sm text-red-600">
						{this.state.error?.toString()}
						<br />
						{this.state.errorInfo?.componentStack}
					</details>
				</div>
			);
		}

		return this.props.children;
	}
}

export default ErrorBoundary;

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"

import App from "./App"
import ErrorBoundary from "./components/ErrorBoundary"

import "./app.css"

// Create a single QueryClient instance for the entire app
const queryClient = new QueryClient()

try {
	const rootElement = document.getElementById("root")

	if (!rootElement) {
		throw new Error("Root element with id 'root' not found")
	}

	createRoot(rootElement).render(
		<StrictMode>
			<ErrorBoundary>
				<QueryClientProvider client={queryClient}>
					<BrowserRouter>
						<App />
					</BrowserRouter>
				</QueryClientProvider>
			</ErrorBoundary>
		</StrictMode>
	)
} catch (error) {
	document.getElementById("root").innerHTML = `
      <div style="padding: 20px; color: #ef4444; background: #fef2f2; border: 1px solid #fee2e2; border-radius: 6px;">
        <h2 style="margin: 0 0 10px 0;">Application Initialization Error</h2>
        <pre style="margin: 0; white-space: pre-wrap;">${error.message}</pre>
      </div>
    `
}

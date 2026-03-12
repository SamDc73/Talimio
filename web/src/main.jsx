import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { HashRouter } from "react-router-dom"
import App from "@/App"
import ErrorBoundary from "@/components/ErrorBoundary"
import { TooltipProvider } from "@/components/Tooltip"
import { initializeFrontendObservability } from "@/lib/faro"
import logger from "@/lib/logger"

import "@/app.css"

// Create a single QueryClient instance for the entire app
const queryClient = new QueryClient()

const rootElement = document.getElementById("root")

if (!rootElement) {
	const initializationError = new Error("Root element with id 'root' not found")
	logger.error("Application bootstrap failed", initializationError)
	throw initializationError
}

initializeFrontendObservability()
logger.installGlobalErrorHandlers()

createRoot(rootElement).render(
	<StrictMode>
		<ErrorBoundary>
			<QueryClientProvider client={queryClient}>
				<HashRouter>
					<TooltipProvider>
						<App />
					</TooltipProvider>
				</HashRouter>
			</QueryClientProvider>
		</ErrorBoundary>
	</StrictMode>
)

import React, { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { checkRadixComponents, checkReactVersion } from "./utils/version-check";

import "./features/navigation/reset.css";
import "./index.css";

const init = async () => {
	try {
		// Check React version and features
		checkReactVersion();

		// Check Radix UI components
		if (import.meta.env.VITE_DEBUG_MODE === "true") {
			console.log("[Debug] Checking Radix UI components...");
		}
		const radixComponentsLoaded = await checkRadixComponents();

		if (!radixComponentsLoaded) {
			console.error("[Error] Failed to load required Radix UI components");
			return;
		}

		if (import.meta.env.VITE_DEBUG_MODE === "true") {
			console.log(
				"[Debug] All components loaded successfully, rendering app...",
			);
		}

		// Create root and render app
		createRoot(document.getElementById("root")).render(
			<StrictMode>
				<ErrorBoundary>
					<BrowserRouter>
						<App />
					</BrowserRouter>
				</ErrorBoundary>
			</StrictMode>,
		);
	} catch (error) {
		console.error("[Error] Failed to initialize application:", error);
		document.getElementById("root").innerHTML = `
      <div style="padding: 20px; color: #ef4444; background: #fef2f2; border: 1px solid #fee2e2; border-radius: 6px;">
        <h2 style="margin: 0 0 10px 0;">Application Initialization Error</h2>
        <pre style="margin: 0; white-space: pre-wrap;">${error.message}</pre>
      </div>
    `;
	}
};

init();

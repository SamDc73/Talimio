import {
	createReactRouterV7Options,
	getWebInstrumentations,
	initializeFaro,
	ReactIntegration,
} from "@grafana/faro-react"
import { getDefaultOTELInstrumentations, TracingInstrumentation } from "@grafana/faro-web-tracing"
import { createRoutesFromChildren, matchRoutes, Routes, useLocation, useNavigationType } from "react-router-dom"

const env = import.meta.env
// biome-ignore lint/correctness/noUndeclaredVariables: Vite injects this constant at build time.
const releaseVersion = __APP_VERSION__.trim()
const faroCollectorUrl = env.VITE_GRAFANA_FARO_URL?.trim()
const faroAppName = env.VITE_GRAFANA_FARO_APP_NAME?.trim()
const shouldInitializeFaro = Boolean(faroCollectorUrl && faroAppName)

export const frontendReleaseVersion = releaseVersion
export let faro = null

export const initializeFrontendObservability = () => {
	if (typeof window === "undefined" || !shouldInitializeFaro || faro) {
		return faro
	}

	const app = {
		name: faroAppName,
	}

	if (releaseVersion) {
		app.version = releaseVersion
	}

	faro =
		initializeFaro({
			url: faroCollectorUrl,
			app,
			sessionTracking: {
				enabled: true,
				persistent: true,
			},
			instrumentations: [
				...getWebInstrumentations(),
				new ReactIntegration({
					router: createReactRouterV7Options({
						createRoutesFromChildren,
						matchRoutes,
						Routes,
						useLocation,
						useNavigationType,
					}),
				}),
				new TracingInstrumentation({
					instrumentations: [...getDefaultOTELInstrumentations()],
				}),
			],
			experimental: {
				trackNavigation: true,
			},
		}) ?? null

	return faro
}

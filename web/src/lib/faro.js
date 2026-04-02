import {
	createReactRouterV7Options,
	getWebInstrumentations,
	InternalLoggerLevel,
	initializeFaro,
	ReactIntegration,
} from "@grafana/faro-react"
import { getDefaultOTELInstrumentations, TracingInstrumentation } from "@grafana/faro-web-tracing"
import { createRoutesFromChildren, matchRoutes, Routes, useLocation, useNavigationType } from "react-router-dom"

const env = import.meta.env
const FARO_SESSION_DISABLED_KEY = "faro-transport-disabled"
const FARO_TRANSPORT_FAILURE_TEXT = "Failed sending payload to the receiver"
// biome-ignore lint/correctness/noUndeclaredVariables: Vite injects this constant at build time.
const releaseVersion = __APP_VERSION__.trim()
const faroCollectorUrl = env.VITE_GRAFANA_FARO_URL?.trim()
const faroAppName = env.VITE_GRAFANA_FARO_APP_NAME?.trim()
const shouldInitializeFaro = Boolean(faroCollectorUrl && faroAppName)

export const frontendReleaseVersion = releaseVersion
export let faro = null

const isFaroTransportDisabled = () => {
	if (typeof window === "undefined") {
		return false
	}

	try {
		return window.sessionStorage.getItem(FARO_SESSION_DISABLED_KEY) === "1"
	} catch {
		return false
	}
}

const disableFaroTransportForSession = () => {
	if (typeof window === "undefined") {
		return
	}

	try {
		window.sessionStorage.setItem(FARO_SESSION_DISABLED_KEY, "1")
	} catch {
		// Ignore storage failures and fall back to pausing only this instance.
	}
}

const createFaroConsole = () => {
	const baseConsole = window.console

	return {
		...baseConsole,
		error: (...args) => {
			const hasTransportFailure = args.some(
				(value) => typeof value === "string" && value.includes(FARO_TRANSPORT_FAILURE_TEXT)
			)

			if (!hasTransportFailure) {
				baseConsole.error(...args)
				return
			}

			disableFaroTransportForSession()
			faro?.pause?.()

			if (import.meta.env.DEV) {
				baseConsole.warn("Faro transport is unavailable. Pausing frontend observability for this session.")
			}
		},
	}
}

export const initializeFrontendObservability = () => {
	if (typeof window === "undefined" || !shouldInitializeFaro || faro || isFaroTransportDisabled()) {
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
			internalLoggerLevel: InternalLoggerLevel.ERROR,
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
			unpatchedConsole: createFaroConsole(),
		}) ?? null

	return faro
}

import path from "node:path"
import { fileURLToPath } from "node:url"
import faroUploader from "@grafana/faro-rollup-plugin"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

const Dirname = path.dirname(fileURLToPath(import.meta.url))

const normalizeBasePath = (value) => {
	if (!value) return "/"
	if (value === "/") return "/"
	const withLeadingSlash = value.startsWith("/") ? value : `/${value}`
	return withLeadingSlash.endsWith("/") ? withLeadingSlash : `${withLeadingSlash}/`
}

const getTrimmedValue = (value) => value?.trim() || ""

const getReleaseVersion = (env) => {
	const configured = getTrimmedValue(env.VITE_RELEASE_VERSION)
	if (configured) return configured

	return getTrimmedValue(process.env.CF_PAGES_COMMIT_SHA)
}

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), "")
	const basePath = normalizeBasePath(env.VITE_BASE_PATH || "/")
	const releaseVersion = getReleaseVersion(env)
	const faroAppName = getTrimmedValue(env.VITE_GRAFANA_FARO_APP_NAME)
	const sourcemapEndpoint = getTrimmedValue(env.GRAFANA_FARO_SOURCEMAPS_ENDPOINT)
	const sourcemapApiKey = getTrimmedValue(env.GRAFANA_FARO_SOURCEMAPS_API_KEY)
	const faroAppId = getTrimmedValue(env.GRAFANA_FARO_APP_ID)
	const faroStackId = getTrimmedValue(env.GRAFANA_FARO_STACK_ID)
	const canUploadSourcemaps = Boolean(
		releaseVersion && faroAppName && sourcemapEndpoint && sourcemapApiKey && faroAppId && faroStackId
	)
	const plugins = [tailwindcss(), react()]

	if (canUploadSourcemaps) {
		plugins.push(
			faroUploader({
				appName: faroAppName,
				endpoint: sourcemapEndpoint,
				apiKey: sourcemapApiKey,
				appId: faroAppId,
				stackId: faroStackId,
				bundleId: releaseVersion,
				// Uploads sourcemaps in batches under the API's 30 MB uncompressed limit.
				gzipContents: true,
				// Vite emits maps into assets/, so the map `file` property needs the same prefix.
				prefixPath: "assets/",
			})
		)
	}

	return {
		base: basePath,
		plugins,
		build: {
			sourcemap: canUploadSourcemaps,
		},
		define: {
			// biome-ignore lint/style/useNamingConvention: Vite compile-time constant
			__APP_VERSION__: JSON.stringify(releaseVersion),
		},
		resolve: {
			alias: {
				"@": path.resolve(Dirname, "./src"),
			},
			dedupe: ["react", "react-dom"],
		},
		server: {
			port: Number.parseInt(env.VITE_DEV_SERVER_PORT || "5173", 10),
			fs: {
				allow: [".."],
			},
			watch: {
				usePolling: true,
				interval: 1000,
			},
			proxy: {
				"/api": {
					target: env.VITE_PROXY_TARGET || "http://localhost:8080",
					changeOrigin: true,
					secure: false,
					ws: true,
					configure: (proxy, _options) => {
						proxy.on("error", (_err, _req, _res) => {})
						proxy.on("proxyReq", (proxyReq, req, _res) => {
							// Forward cookies from the original request
							if (req.headers.cookie) {
								proxyReq.setHeader("Cookie", req.headers.cookie)
							}
						})
						proxy.on("proxyRes", (proxyRes, _req, _res) => {
							// Log set-cookie headers if present
							if (proxyRes.headers["set-cookie"]) {
							}
						})
					},
				},
			},
		},
	}
})

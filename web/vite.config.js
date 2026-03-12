import { execFileSync } from "node:child_process"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import faroUploader from "@grafana/faro-rollup-plugin"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

const Dirname = path.dirname(fileURLToPath(import.meta.url))
const JS_SOURCEMAP_PATTERN = /\.(js|ts|jsx|tsx|mjs|cjs)\.map$/

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

const createFaroSourceMapUploadPlugin = ({ endpoint, apiKey, appId, stackId, bundleId }) => ({
	name: "talimio-faro-sourcemap-uploader",
	async writeBundle(options) {
		const outputPath = options.dir || (options.file ? path.dirname(options.file) : process.cwd())
		const sourcemapEndpoint = `${endpoint}/app/${appId}/sourcemaps/${bundleId}`
		const filenames = await fs.promises.readdir(outputPath, { recursive: true })
		const sourceMapFiles = filenames
			.map((filename) => filename.toString())
			.filter((filename) => JS_SOURCEMAP_PATTERN.test(filename))

		if (sourceMapFiles.length === 0) {
			return
		}

		const tarballPath = path.join(outputPath, `faro-sourcemaps-${bundleId}.tar.gz`)

		try {
			execFileSync("tar", ["-czf", tarballPath, "-C", outputPath, ...sourceMapFiles], {
				stdio: "ignore",
			})
			const body = await fs.promises.readFile(tarballPath)
			const response = await fetch(sourcemapEndpoint, {
				method: "POST",
				headers: {
					Authorization: `Bearer ${stackId}:${apiKey}`,
					"Content-Type": "application/gzip",
				},
				body,
			})

			if (!response.ok) {
				const errorText = await response.text()
				throw new Error(`Faro sourcemap upload failed: ${response.status} ${errorText}`)
			}
		} finally {
			if (fs.existsSync(tarballPath)) {
				await fs.promises.unlink(tarballPath)
			}
		}
	},
})

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
				gzipContents: true,
				keepSourcemaps: true,
				prefixPath: "assets/",
				skipUpload: true,
			})
		)
		plugins.push(
			createFaroSourceMapUploadPlugin({
				endpoint: sourcemapEndpoint,
				apiKey: sourcemapApiKey,
				appId: faroAppId,
				stackId: faroStackId,
				bundleId: releaseVersion,
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
		optimizeDeps: {
			include: ["three", "@react-three/fiber", "@react-three/drei", "@react-three/postprocessing", "postprocessing"],
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

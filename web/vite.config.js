import path from "node:path"
import { fileURLToPath } from "node:url"
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

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), "")
	const basePath = normalizeBasePath(env.VITE_BASE_PATH || "/")

	return {
		base: basePath,
		plugins: [tailwindcss(), react()],
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
			port: Number.parseInt(env.VITE_DEV_SERVER_PORT || "5173"),
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

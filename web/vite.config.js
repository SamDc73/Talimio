import path from "node:path"
import { fileURLToPath } from "node:url"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

const Dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => {
	// Load env file based on `mode` in the current working directory.
	const env = loadEnv(mode, process.cwd(), "")

	return {
		plugins: [tailwindcss(), react()],
		resolve: {
			alias: {
				"@": path.resolve(Dirname, "./src"),
			},
		},
		optimizeDeps: {
			include: ["react-pdf", "pdfjs-dist", "react-window"],
			exclude: ["pdfjs-dist/build/pdf.worker.min.mjs"],
			esbuildOptions: {
				target: "esnext",
			},
		},
		build: {
			rollupOptions: {
				external: [/pdf\.worker\.min\.mjs$/],
			},
		},
		server: {
			port: Number.parseInt(env.VITE_DEV_SERVER_PORT || "5173"),
			proxy: {
				"/api": {
					target: env.VITE_PROXY_TARGET || "http://localhost:8080",
					changeOrigin: true,
					secure: false,
					ws: true,
					configure: (proxy, _options) => {
						proxy.on("error", (err, _req, _res) => {
							console.log("proxy error", err)
						})
						proxy.on("proxyReq", (proxyReq, req, _res) => {
							// Forward cookies from the original request
							if (req.headers.cookie) {
								proxyReq.setHeader("Cookie", req.headers.cookie)
							}
							console.log("Proxying:", req.method, req.url, "with cookies:", req.headers.cookie?.substring(0, 50))
						})
						proxy.on("proxyRes", (proxyRes, req, _res) => {
							console.log("Proxy response:", proxyRes.statusCode, req.url)
							// Log set-cookie headers if present
							if (proxyRes.headers["set-cookie"]) {
								console.log("Setting cookies:", proxyRes.headers["set-cookie"])
							}
						})
					},
				},
			},
		},
	}
})

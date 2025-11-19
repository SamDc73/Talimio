import path from "node:path"
import { fileURLToPath } from "node:url"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

const Dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), "")

	return {
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
		build: {
			// The PDF engine and app bundle are large; split vendor libs into separate chunks
			chunkSizeWarningLimit: 3000,
			rollupOptions: {
				output: {
					manualChunks(id) {
						if (!id.includes("node_modules")) return undefined
						if (id.includes("@embedpdf") || id.includes("pdfium")) return "pdf"
						if (id.includes("@uiw") || id.includes("@codemirror") || id.includes("codemirror")) return "codemirror"
						if (id.includes("@assistant-ui")) return "assistant"
						if (id.includes("@tanstack")) return "react-query"
						if (id.includes("framer-motion")) return "framer-motion"
						if (id.includes("katex") || id.includes("rehype-katex")) return "katex"
						if (id.includes("@mdx-js") || id.includes("remark") || id.includes("rehype")) return "mdx"
						if (id.includes("lucide-react")) return "icons"
						if (id.includes("three") || id.includes("@react-three") || id.includes("postprocessing")) return "three"
						if (id.includes("react-force-graph") || id.includes("reagraph") || id.includes("@cosmograph")) return "viz"
						return undefined
					},
				},
			},
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

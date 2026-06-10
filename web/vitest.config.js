import path from "node:path"
import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

const dirname = path.dirname(fileURLToPath(import.meta.url))
const APP_VERSION_DEFINE = "__APP_VERSION__"

export default defineConfig({
	plugins: [react()],
	define: {
		[APP_VERSION_DEFINE]: '"test"',
	},
	resolve: {
		alias: {
			"@": path.resolve(dirname, "./src"),
		},
	},
	test: {
		environment: "jsdom",
		setupFiles: "./src/test/setup.js",
	},
})

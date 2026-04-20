// ESLint config - only for what Biome doesn't handle
// Biome handles: jsx-key, no-children-prop, void-elements, duplicate-props, jsx-no-undef,
// forwardRef, exhaustive-deps, hooks-at-top-level, no-nested-ternaries, naming conventions,
// import-sorting, no-console, function-component-definition, etc.

import tanstackQuery from "@tanstack/eslint-plugin-query"
import betterTailwindcss from "eslint-plugin-better-tailwindcss"
import boundaries from "eslint-plugin-boundaries"
import importPlugin from "eslint-plugin-import"
import promisePlugin from "eslint-plugin-promise"
import react from "eslint-plugin-react"
import reactCompiler from "eslint-plugin-react-compiler"
import sonarjs from "eslint-plugin-sonarjs"
import unicorn from "eslint-plugin-unicorn"

export default [
	// Ignore build outputs and third-party files
	{
		ignores: ["dist/**", "node_modules/**", "build/**", "coverage/**", "public/pdf.worker.min.js", "**/*.min.js"],
	},

	// TanStack Query linting
	...tanstackQuery.configs["flat/recommended"],

	// Enforce module boundaries (feature isolation, shared unidirectional imports)
	{
		files: ["src/**/*.{js,jsx}"],
		plugins: {
			boundaries,
		},
		settings: {
			"boundaries/include": ["src/**/*.{js,jsx}"],
			"boundaries/elements": [
				{
					type: "feature",
					pattern: "src/features/*",
					mode: "folder",
					capture: ["elementName"],
				},
				{
					type: "page",
					pattern: "src/pages/*",
					mode: "file",
				},
				{ type: "shared", pattern: "src/components/**", mode: "file" },
				{ type: "shared", pattern: "src/contexts/**", mode: "file" },
				{ type: "shared", pattern: "src/hooks/**", mode: "file" },
				{ type: "shared", pattern: "src/lib/**", mode: "file" },
				{ type: "shared", pattern: "src/stores/**", mode: "file" },
				{ type: "shared", pattern: "src/utils/**", mode: "file" },
				{
					type: "app",
					pattern: "src/*.{js,jsx}",
					mode: "file",
				},
			],
			"import/resolver": {
				node: {
					extensions: [".js", ".jsx"],
				},
				typescript: {
					project: "./jsconfig.json",
					alwaysTryTypes: false,
				},
			},
		},
		rules: {
			"boundaries/element-types": [
				"error",
				{
					default: "disallow",
					rules: [
						{
							from: ["app"],
							allow: ["app", "shared", "page", "feature"],
						},
						{
							from: ["page"],
							allow: ["shared", "page", "feature"],
						},
						{
							from: ["shared"],
							allow: ["shared"],
						},
						{
							from: ["feature"],
							allow: ["shared", ["feature", { elementName: "${from.elementName}" }]],
						},
					],
				},
			],
		},
	},

	// Tailwind class linting/formatting
	{
		files: ["**/*.js", "**/*.jsx"],
		plugins: {
			"better-tailwindcss": betterTailwindcss,
		},
		settings: {
			"better-tailwindcss": {
				entryPoint: "src/app.css",
			},
		},
		rules: {
			...betterTailwindcss.configs["recommended-error"].rules,
			"better-tailwindcss/enforce-consistent-class-order": "off",
			"better-tailwindcss/enforce-consistent-line-wrapping": "off",
			"better-tailwindcss/no-unnecessary-whitespace": "off",
			"better-tailwindcss/no-unknown-classes": [
				"error",
				{
					detectComponentClasses: true,
					ignore: ["^aui-.*", "^epub-container$", "^lesson-mdx$"],
				},
			],
		},
	},

	// JavaScript files - rules Biome doesn't cover
	{
		files: ["**/*.js"],
		languageOptions: {
			ecmaVersion: 2024,
			sourceType: "module",
		},
		plugins: {
			import: importPlugin,
			sonarjs: sonarjs,
			unicorn: unicorn,
		},
		rules: {
			...sonarjs.configs.recommended.rules,
			"sonarjs/no-nested-conditional": "off",
			"sonarjs/cognitive-complexity": "off",
			"import/no-cycle": ["warn", { maxDepth: 1 }],
			"import/no-duplicates": "error",
			"import/no-restricted-paths": [
				"error",
				{
					zones: [
						{ target: "./src/features/assistant", from: "./src/features", except: ["./assistant"] },
						{ target: "./src/features/auth", from: "./src/features", except: ["./auth"] },
						{ target: "./src/features/book-viewer", from: "./src/features", except: ["./book-viewer"] },
						{ target: "./src/features/course", from: "./src/features", except: ["./course"] },
						{ target: "./src/features/home", from: "./src/features", except: ["./home"] },
						{ target: "./src/features/lesson", from: "./src/features", except: ["./lesson"] },
						{ target: "./src/features/video-viewer", from: "./src/features", except: ["./video-viewer"] },
						{
							target: ["./src/components", "./src/hooks", "./src/lib", "./src/types", "./src/utils"],
							from: ["./src/features", "./src/app"],
						},
						{ target: "./src/features", from: "./src/app" },
					],
				},
			],
		},
	},

	// JSX files - React rules Biome doesn't fully cover
	{
		files: ["**/*.jsx"],
		languageOptions: {
			ecmaVersion: 2024,
			sourceType: "module",
			parserOptions: {
				ecmaFeatures: {
					jsx: true,
				},
			},
		},
		plugins: {
			import: importPlugin,
			promise: promisePlugin,
			react: react,
			"react-compiler": reactCompiler,
			sonarjs: sonarjs,
			unicorn: unicorn,
		},
		settings: {
			react: {
				version: "19.1.1",
			},
		},
		rules: {
			...sonarjs.configs.recommended.rules,
			"sonarjs/no-nested-conditional": "off",
			"sonarjs/cognitive-complexity": "off",

			"import/no-cycle": ["warn", { maxDepth: 1 }],
			"import/no-duplicates": "error",

			// Enforce project structure (no cross-feature imports, unidirectional architecture)
			"import/no-restricted-paths": [
				"error",
				{
					zones: [
						{ target: "./src/features/assistant", from: "./src/features", except: ["./assistant"] },
						{ target: "./src/features/auth", from: "./src/features", except: ["./auth"] },
						{ target: "./src/features/book-viewer", from: "./src/features", except: ["./book-viewer"] },
						{ target: "./src/features/course", from: "./src/features", except: ["./course"] },
						{ target: "./src/features/home", from: "./src/features", except: ["./home"] },
						{ target: "./src/features/lesson", from: "./src/features", except: ["./lesson"] },
						{ target: "./src/features/video-viewer", from: "./src/features", except: ["./video-viewer"] },
						{
							target: ["./src/components", "./src/hooks", "./src/lib", "./src/types", "./src/utils"],
							from: ["./src/features", "./src/app"],
						},
						{ target: "./src/features", from: "./src/app" },
					],
				},
			],

			// React Compiler
			"react-compiler/react-compiler": "error",

			// React 19 rules (Biome doesn't cover these)
			"react/no-unknown-property": ["error", { ignore: ["css", "tw"] }],
			"react/display-name": "warn",
			"react/jsx-no-target-blank": "error",
			"react/no-danger-with-children": "error",
			"react/no-deprecated": "error",
			"react/no-direct-mutation-state": "error",
			"react/require-render-return": "error",

			// Promise best practices (Biome doesn't have these)
			"promise/catch-or-return": "error",
			"promise/no-return-wrap": "error",
			"promise/param-names": "error",
			"promise/always-return": "error",
			"promise/no-nesting": "warn",
			"promise/no-promise-in-callback": "warn",
			"promise/no-callback-in-promise": "warn",
		},
	},
]

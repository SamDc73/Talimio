// Minimal ESLint config - only for what Biome can't handle
import importPlugin from "eslint-plugin-import"
import promisePlugin from "eslint-plugin-promise"
import react from "eslint-plugin-react"
import reactCompiler from "eslint-plugin-react-compiler"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"

export default [
	// Ignore build outputs and third-party files
	{
		ignores: [
			"dist/**",
			"node_modules/**",
			"build/**",
			"coverage/**",
			"public/pdf.worker.min.js", // Exclude minified third-party files
			"**/*.min.js", // Exclude all minified files
		],
	},

	// JavaScript files - stricter rules
	{
		files: ["**/*.js"],
		languageOptions: {
			ecmaVersion: 2024,
			sourceType: "module",
		},
		plugins: {
			import: importPlugin,
		},
		rules: {
			"no-nested-ternary": "error", // Strict for JS files
			// Enforce project structure (no cross-feature imports, unidirectional architecture)
			"import/no-restricted-paths": [
				"error",
				{
					zones: [
						// Disable cross-feature imports: each feature can only import itself under src/features
						{ target: "./src/features/assistant", from: "./src/features", except: ["./assistant"] },
						{ target: "./src/features/auth", from: "./src/features", except: ["./auth"] },
						{ target: "./src/features/book-viewer", from: "./src/features", except: ["./book-viewer"] },
						{ target: "./src/features/course", from: "./src/features", except: ["./course"] },
						{ target: "./src/features/home", from: "./src/features", except: ["./home"] },
						{ target: "./src/features/lesson", from: "./src/features", except: ["./lesson"] },
						{ target: "./src/features/video-viewer", from: "./src/features", except: ["./video-viewer"] },
						// Unidirectional: shared cannot import from features/app
						{
							target: [
								"./src/components",
								"./src/hooks",
								"./src/lib",
								"./src/types",
								"./src/utils",
							],
							from: ["./src/features", "./src/app"],
						},
						// Unidirectional: features should not import from app (future-proof)
						{ target: "./src/features", from: "./src/app" },
					],
				},
			],
		},
	},

	// JSX files - React-specific rules
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
			"react-hooks": reactHooks,
			"react-refresh": reactRefresh,
			"react-compiler": reactCompiler,
		},
		settings: {
			react: {
				version: "19.1.1", // Specify React 19
			},
		},
			rules: {
				// Nested ternary - disabled for JSX files (handled by Biome for JS files)
				"no-nested-ternary": "off", // Off for JSX - common React pattern

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
								target: [
									"./src/components",
									"./src/hooks",
									"./src/lib",
									"./src/types",
									"./src/utils",
								],
								from: ["./src/features", "./src/app"],
							},
						{ target: "./src/features", from: "./src/app" },
					],
					},
				],

				// React Compiler - preparing for migration
				"react-compiler/react-compiler": "error",

				// React Hooks - essential for React development
				"react-hooks/rules-of-hooks": "error",
				"react-hooks/exhaustive-deps": "error", // Error for useEffect/useLayoutEffect only - critical for preventing race conditions
				// Note: React 19 auto-memoizes useMemo/useCallback, so we don't check their deps

				// React Refresh - ensure components can hot reload
				"react-refresh/only-export-components": [
					"warn",
					{
						allowConstantExport: true,
					},
				],

				// Promise best practices - Biome doesn't have these
				"promise/catch-or-return": "error",
				"promise/no-return-wrap": "error",
				"promise/param-names": "error",
				"promise/always-return": "error",
				"promise/no-nesting": "warn",
				"promise/no-promise-in-callback": "warn",
				"promise/no-callback-in-promise": "warn",

				// React 19 specific rules
				"react/jsx-uses-react": "off", // React 19 doesn't need React import
				"react/react-in-jsx-scope": "off", // React 19 doesn't need React in scope
				"react/no-unknown-property": ["error", { ignore: ["css", "tw"] }], // Allow CSS-in-JS
				"react/prop-types": "off", // Use TypeScript/JSDoc instead
				"react/display-name": "warn", // Helpful for debugging
				"react/jsx-no-target-blank": "error", // Security: prevent reverse tabnabbing

				// Function component definition (prefer function declarations)
				"react/function-component-definition": [
					"error",
					{
						namedComponents: "function-declaration",
						unnamedComponents: "function-expression",
					},
				],
				"react/jsx-key": ["error", { checkFragmentShorthand: true }], // Ensure keys in lists
				"react/no-children-prop": "error", // Use JSX children syntax
				"react/void-dom-elements-no-children": "error", // No children on void elements
				"react/jsx-no-duplicate-props": "error", // Prevent duplicate props
				"react/jsx-no-undef": "error", // Prevent undefined components
				"react/no-danger-with-children": "error", // Prevent dangerouslySetInnerHTML with children
				"react/no-deprecated": "warn", // Warn about deprecated React APIs
				"react/no-direct-mutation-state": "error", // Never mutate state directly
				"react/no-find-dom-node": "error", // findDOMNode is deprecated
				"react/no-is-mounted": "error", // isMounted is anti-pattern
				"react/no-string-refs": "error", // String refs are legacy
				"react/no-render-return-value": "error", // Don't use return value of ReactDOM.render
				"react/require-render-return": "error", // Enforce return in render
			},
	},
]

// Minimal ESLint config - only for what Biome can't handle

import tanstackQuery from "@tanstack/eslint-plugin-query"
import betterTailwindcss from "eslint-plugin-better-tailwindcss"
import boundaries from "eslint-plugin-boundaries"
import importPlugin from "eslint-plugin-import"
import promisePlugin from "eslint-plugin-promise"
import react from "eslint-plugin-react"
import reactCompiler from "eslint-plugin-react-compiler"
import reactRefresh from "eslint-plugin-react-refresh"
import sonarjs from "eslint-plugin-sonarjs"
import unicorn from "eslint-plugin-unicorn"

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

	// TanStack Query linting
	...tanstackQuery.configs["flat/recommended"],

	// React Router: no project-specific ESLint plugin currently configured

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
				alias: {
					map: [["@", "./src"]],
					extensions: [".js", ".jsx"],
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
					ignore: ["^aui-.*", "^epub-container$"],
				},
			],
		},
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
			sonarjs: sonarjs,
			unicorn: unicorn,
		},
		rules: {
			...unicorn.configs["flat/recommended"].rules,
			...sonarjs.configs.recommended.rules,
			"sonarjs/no-nested-conditional": "off",
			"sonarjs/cognitive-complexity": "off",
			"unicorn/catch-error-name": "off",
			"unicorn/expiring-todo-comments": "off",
			"unicorn/consistent-function-scoping": "off",
			"unicorn/empty-brace-spaces": "off",
			"unicorn/no-lonely-if": "off",
			"unicorn/no-array-for-each": "off",
			"unicorn/no-array-reduce": "off",
			"unicorn/no-for-loop": "off",
			"unicorn/no-null": "off",
			"unicorn/number-literal-case": "off",
			"unicorn/prefer-default-parameters": "off",
			"unicorn/prefer-global-this": "off",
			"unicorn/prefer-optional-catch-binding": "off",
			"unicorn/prefer-query-selector": "off",
			"unicorn/prefer-string-replace-all": "off",
			"unicorn/prefer-ternary": "off",
			"unicorn/prevent-abbreviations": "off",
			"unicorn/prefer-logical-operator-over-ternary": "off",
			"unicorn/no-nested-ternary": "off",
			"unicorn/filename-case": [
				"error",
				{
					cases: {
						camelCase: true,
						kebabCase: true,
						pascalCase: true,
					},
					ignore: ["^JXGBoard\\.jsx$", "^JXGBoardPractice\\.jsx$"],
				},
			],
			"no-nested-ternary": "off",
			"import/no-cycle": ["warn", { maxDepth: 1 }],
			"import/no-duplicates": "error",
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
							target: ["./src/components", "./src/hooks", "./src/lib", "./src/types", "./src/utils"],
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
			"react-refresh": reactRefresh,
			"react-compiler": reactCompiler,
			sonarjs: sonarjs,
			unicorn: unicorn,
		},
		settings: {
			react: {
				version: "19.1.1", // Specify React 19
			},
		},
		rules: {
			...unicorn.configs["flat/recommended"].rules,
			...sonarjs.configs.recommended.rules,
			"sonarjs/no-nested-conditional": "off",
			"sonarjs/cognitive-complexity": "off",
			"unicorn/catch-error-name": "off",
			"unicorn/expiring-todo-comments": "off",
			"unicorn/consistent-function-scoping": "off",
			"unicorn/empty-brace-spaces": "off",
			"unicorn/no-lonely-if": "off",
			"unicorn/no-array-for-each": "off",
			"unicorn/no-array-reduce": "off",
			"unicorn/no-for-loop": "off",
			"unicorn/no-null": "off",
			"unicorn/no-nested-ternary": "off",
			"unicorn/number-literal-case": "off",
			"unicorn/prefer-default-parameters": "off",
			"unicorn/prefer-global-this": "off",
			"unicorn/prefer-optional-catch-binding": "off",
			"unicorn/prefer-query-selector": "off",
			"unicorn/prefer-string-replace-all": "off",
			"unicorn/prefer-ternary": "off",
			"unicorn/prevent-abbreviations": "off",
			"unicorn/prefer-logical-operator-over-ternary": "off",
			"unicorn/filename-case": [
				"error",
				{
					cases: {
						camelCase: true,
						kebabCase: true,
						pascalCase: true,
					},
					ignore: ["^JXGBoard\\.jsx$", "^JXGBoardPractice\\.jsx$"],
				},
			],
			"no-nested-ternary": "off",

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

			// React Compiler - preparing for migration
			"react-compiler/react-compiler": "error",

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

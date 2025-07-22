/** @type {import("@biomejs/biome").Config} */
module.exports = {
	formatter: {
		lineWidth: 120,
		quoteStyle: "double",
		trailingComma: "all",
		semi: true,
		singleAttributePerLine: false,
		indentStyle: "space",
		indentWidth: 4,
	},
	lint: {
		enabled: true,
		rules: {
			recommended: true,
			suspicious: {
				noArrayIndexKey: "error",
				noConsoleLog: "warn",
				noEmptyBlockStatements: "error",
				noExplicitAny: "warn",
			},
			style: {
				noVar: "error",
				useConst: "error",
				useTemplate: "error",
				useShorthandFunctionType: "error",
				noNonNullAssertion: "warn",
				useNamingConvention: {
					level: "error",
					options: {
						conventions: [
							{
								selector: {
									kind: "function",
								},
								formats: ["camelCase", "PascalCase"],
							},
							{
								selector: {
									kind: "variable",
								},
								formats: ["camelCase", "CONSTANT_CASE"],
							},
							{
								selector: {
									kind: "typeLike",
								},
								formats: ["PascalCase"],
							},
						],
					},
				},
			},
			correctness: {
				noUnusedVariables: "error",
				noUnusedImports: "error",
				useJsxKeyInIterable: "error",
			},
			complexity: {
				noExcessiveCognitiveComplexity: "warn",
				noForEach: "off",
			},
			nursery: {
				useSortedClasses: "off",
			},
		},
		exclude: [
			"**/migrations/**",
			"**/*.spec.ts",
			"**/*.test.js",
			"**/*.test.jsx",
			"node_modules",
		],
	},
	organizeImports: {
		enabled: true,
	},
	javascript: {
		formatter: {
			quoteStyle: "double",
			semicolons: "always",
			trailingCommas: "all",
		},
	},
	typescript: {
		enabled: true,
	},
	json: {
		formatter: {
			enabled: true,
		},
	},
	exclude: ["dist", "coverage", "node_modules", "build"],
};

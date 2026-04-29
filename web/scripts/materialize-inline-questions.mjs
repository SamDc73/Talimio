import process from "node:process"
import remarkMdx from "remark-mdx"
import remarkParse from "remark-parse"
import remarkStringify from "remark-stringify"
import { unified } from "unified"

const SUPPORTED_COMPONENTS = new Set(["LatexExpression", "FreeForm", "JXGBoard", "MultipleChoice", "FillInTheBlank"])

const SERVER_PROPS = new Set([
	"answer",
	"answerKind",
	"correctAnswer",
	"criteria",
	"expectedAnswer",
	"expectedLatex",
	"expectedState",
	"hints",
	"options",
	"perCheckTolerance",
	"practiceContext",
	"question",
	"sampleAnswer",
	"sentence",
	"solutionLatex",
	"tolerance",
])

const HIDDEN_PROPS = new Set([
	"expectedLatex",
	"expectedAnswer",
	"sampleAnswer",
	"solutionLatex",
	"expectedState",
	"correctAnswer",
	"answer",
	"explanation",
	"tolerance",
	"perCheckTolerance",
])

const processor = unified().use(remarkParse).use(remarkMdx).use(remarkStringify, {
	bullet: "-",
	fences: true,
	listItemIndent: "one",
})

function readStdin() {
	return new Promise((resolve, reject) => {
		let data = ""
		process.stdin.setEncoding("utf8")
		process.stdin.on("data", (chunk) => {
			data += chunk
		})
		process.stdin.on("end", () => resolve(data))
		process.stdin.on("error", reject)
	})
}

function walk(node, visitor) {
	if (!node || typeof node !== "object") return
	visitor(node)
	for (const value of Object.values(node)) {
		if (Array.isArray(value)) {
			for (const child of value) walk(child, visitor)
		}
	}
}

function attributeValue(attribute) {
	if (typeof attribute.value === "string") return attribute.value
	if (attribute.value === null || attribute.value === undefined) return true
	const expression = expressionFromProgram(attribute.value.data?.estree)
	return expressionToValue(expression)
}

function expressionFromProgram(program) {
	const statement = program?.body?.[0]
	return statement?.type === "ExpressionStatement" ? statement.expression : undefined
}

function expressionToValue(node) {
	if (!node) return undefined
	if (node.type === "Literal") return node.value
	if (node.type === "ArrayExpression") return node.elements.map(expressionToValue)
	if (node.type === "ObjectExpression") return objectExpressionToValue(node)
	if (node.type === "UnaryExpression" && node.operator === "-") {
		const value = expressionToValue(node.argument)
		return typeof value === "number" ? -value : undefined
	}
	return undefined
}

function objectExpressionToValue(node) {
	const value = {}
	for (const property of node.properties) {
		if (property.type !== "Property") continue
		const key = propertyKey(property.key)
		if (!key) continue
		value[key] = expressionToValue(property.value)
	}
	return value
}

function propertyKey(node) {
	if (node.type === "Identifier") return node.name
	if (node.type === "Literal") return String(node.value)
	return undefined
}

function collectAttributes(node) {
	const attrs = {}
	for (const attribute of node.attributes || []) {
		if (attribute.type !== "mdxJsxAttribute") continue
		if (!SERVER_PROPS.has(attribute.name)) continue
		const value = attributeValue(attribute)
		if (value !== undefined) attrs[attribute.name] = value
	}
	return attrs
}

function rewriteAttributes(node, placeholder) {
	node.attributes = (node.attributes || []).filter((attribute) => {
		return (
			attribute.type !== "mdxJsxAttribute" || (!HIDDEN_PROPS.has(attribute.name) && attribute.name !== "questionId")
		)
	})
	node.attributes.push({ type: "mdxJsxAttribute", name: "questionId", value: placeholder })
}

function materializeDocument(document) {
	const tree = processor.parse(document.content)
	const components = []
	walk(tree, (node) => {
		if (!["mdxJsxFlowElement", "mdxJsxTextElement"].includes(node.type)) return
		if (!SUPPORTED_COMPONENTS.has(node.name)) return
		const placeholder = `__INLINE_QUESTION_${components.length}__`
		components.push({
			component: node.name,
			index: components.length,
			placeholder,
			attrs: collectAttributes(node),
		})
		rewriteAttributes(node, placeholder)
	})
	return {
		key: document.key,
		content: processor.stringify(tree),
		components,
	}
}

async function main() {
	const input = JSON.parse(await readStdin())
	const documents = input.documents.map(materializeDocument)
	process.stdout.write(JSON.stringify({ documents }))
}

main().catch((error) => {
	process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`)
	process.exit(1)
})

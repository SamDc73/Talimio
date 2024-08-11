export const serializeGraphState = (nodes, edges) => ({
	nodes: nodes.map((node) => ({
		id: node.id,
		type: node.type,
		position: { ...node.position },
		data: { ...node.data },
	})),
	edges: edges.map((edge) => ({
		id: edge.id,
		source: edge.source,
		target: edge.target,
		type: edge.type,
	})),
})

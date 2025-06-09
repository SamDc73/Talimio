import { ROADMAP_DEFAULTS } from "@/lib/constants";

export const calculateNodePosition = (sourceNode, index) => {
	if (!sourceNode || !sourceNode.position) {
		console.error("Invalid source node:", sourceNode);
		return { x: 0, y: 0 };
	}

	const randomOffset = {
		x: (Math.random() - 0.5) * (ROADMAP_DEFAULTS.NODE_SPACING.HORIZONTAL * 0.5),
		y: (Math.random() - 0.5) * (ROADMAP_DEFAULTS.NODE_SPACING.VERTICAL * 0.5),
	};

	const position = {
		x:
			sourceNode.position.x +
			ROADMAP_DEFAULTS.NODE_SPACING.HORIZONTAL +
			randomOffset.x,
		y:
			sourceNode.position.y +
			index * ROADMAP_DEFAULTS.NODE_SPACING.VERTICAL +
			randomOffset.y,
	};

	console.log("Calculated position:", position);
	return position;
};

export const createEdge = (sourceId, targetId) => {
	if (!sourceId || !targetId) {
		console.error("Invalid edge params:", { sourceId, targetId });
		throw new Error("Invalid edge parameters");
	}

	const edge = {
		id: `e${sourceId}-${targetId}`,
		source: sourceId,
		target: targetId,
		type: "default",
	};

	console.log("Created edge:", edge);
	return edge;
};

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
});

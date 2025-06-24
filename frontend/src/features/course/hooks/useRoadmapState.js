import { addEdge, useEdgesState, useNodesState } from "@xyflow/react";
import { useCallback, useEffect, useRef, useState } from "react";

const NODE_HEIGHT = 80;
const VERTICAL_SPACING = 180;
const HORIZONTAL_INDENTATION = 70;
const HORIZONTAL_SIBLING_SPACING = 250;

const shouldUseHorizontalLayout = (node, childIds, allNodes) => {
	if (!node || !childIds || childIds.length < 2) {
		return false;
	}

	if (node.parentId === null) {
		return false;
	}

	const children = childIds.map((id) => allNodes.get(id)).filter(Boolean);
	return children.length >= 2;
};

const processNode = (node, parentId, uniqueApiNodes, nodeRelationships) => {
	if (!uniqueApiNodes.has(node.id)) {
		uniqueApiNodes.set(node.id, { ...node, parentId: parentId });
	} else {
		const existingNode = uniqueApiNodes.get(node.id);
		if (!existingNode.parentId && parentId) {
			existingNode.parentId = parentId;
		}
	}

	if (parentId) {
		if (!nodeRelationships.has(parentId)) {
			nodeRelationships.set(parentId, []);
		}
		if (!nodeRelationships.get(parentId).includes(node.id)) {
			nodeRelationships.get(parentId).push(node.id);
		}
	}
};

const createReactFlowNode = (apiNode, nodePositions, nodeRelationships) => {
	const position = nodePositions.get(apiNode.id);
	if (!position) {
		console.warn(`Position missing for node ID: ${apiNode.id}`);
		return null;
	}

	return {
		id: apiNode.id,
		type:
			nodeRelationships.has(apiNode.id) &&
				nodeRelationships.get(apiNode.id).length > 0
				? "decision"
				: "task",
		position,
		data: {
			label: apiNode.title,
			description: apiNode.description,
			...apiNode,
		},
	};
};

const calculateNodePosition = (
	nodeId,
	nodePositions,
	uniqueApiNodes,
	nodeRelationships,
	processedNodeIds,
	level = 0,
	parentX = 0,
	forcedY = null,
) => {
	if (processedNodeIds.has(nodeId)) return { height: 0 };

	processedNodeIds.add(nodeId);
	const node = uniqueApiNodes.get(nodeId);
	if (!node) return { height: 0 };

	const x = parentX + level * HORIZONTAL_INDENTATION;
	const baseY = 50;
	const y = forcedY ?? baseY + processedNodeIds.size * VERTICAL_SPACING;

	nodePositions.set(nodeId, { x, y });

	let childIds = nodeRelationships.get(nodeId) || [];
	if (childIds.length === 0) {
		return { height: NODE_HEIGHT + VERTICAL_SPACING };
	}

	// Sort child IDs by their order property in the original nodes
	childIds = childIds.slice().sort((a, b) => {
		const nodeA = uniqueApiNodes.get(a);
		const nodeB = uniqueApiNodes.get(b);
		return (nodeA?.order ?? 0) - (nodeB?.order ?? 0);
	});

	const useHorizontalLayout = shouldUseHorizontalLayout(
		node,
		childIds,
		uniqueApiNodes,
	);

	if (useHorizontalLayout) {
		const totalWidth = (childIds.length - 1) * HORIZONTAL_SIBLING_SPACING;
		const startX = x - totalWidth / 2;
		const horizontalRowY = y + NODE_HEIGHT + VERTICAL_SPACING;

		let maxHeight = 0;
		for (const [index, childId] of childIds.entries()) {
			const childX = startX + index * HORIZONTAL_SIBLING_SPACING;
			const { height } = calculateNodePosition(
				childId,
				nodePositions,
				uniqueApiNodes,
				nodeRelationships,
				processedNodeIds,
				level + 1,
				childX,
				horizontalRowY,
			);
			maxHeight = Math.max(maxHeight, height);
		}
		return { height: maxHeight + NODE_HEIGHT + VERTICAL_SPACING };
	}

	let totalHeight = NODE_HEIGHT + VERTICAL_SPACING;
	for (const childId of childIds) {
		const { height } = calculateNodePosition(
			childId,
			nodePositions,
			uniqueApiNodes,
			nodeRelationships,
			processedNodeIds,
			level + 1,
			x,
		);
		totalHeight += height;
	}
	return { height: totalHeight };
};

const layoutNodes = (
	rootNodes,
	nodePositions,
	uniqueApiNodes,
	nodeRelationships,
) => {
	const processedNodeIds = new Set();
	for (const rootId of rootNodes) {
		calculateNodePosition(
			rootId,
			nodePositions,
			uniqueApiNodes,
			nodeRelationships,
			processedNodeIds,
		);
	}
};

// Helper functions for node processing
const processNodeStack = (apiNodes) => {
	const uniqueApiNodes = new Map();
	const nodeRelationships = new Map();
	const stack = apiNodes.map((node) => ({
		node,
		parentId: node.parentId || null,
	}));

	while (stack.length > 0) {
		const { node, parentId } = stack.pop();
		processNode(node, parentId, uniqueApiNodes, nodeRelationships);

		if (Array.isArray(node.children) && node.children.length > 0) {
			const sortedChildren = [...node.children]
				.sort((a, b) => a.order - b.order)
				.reverse();
			for (const child of sortedChildren) {
				stack.push({ node: child, parentId: node.id });
			}
		}
	}

	return { uniqueApiNodes, nodeRelationships };
};

const findRootNodes = (uniqueApiNodes) => {
	const allNodeIds = new Set(uniqueApiNodes.keys());
	return Array.from(uniqueApiNodes.values())
		.filter((node) => !node.parentId || !allNodeIds.has(node.parentId))
		.sort((a, b) => a.order - b.order)
		.map((node) => node.id);
};

const sortNodesByHierarchy = (nodes) => {
	return nodes.sort((a, b) => {
		if (a.parentId !== b.parentId) {
			if (!a.parentId) return -1;
			if (!b.parentId) return 1;
			return a.parentId.localeCompare(b.parentId);
		}
		return a.order - b.order;
	});
};

const createEdges = (nodeRelationships, uniqueApiNodes) => {
	const edges = [];
	for (const [parentId, children] of nodeRelationships) {
		if (uniqueApiNodes.has(parentId)) {
			const sortedChildren = [...children].sort((a, b) => {
				const nodeA = uniqueApiNodes.get(a);
				const nodeB = uniqueApiNodes.get(b);
				return (nodeA?.order ?? 0) - (nodeB?.order ?? 0);
			});

			for (const childId of sortedChildren) {
				if (uniqueApiNodes.has(childId)) {
					edges.push({
						id: `e${parentId}-${childId}`,
						source: parentId,
						target: childId,
						type: "smoothstep",
					});
				}
			}
		}
	}
	return edges;
};

// Vertical layout with intuitive parent-child relationships
const getVerticalTreeLayout = (apiNodes) => {
	// Process nodes and build relationships
	const { uniqueApiNodes, nodeRelationships } = processNodeStack(apiNodes);

	// Find and sort root nodes
	const rootNodes = findRootNodes(uniqueApiNodes);

	// Calculate node positions
	const nodePositions = new Map();
	layoutNodes(rootNodes, nodePositions, uniqueApiNodes, nodeRelationships);

	// Create and sort React Flow nodes
	const reactFlowNodes = sortNodesByHierarchy(
		Array.from(uniqueApiNodes.values()),
	)
		.map((apiNode) =>
			createReactFlowNode(apiNode, nodePositions, nodeRelationships),
		)
		.filter(Boolean);

	// Create edges
	const reactFlowEdges = createEdges(nodeRelationships, uniqueApiNodes);

	return { nodes: reactFlowNodes, edges: reactFlowEdges };
};

const getLayoutedElements = (apiNodes) => {
	const sortedApiNodes = [...apiNodes].sort((a, b) => a.order - b.order);
	return getVerticalTreeLayout(sortedApiNodes);
};

export const useRoadmapState = (roadmapId, onError) => {
	const [nodes, setNodes, onNodesChange] = useNodesState([]);
	const [edges, setEdges, onEdgesChange] = useEdgesState([]);
	const [isLoading, setIsLoading] = useState(false);
	const [hasInitialized, setHasInitialized] = useState(false);
	const [roadmap, setRoadmap] = useState(null);
	const initializedRef = useRef(false);

	const handleConnect = useCallback(
		(params) => setEdges((eds) => addEdge(params, eds)),
		[setEdges],
	);

	const updateRoadmapState = useCallback(
		(roadmap) => {
			setRoadmap(roadmap);
			if (roadmap?.nodes?.length > 0) {
				const { nodes: layoutedNodes, edges: layoutedEdges } =
					getLayoutedElements(roadmap.nodes);
				setNodes(layoutedNodes);
				setEdges(layoutedEdges);
			} else {
				setNodes([]);
				setEdges([]);
			}
			setHasInitialized(true);
		},
		[setNodes, setEdges],
	);

	const initializeRoadmap = useCallback(
		async (roadmapId) => {
			if (!roadmapId || hasInitialized || isLoading) {
				return;
			}

			setIsLoading(true);
			try {
				const response = await fetch(
					`${import.meta.env.VITE_API_BASE || "/api/v1"}/courses/${roadmapId}?generate=true`,
				);
				if (!response.ok) {
					throw new Error(`HTTP error! status: ${response.status}`);
				}

				const roadmap = await response.json();
				updateRoadmapState(roadmap);
			} catch (error) {
				if (error.name !== "AbortError") {
					console.error("Failed to initialize roadmap:", error);
				}
			} finally {
				setIsLoading(false);
			}
		},
		[hasInitialized, isLoading, updateRoadmapState],
	);

	useEffect(() => {
		if (!roadmapId || initializedRef.current) return;

		initializedRef.current = true;
		initializeRoadmap(roadmapId).catch((error) => {
			console.error("Error loading roadmap:", error);
			onError?.();
		});
	}, [roadmapId, initializeRoadmap, onError]);

	useEffect(() => {
		const controller = new AbortController();
		return () => controller.abort();
	}, []);

	return {
		nodes,
		edges,
		isLoading,
		onNodesChange,
		onEdgesChange,
		handleConnect,
		initializeRoadmap,
		roadmap,
	};
};

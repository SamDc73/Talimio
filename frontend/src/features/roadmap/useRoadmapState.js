import { addEdge, useEdgesState, useNodesState } from "@xyflow/react";
import { useCallback, useEffect, useRef, useState } from "react";
// import dagre from "@dagrejs/dagre";

// --- Layout Helpers ---
const NODE_WIDTH = 220; // Width matching our CSS width in node components
const NODE_HEIGHT = 80; // Height matching our CSS height in node components
const VERTICAL_SPACING = 180; // Increased vertical space between nodes for better separation
const HORIZONTAL_INDENTATION = 70; // Slightly reduced for denser child grouping
const SIBLING_SPACING = 36; // Reduced spacing for denser sibling layout
const HORIZONTAL_SIBLING_SPACING = 250; // Spacing for horizontally arranged siblings

// Helper function to determine if a node's children should be arranged horizontally
// This makes the decision dynamic based on node type and relationship
const shouldUseHorizontalLayout = (node, childIds, allNodes) => {
  if (!node || !childIds || childIds.length < 2) {
    return false;
  }

  // Top-level parent nodes (those without parent_id) should always flow vertically
  if (node.parent_id === null) {
    return false;
  }

  // For siblings that represent parallel concepts rather than sequential steps,
  // arrange them horizontally to better visualize their relationship
  const children = childIds.map((id) => allNodes.get(id)).filter(Boolean);

  // If node has multiple children that don't depend on each other,
  // display them horizontally
  return children.length >= 2;
};

// Helper functions to break down complexity
const processNode = (node, parentId, uniqueApiNodes, nodeRelationships) => {
  if (!uniqueApiNodes.has(node.id)) {
    uniqueApiNodes.set(node.id, { ...node, parent_id: parentId });
  } else {
    const existingNode = uniqueApiNodes.get(node.id);
    if (!existingNode.parent_id && parentId) {
      existingNode.parent_id = parentId;
    }
  }

  if (parentId) {
    if (!nodeRelationships.has(parentId)) {
      nodeRelationships.set(parentId, []);
    }
    if (!nodeRelationships.get(parentId).includes(node.id)) {
      // Add the node to the parent's children array
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
    type: nodeRelationships.has(apiNode.id) && nodeRelationships.get(apiNode.id).length > 0 ? "decision" : "task",
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

  const useHorizontalLayout = shouldUseHorizontalLayout(node, childIds, uniqueApiNodes);

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

const layoutNodes = (rootNodes, nodePositions, uniqueApiNodes, nodeRelationships) => {
  const processedNodeIds = new Set();
  for (const rootId of rootNodes) {
    calculateNodePosition(rootId, nodePositions, uniqueApiNodes, nodeRelationships, processedNodeIds);
  }
};

// Helper functions for node processing
const processNodeStack = (apiNodes) => {
  const uniqueApiNodes = new Map();
  const nodeRelationships = new Map();
  const stack = apiNodes.map((node) => ({ node, parentId: node.parent_id || null }));

  while (stack.length > 0) {
    const { node, parentId } = stack.pop();
    processNode(node, parentId, uniqueApiNodes, nodeRelationships);

    if (Array.isArray(node.children) && node.children.length > 0) {
      const sortedChildren = [...node.children].sort((a, b) => a.order - b.order).reverse();
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
    .filter((node) => !node.parent_id || !allNodeIds.has(node.parent_id))
    .sort((a, b) => a.order - b.order)
    .map((node) => node.id);
};

const sortNodesByHierarchy = (nodes) => {
  return nodes.sort((a, b) => {
    if (a.parent_id !== b.parent_id) {
      if (!a.parent_id) return -1;
      if (!b.parent_id) return 1;
      return a.parent_id.localeCompare(b.parent_id);
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

// Duolingo-style vertical layout with intuitive parent-child relationships
const getVerticalTreeLayout = (apiNodes) => {
  // Process nodes and build relationships
  const { uniqueApiNodes, nodeRelationships } = processNodeStack(apiNodes);

  // Find and sort root nodes
  const rootNodes = findRootNodes(uniqueApiNodes);

  // Calculate node positions
  const nodePositions = new Map();
  layoutNodes(rootNodes, nodePositions, uniqueApiNodes, nodeRelationships);

  // Create and sort React Flow nodes
  const reactFlowNodes = sortNodesByHierarchy(Array.from(uniqueApiNodes.values()))
    .map((apiNode) => createReactFlowNode(apiNode, nodePositions, nodeRelationships))
    .filter(Boolean);

  // Create edges
  const reactFlowEdges = createEdges(nodeRelationships, uniqueApiNodes);

  return { nodes: reactFlowNodes, edges: reactFlowEdges };
};

// Helper functions for Dagre layout processing
const initializeDagreGraph = (direction = "TB") => {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: direction, nodesep: 70, ranksep: 100 });
  return graph;
};

const setupDagreNode = (node, dagreGraph) => {
  dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  return node;
};

const createEdge = (parentId, nodeId) => ({
  id: `e${parentId}-${nodeId}`,
  source: parentId,
  target: nodeId,
  type: "smoothstep",
});

const determineNodeType = (node) =>
  node.type || (Array.isArray(node.children) && node.children.length > 0 ? "decision" : "task");

const createFlowNode = (apiNode, nodeWithPosition) => ({
  id: apiNode.id,
  type: determineNodeType(apiNode),
  position: {
    x: nodeWithPosition.x - NODE_WIDTH / 2,
    y: nodeWithPosition.y - NODE_HEIGHT / 2,
  },
  data: {
    label: apiNode.title,
    description: apiNode.description,
    ...apiNode,
  },
});

// Keep the original Dagre layout as a fallback
const getDagreLayout = (apiNodes, direction = "TB") => {
  const dagreGraph = initializeDagreGraph(direction);
  const uniqueApiNodes = new Map();
  const processedNodeIds = new Set();
  const edges = new Set();

  const addNodeAndEdges = (node, parentId = null) => {
    if (!processedNodeIds.has(node.id)) {
      processedNodeIds.add(node.id);
      uniqueApiNodes.set(node.id, node);
      setupDagreNode(node, dagreGraph);
    }

    if (parentId) {
      const edgeId = `e${parentId}-${node.id}`;
      if (!edges.has(edgeId)) {
        dagreGraph.setEdge(parentId, node.id);
        edges.add(edgeId);
      }
    }

    if (Array.isArray(node.children)) {
      for (const child of node.children) {
        addNodeAndEdges(child, node.id);
      }
    }
  };

  const rootNodes = apiNodes.filter((node) => !node.parent_id);
  for (const node of rootNodes) {
    addNodeAndEdges(node);
  }

  dagre.layout(dagreGraph);

  const reactFlowNodes = Array.from(uniqueApiNodes.values())
    .map((apiNode) => {
      const nodeWithPosition = dagreGraph.node(apiNode.id);
      if (!nodeWithPosition) {
        console.warn(`Dagre layout information missing for node ID: ${apiNode.id}`);
        return null;
      }
      return createFlowNode(apiNode, nodeWithPosition);
    })
    .filter(Boolean);

  const finalNodeIds = new Set(reactFlowNodes.map((n) => n.id));
  const reactFlowEdges = Array.from(edges)
    .map((edgeId) => {
      const [, parentId, nodeId] = edgeId.match(/^e(.*)-(.*)$/);
      return createEdge(parentId, nodeId);
    })
    .filter((edge) => finalNodeIds.has(edge.source) && finalNodeIds.has(edge.target));

  return { nodes: reactFlowNodes, edges: reactFlowEdges };
};

// Main layout function that uses the vertical tree layout
const getLayoutedElements = (apiNodes) => {
  // Sort the top-level nodes by their order property before processing
  const sortedApiNodes = [...apiNodes].sort((a, b) => a.order - b.order);
  return getVerticalTreeLayout(sortedApiNodes);
};

export const useRoadmapState = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [roadmap, setRoadmap] = useState(null);
  const requestRef = useRef(null);

  const handleConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  const updateRoadmapState = useCallback(
    (roadmap) => {
      setRoadmap(roadmap);
      if (roadmap?.nodes?.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(roadmap.nodes);
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
        const response = await fetch(`http://localhost:8080/api/v1/roadmaps/${roadmapId}`);
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

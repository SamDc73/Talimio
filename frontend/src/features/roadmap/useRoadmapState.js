import { useNodesState, useEdgesState, addEdge } from '@xyflow/react'; // Added addEdge import
import { useCallback, useState, useRef, useEffect } from 'react';  // Added useRef import
import dagre from '@dagrejs/dagre';

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
  const children = childIds.map(id => allNodes.get(id)).filter(Boolean);

  // If node has multiple children that don't depend on each other,
  // display them horizontally
  return children.length >= 2;
};

// Duolingo-style vertical layout with intuitive parent-child relationships
const getVerticalTreeLayout = (apiNodes) => {
  const uniqueApiNodes = new Map(); // Store unique nodes by ID
  const nodeRelationships = new Map(); // Maps node IDs to arrays of child IDs
  const processedNodeIds = new Set(); // Track IDs we've seen (used in positioning)
  // Edges will be created later based on nodeRelationships

  // --- MODIFICATION START: Use iterative traversal for nested nodes ---
  const stack = [...apiNodes.map(node => ({ node, parentId: node.parent_id || null }))];

  while (stack.length > 0) {
    const { node, parentId } = stack.pop();

    // Add node if not already processed/added
    if (!uniqueApiNodes.has(node.id)) {
      // Ensure parent_id from the stack context is stored, preferring it over node.parent_id
      // as the stack provides the correct hierarchical parent during traversal.
      uniqueApiNodes.set(node.id, { ...node, parent_id: parentId });
    } else {
      // If node exists (e.g., was a root node initially), update its parent_id if found via traversal
      const existingNode = uniqueApiNodes.get(node.id);
      if (!existingNode.parent_id && parentId) {
        existingNode.parent_id = parentId;
      }
    }

    // Establish parent-child relationship using the parentId from the stack context
    if (parentId) {
      if (!nodeRelationships.has(parentId)) {
        nodeRelationships.set(parentId, []);
      }
      // Avoid adding duplicate children relationships
      if (!nodeRelationships.get(parentId).includes(node.id)) {
        nodeRelationships.get(parentId).push(node.id);
      }
    }

    // Add children from the JSON structure to the stack for processing
    if (Array.isArray(node.children) && node.children.length > 0) {
      // Add children in reverse order to maintain original order when popped
      for (let i = node.children.length - 1; i >= 0; i--) {
        const child = node.children[i];
        // Pass the current node's id as the parentId for the child
        stack.push({ node: child, parentId: node.id });
      }
    }
  }
  // --- MODIFICATION END ---


  // Find root nodes (nodes without a parent_id or whose parent_id is not in our fully populated node list)
  const allNodeIds = new Set(uniqueApiNodes.keys()); // Use keys from the map after full traversal
  const rootNodes = Array.from(uniqueApiNodes.values())
    .filter(node => !node.parent_id || !allNodeIds.has(node.parent_id))
    .map(node => node.id);

  // Position tracking
  let currentY = 50; // Starting Y position
  const nodePositions = new Map(); // Maps node IDs to {x, y} positions

  // Recursive function to position a node and all its children
  const positionNodeAndChildren = (nodeId, level = 0, parentX = 0) => {
    if (processedNodeIds.has(nodeId)) return 0; // Skip if already processed

    processedNodeIds.add(nodeId);
    const node = uniqueApiNodes.get(nodeId);
    if (!node) return 0; // Should not happen, but safety check

    // Calculate X position
    const x = parentX + (level * HORIZONTAL_INDENTATION);
    const y = currentY;
    nodePositions.set(nodeId, { x, y });

    // Increment Y position for the next node at this level or the start of the next branch
    currentY += NODE_HEIGHT + VERTICAL_SPACING;

    const childIds = nodeRelationships.get(nodeId) || [];
    const useHorizontalLayout = shouldUseHorizontalLayout(node, childIds, uniqueApiNodes);

    let startX = x; // Default start X for children (vertical layout)
    if (useHorizontalLayout && childIds.length > 0) {
      // Calculate starting X for horizontal layout
      const totalWidth = (childIds.length - 1) * HORIZONTAL_SIBLING_SPACING;
      startX = x - (totalWidth / 2);
    }

    const horizontalRowY = currentY; // Save Y for horizontal layout row

    let maxChildBranchHeight = 0; // Track height of the tallest child branch

    childIds.forEach((childId, index) => {
      // For horizontal layout, position children side-by-side
      if (useHorizontalLayout) {
        currentY = horizontalRowY; // Reset Y for each sibling in the row
        const childX = startX + (index * HORIZONTAL_SIBLING_SPACING);
        const childBranchHeight = positionNodeAndChildren(childId, level + 1, childX);
        maxChildBranchHeight = Math.max(maxChildBranchHeight, childBranchHeight);
      } else {
        // For vertical layout, position children below, indented
        const childBranchHeight = positionNodeAndChildren(childId, level + 1, x);
        maxChildBranchHeight = Math.max(maxChildBranchHeight, childBranchHeight);
        // currentY is already incremented by the recursive call
      }
    });

    // Adjust currentY after processing all children of this node
    if (useHorizontalLayout && childIds.length > 0) {
       // After a horizontal row, move Y down by the height of the tallest branch processed in that row
       currentY = horizontalRowY + maxChildBranchHeight;
    } else if (childIds.length === 0) {
       // If it's a leaf node, the height is just its own height + spacing
       return NODE_HEIGHT + VERTICAL_SPACING;
    }
    // If vertical layout, currentY is already correctly positioned by the last child's branch

    // Return the total height used by this node and its descendants branch
    return 0; // Simplified return
  };


  // Position all root nodes and their descendants
  rootNodes.forEach(rootId => {
    positionNodeAndChildren(rootId);
  });

  // Create the React Flow nodes with their calculated positions
  const reactFlowNodes = Array.from(uniqueApiNodes.values()).map(apiNode => {
    const position = nodePositions.get(apiNode.id);

    if (!position) {
      console.warn(`Position missing for node ID: ${apiNode.id}. Node might be disconnected or data inconsistent.`);
      return null; // Skip nodes that couldn't be positioned
    }

    return {
      id: apiNode.id,
      // Determine type based on whether it has children in the relationship map
      type: nodeRelationships.has(apiNode.id) && nodeRelationships.get(apiNode.id).length > 0 ? 'decision' : 'task',
      position,
      data: {
        label: apiNode.title,
        description: apiNode.description,
        ...apiNode
      },
    };
  }).filter(Boolean); // Filter out any null nodes


  // --- ADJUST EDGE CREATION: Create edges based on the final nodeRelationships map ---
  const reactFlowEdges = [];
  nodeRelationships.forEach((children, parentId) => {
    if (uniqueApiNodes.has(parentId)) {
      children.forEach(childId => {
        if (uniqueApiNodes.has(childId)) {
           reactFlowEdges.push({
              id: `e${parentId}-${childId}`,
              source: parentId,
              target: childId,
              type: 'smoothstep',
           });
        }
      });
    }
  });
  // --- END ADJUST EDGE CREATION ---

  return { nodes: reactFlowNodes, edges: reactFlowEdges };
};

// Keep the original Dagre layout as a fallback
const getDagreLayout = (apiNodes, direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 70, ranksep: 100 });

  const uniqueApiNodes = new Map(); // Store unique nodes by ID
  const processedNodeIds = new Set(); // Track IDs added to dagre
  const reactFlowEdges = []; // Edges for React Flow

  const processApiNodes = (nodes, parentId = null) => {
    nodes.forEach((node) => {
      if (!processedNodeIds.has(node.id)) {
        processedNodeIds.add(node.id);
        uniqueApiNodes.set(node.id, node);
        dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
      }

      if (parentId) {
        const edgeId = `e${parentId}-${node.id}`;
        if (!reactFlowEdges.some(e => e.id === edgeId)) {
          dagreGraph.setEdge(parentId, node.id);
          reactFlowEdges.push({
            id: edgeId,
            source: parentId,
            target: node.id,
            type: 'smoothstep',
          });
        }
      }

      if (Array.isArray(node.children) && node.children.length > 0) {
        processApiNodes(node.children, node.id);
      }
    });
  };

  const allNodeIds = new Set(apiNodes.map(n => n.id));
  const rootNodes = apiNodes.filter(node => !node.parent_id || !allNodeIds.has(node.parent_id));

  processApiNodes(rootNodes);

  dagre.layout(dagreGraph);

  const reactFlowNodes = Array.from(uniqueApiNodes.values()).map((apiNode) => {
    const nodeWithPosition = dagreGraph.node(apiNode.id);
    if (!nodeWithPosition) {
      console.warn(`Dagre layout information missing for node ID: ${apiNode.id}`);
      return null;
    }
    return {
      id: apiNode.id,
      type: apiNode.type || (Array.isArray(apiNode.children) && apiNode.children.length > 0 ? 'decision' : 'task'),
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
      data: {
        label: apiNode.title,
        description: apiNode.description,
        ...apiNode
      },
    };
  }).filter(Boolean);

  const finalNodeIds = new Set(reactFlowNodes.map(n => n.id));
  const filteredEdges = reactFlowEdges.filter(edge =>
    finalNodeIds.has(edge.source) && finalNodeIds.has(edge.target)
  );

  return { nodes: reactFlowNodes, edges: filteredEdges };
};

// Main layout function that uses the vertical tree layout
const getLayoutedElements = (apiNodes) => {
  return getVerticalTreeLayout(apiNodes);
};

export const useRoadmapState = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);
  const requestRef = useRef(null);

  const handleConnect = useCallback((params) => {
    setEdges((eds) => addEdge(params, eds));
  }, [setEdges]);

  const initializeRoadmap = useCallback(async (roadmapId) => {
    console.log("initializeRoadmap called with:", roadmapId);
    if (!roadmapId || hasInitialized || isLoading) {
      console.log("Early return:", { hasRoadmapId: !!roadmapId, hasInitialized, isLoading });
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8080/api/v1/roadmaps/${roadmapId}`);
      console.log("API response status:", response.status);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const roadmap = await response.json();
      console.log("Roadmap data fetched:", roadmap);

      if (roadmap?.nodes?.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(roadmap.nodes, 'TB');

        console.log("Layouted Dagre nodes:", layoutedNodes);
        console.log("Layouted Dagre edges:", layoutedEdges);

        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
        setHasInitialized(true);
      } else {
        console.log("No nodes found in roadmap data.");
        setNodes([]);
        setEdges([]);
        setHasInitialized(true);
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Failed to initialize roadmap:', error);
      }
    } finally {
      setIsLoading(false);
    }
  }, [setNodes, setEdges, hasInitialized, isLoading]);

  useEffect(() => {
    const controller = new AbortController();

    return () => {
      controller.abort();
    };
  }, []);

  return {
    nodes,
    edges,
    isLoading,
    onNodesChange,
    onEdgesChange,
    handleConnect,
    initializeRoadmap
  };
};

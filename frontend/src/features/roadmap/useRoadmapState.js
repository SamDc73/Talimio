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
  const processedNodeIds = new Set(); // Track IDs we've seen
  const reactFlowEdges = []; // Edges for React Flow

  // First pass - collect all unique nodes and build parent-child relationships
  const nodeRelationships = new Map(); // Maps node IDs to arrays of child IDs

  // Process nodes to establish parent-child relationships
  apiNodes.forEach(node => {
    uniqueApiNodes.set(node.id, node);

    if (node.parent_id) {
      // Add this node as a child of its parent
      if (!nodeRelationships.has(node.parent_id)) {
        nodeRelationships.set(node.parent_id, []);
      }
      nodeRelationships.get(node.parent_id).push(node.id);
    }

    // Also process any children in the nested structure
    if (Array.isArray(node.children) && node.children.length > 0) {
      node.children.forEach(child => {
        if (!nodeRelationships.has(node.id)) {
          nodeRelationships.set(node.id, []);
        }
        nodeRelationships.get(node.id).push(child.id);

        // Also add the child to uniqueApiNodes if not already there
        if (!uniqueApiNodes.has(child.id)) {
          uniqueApiNodes.set(child.id, child);
        }
      });
    }
  });

  // Find root nodes (nodes without a parent_id or whose parent_id is not in our node list)
  const allNodeIds = new Set(apiNodes.map(n => n.id));
  const rootNodes = apiNodes
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

    // Calculate X position - indent children based on their level
    // For root nodes, place them in the center of a default width
    // For child nodes, indent them relative to their parent
    const centerX = 600; // Default center point (works for both client and server)
    const x = level === 0 ? centerX - (NODE_WIDTH / 2) : parentX + HORIZONTAL_INDENTATION;

    // Store the position
    nodePositions.set(nodeId, { x, y: currentY });

    // Move down for next node
    currentY += VERTICAL_SPACING;

    // Position all children of this node
    const childIds = nodeRelationships.get(nodeId) || [];
    let lastChildY = 0;

    // Check if this parent node should have its children arranged horizontally
    // We already have the node variable defined above, so we don't need to declare it again
    const useHorizontalLayout = shouldUseHorizontalLayout(node, childIds, uniqueApiNodes);

    // If using horizontal layout, calculate the starting X position to center the children
    let startX = x;
    if (useHorizontalLayout && childIds.length > 1) {
      // Calculate position so children are centered around parent
      // For even number of children, we want them evenly distributed left and right
      // For odd number, the middle child should be directly below the parent
      const totalWidth = (childIds.length - 1) * HORIZONTAL_SIBLING_SPACING;
      startX = x - (totalWidth / 2);
    }

    // Save the original Y position for horizontal layouts
    const horizontalRowY = currentY;

    childIds.forEach((childId, index) => {
      // Create the edge from parent to child
      reactFlowEdges.push({
        id: `e${nodeId}-${childId}`,
        source: nodeId,
        target: childId,
        type: 'smoothstep',
      });

      // For horizontal layout, position children side-by-side
      if (useHorizontalLayout) {
        // Reset Y to the horizontal row position for each sibling
        currentY = horizontalRowY;

        // Calculate the horizontal position for this child
        const childX = startX + (index * HORIZONTAL_SIBLING_SPACING);

        // Store position for this specific child
        nodePositions.set(childId, { x: childX, y: currentY });

        // Move down after positioning this node
        currentY += VERTICAL_SPACING;

        // Position this child's descendants
        const childHeight = positionNodeAndChildren(childId, level + 1, childX);
        lastChildY = Math.max(childHeight, lastChildY);
      }
      // For vertical layout (default), use the original logic
      else {
        // Position this child and its descendants
        const childHeight = positionNodeAndChildren(childId, level + 1, x);
        lastChildY = childHeight > 0 ? childHeight : lastChildY;

        // Add extra spacing between siblings
        if (index < childIds.length - 1) {
          currentY += SIBLING_SPACING;
        }
      }
    });

    // Return the bottom-most Y coordinate in this branch
    return lastChildY > 0 ? lastChildY : currentY;
  };

  // Position all root nodes and their descendants
  rootNodes.forEach(rootId => {
    positionNodeAndChildren(rootId);
  });

  // Create the React Flow nodes with their calculated positions
  const reactFlowNodes = Array.from(uniqueApiNodes.values()).map(apiNode => {
    const position = nodePositions.get(apiNode.id);

    // Skip nodes we didn't position (shouldn't happen with proper data)
    if (!position) {
      console.warn(`Position missing for node ID: ${apiNode.id}`);
      return null;
    }

    return {
      id: apiNode.id,
      type: apiNode.type || (nodeRelationships.has(apiNode.id) && nodeRelationships.get(apiNode.id).length > 0 ? 'decision' : 'task'),
      position,
      data: {
        label: apiNode.title,
        description: apiNode.description,
        ...apiNode
      },
    };
  }).filter(Boolean);

  return { nodes: reactFlowNodes, edges: reactFlowEdges };
};

// Keep the original Dagre layout as a fallback
const getDagreLayout = (apiNodes, direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  // Increased ranksep for more vertical space, nodesep for horizontal
  dagreGraph.setGraph({ rankdir: direction, nodesep: 70, ranksep: 100 });

  const uniqueApiNodes = new Map(); // Store unique nodes by ID
  const processedNodeIds = new Set(); // Track IDs added to dagre
  const reactFlowEdges = []; // Edges for React Flow

  // Recursive function to traverse API nodes and add unique ones to Dagre graph
  const processApiNodes = (nodes, parentId = null) => {
    nodes.forEach((node) => {
      // Process this node only if its ID hasn't been seen before
      if (!processedNodeIds.has(node.id)) {
        processedNodeIds.add(node.id);
        uniqueApiNodes.set(node.id, node); // Store unique node data
        dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
      } else {
        // Log if we encounter an ID again in the hierarchy (might indicate backend issue)
        // console.warn(`Node ID ${node.id} encountered again in hierarchy, skipping add to dagre graph.`);
      }

      // Add edge regardless of whether the node was already processed (edge connects existing nodes)
      if (parentId) {
        // Ensure edge doesn't already exist (simple check)
        const edgeId = `e${parentId}-${node.id}`;
        if (!reactFlowEdges.some(e => e.id === edgeId)) {
          dagreGraph.setEdge(parentId, node.id);
          reactFlowEdges.push({
            id: edgeId,
            source: parentId,
            target: node.id,
            type: 'smoothstep', // Using smoothstep for potentially better edge routing
          });
        }
      }

      // Recurse for children if they exist and are an array
      if (Array.isArray(node.children) && node.children.length > 0) {
        processApiNodes(node.children, node.id);
      }
    });
  };

  // Find root nodes (nodes without a parent_id or whose parent_id is not in the list)
  const allNodeIds = new Set(apiNodes.map(n => n.id));
  const rootNodes = apiNodes.filter(node => !node.parent_id || !allNodeIds.has(node.parent_id));

  processApiNodes(rootNodes);

  dagre.layout(dagreGraph);

  // Map unique layouted nodes back to React Flow format
  const reactFlowNodes = Array.from(uniqueApiNodes.values()).map((apiNode) => {
    const nodeWithPosition = dagreGraph.node(apiNode.id);
    if (!nodeWithPosition) {
      console.warn(`Dagre layout information missing for node ID: ${apiNode.id}`);
      return null; // Should not happen if added correctly, but safety check
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
  }).filter(Boolean); // Filter out any nulls from safety check

  // Filter edges again just in case (source/target might not be in uniqueApiNodes if data is inconsistent)
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


// Removed old layout constants
export const useRoadmapState = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);
  const requestRef = useRef(null);

  const handleConnect = useCallback((params) => {
    setEdges((eds) => addEdge(params, eds));
  }, [setEdges]);

  // Removed old processNodes function
  const initializeRoadmap = useCallback(async (roadmapId) => {
    console.log("initializeRoadmap called with:", roadmapId);
    if (!roadmapId || hasInitialized || isLoading) {
      console.log("Early return:", { hasRoadmapId: !!roadmapId, hasInitialized, isLoading });
      return;
    }

    setIsLoading(true);
    try {
      // Consider using AbortController for fetch requests
      const response = await fetch(`http://localhost:8080/api/v1/roadmaps/${roadmapId}`);
      console.log("API response status:", response.status);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const roadmap = await response.json();
      console.log("Roadmap data fetched:", roadmap);

      if (roadmap?.nodes?.length > 0) {
        // Use Dagre layout function directly
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(roadmap.nodes, 'TB');

        console.log("Layouted Dagre nodes:", layoutedNodes);
        console.log("Layouted Dagre edges:", layoutedEdges);

        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
        setHasInitialized(true); // Mark as initialized after successful layout
      } else {
        console.log("No nodes found in roadmap data.");
        // Optionally clear state if roadmap is empty
        setNodes([]);
        setEdges([]);
        setHasInitialized(true);
      }
    } catch (error) {
      // Handle fetch or layout errors
      if (error.name !== 'AbortError') {
        console.error('Failed to initialize roadmap:', error);
        // Optionally trigger an error state or notification
      }
    } finally {
      setIsLoading(false);
    }
  }, [setNodes, setEdges, hasInitialized, isLoading]); // Dependencies for useCallback

  // Cleanup on unmount (example if using AbortController)
  useEffect(() => {
    const controller = new AbortController();
    // Pass controller.signal to fetch if implemented

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

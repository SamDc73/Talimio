import { useNodesState, useEdgesState, addEdge } from '@xyflow/react'; // Added addEdge import
import { useCallback, useState, useRef, useEffect } from 'react';  // Added useRef import
import dagre from '@dagrejs/dagre';

// --- Dagre Layout Helper ---
const NODE_WIDTH = 250; // Adjust based on your node styling
const NODE_HEIGHT = 100; // Increased height for better spacing

const getLayoutedElements = (apiNodes, direction = 'TB') => {
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

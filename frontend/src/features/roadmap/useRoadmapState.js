import { useNodesState, useEdgesState, addEdge } from '@xyflow/react'; // Added addEdge import
import { useCallback, useState, useRef, useEffect } from 'react';  // Added useRef import
import dagre from '@dagrejs/dagre';
import { getCenteredBranchingLayout } from './centeredBranchingLayout';

// --- Dagre Layout Helper ---
const NODE_WIDTH = 250; // Adjust based on your node styling
const NODE_HEIGHT = 50; // Adjust based on your node styling

const getLayoutedElements = (apiNodes, direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 70 }); // Add spacing options

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
            type: 'smoothstep',
          });
        }
      }

      // Recurse for children
      if (node.children && node.children.length > 0) {
        processApiNodes(node.children, node.id);
      }
    });
  };

  processApiNodes(apiNodes); // Start processing from root nodes

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
      type: apiNode.type || 'default',
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
      data: {
        label: apiNode.title,
        description: apiNode.description,
        content: apiNode.content,
        status: apiNode.status,
      },
      parentId: apiNode.parent_id,
    };
  }).filter(Boolean); // Filter out any nulls from safety check

  // Filter edges again just in case (source/target might not be in uniqueApiNodes if data is inconsistent)
  const finalNodeIds = new Set(reactFlowNodes.map(n => n.id));
  const filteredEdges = reactFlowEdges.filter(edge =>
    finalNodeIds.has(edge.source) && finalNodeIds.has(edge.target)
  );

  return { nodes: reactFlowNodes, edges: filteredEdges };
};
// --- End Dagre Layout Helper ---


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
    console.log("initializeRoadmap called with:", roadmapId); // Debug log
    if (!roadmapId || hasInitialized || isLoading) {
      console.log("Early return:", { hasRoadmapId: !!roadmapId, hasInitialized, isLoading }); // Debug log
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8080/api/v1/roadmaps/${roadmapId}`);
      console.log("API response:", response.status); // Debug log

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const roadmap = await response.json();
      console.log("Roadmap data:", roadmap); // Debug log

      if (roadmap?.nodes?.length > 0) {
        // Use centered branching layout for vertical center with left/right children
        const { nodes: layoutedNodes, edges: layoutedEdges } = getCenteredBranchingLayout(roadmap.nodes);

        console.log("Layouted flowNodes:", layoutedNodes); // Debug log
        console.log("Layouted flowEdges:", layoutedEdges); // Debug log

        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
        setHasInitialized(true);
      }
    } catch (error) {
      console.error('Failed to initialize roadmap:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setNodes, setEdges, hasInitialized, isLoading]); // Removed processNodes dependency

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (requestRef.current) {
        requestRef.current.abort();
      }
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

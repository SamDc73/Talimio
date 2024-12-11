import { useNodesState, useEdgesState } from '@xyflow/react';
import { useCallback, useState, useRef, useEffect } from 'react';  // Added useRef import

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
        const flowNodes = roadmap.nodes.map((node) => ({
          id: node.id,
          type: 'default',
          position: {
            x: node.order * 250,
            y: 100 + (node.order % 2) * 100
          },
          data: {
            label: node.title,
            description: node.description,
            content: node.content,
            status: node.status,
          },
        }));

        console.log("Created flowNodes:", flowNodes); // Debug log

        // Create edges between consecutive nodes
        const flowEdges = flowNodes.slice(0, -1).map((node, index) => ({
          id: `e${node.id}-${flowNodes[index + 1].id}`,
          source: node.id,
          target: flowNodes[index + 1].id,
          type: 'smoothstep',
        }));

        console.log("Created flowEdges:", flowEdges); // Debug log

        setNodes(flowNodes);
        setEdges(flowEdges);
        setHasInitialized(true);
      }
    } catch (error) {
      console.error('Failed to initialize roadmap:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setNodes, setEdges, hasInitialized, isLoading]);

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

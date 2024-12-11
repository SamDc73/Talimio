import { useNodesState, useEdgesState, addEdge } from '@xyflow/react';
import { useCallback, useState } from 'react';

import { calculateNodePosition, createEdge, serializeGraphState } from './roadmapUtils';

import { useApi } from '@/hooks/useApi';
import { NodeGenerator } from '@/lib/mock-data/node-generator';
import { MOCK_ROADMAP_DATA } from '@/lib/mock-data/roadmap';

export const useRoadmapState = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const {
    data: roadmapData,
    error: roadmapError,
    isLoading: isLoadingRoadmap,
    execute: fetchRoadmap
  } = useApi('/api/v1/roadmaps');

  const handleConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const handleNodeDragStop = useCallback(
    (event, node) => {
      console.log('Node position updated:', node);
    },
    []
  );

  const generateNodesFromContext = useCallback(async (sourceNodeId, count = 1) => {
    const sourceNode = nodes.find(n => n.id === sourceNodeId);
    if (!sourceNode) return;

    try {
      const graphContext = serializeGraphState(nodes, edges);
      const generatedNodes = NodeGenerator.generateNodes(sourceNode, count, graphContext);

      const positionedNodes = generatedNodes.map((node, index) => ({
        ...node,
        position: calculateNodePosition(sourceNode, index)
      }));

      const newEdges = positionedNodes.map(node =>
        createEdge(sourceNodeId, node.id)
      );

      setNodes(nodes => [...nodes, ...positionedNodes]);
      setEdges(edges => [...edges, ...newEdges]);

      return positionedNodes;
    } catch (error) {
      console.error('Failed to generate nodes:', error);
      return [];
    }
  }, [nodes, edges, setNodes, setEdges]);

  const initializeRoadmap = useCallback(async (roadmapId) => {
    try {
      if (!roadmapId) {
        // If no roadmap ID, return null to trigger onboarding
        return null;
      }

      const response = await fetchRoadmap(`/api/v1/roadmaps/${roadmapId}`);
      if (response) {
        setNodes(response.nodes || []);
        setEdges(response.edges || []);
        return response;
      }
      return null;
    } catch (error) {
      console.error('Failed to initialize roadmap:', error);
      return null;
    }
  }, [fetchRoadmap, setNodes, setEdges]);
  
  return {
    nodes,
    edges,
    roadmapData,
    roadmapError,
    isLoadingRoadmap,
    onNodesChange,
    onEdgesChange,
    handleConnect,
    handleNodeDragStop,
    initializeRoadmap,
    generateNodesFromContext
  };
};

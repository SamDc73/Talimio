import { useNodesState, useEdgesState, addEdge } from '@xyflow/react';
import { useCallback, useState } from 'react';

import { calculateNodePosition, createEdge, serializeGraphState } from './roadmapUtils';

import { useApi } from '@/hooks/useApi';
import { NodeGenerator } from '@/lib/mock-data/node-generator';
import { MOCK_ROADMAP_DATA } from '@/lib/mock-data/roadmap';

export const useRoadmapState = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(MOCK_ROADMAP_DATA.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(MOCK_ROADMAP_DATA.edges);

  const {
    data: roadmapData,
    error: roadmapError,
    isLoading: isLoadingRoadmap,
    execute: fetchRoadmap
  } = useApi('/api/roadmap', { fallbackData: MOCK_ROADMAP_DATA });

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

  const initializeRoadmap = useCallback(async (roadmap = MOCK_ROADMAP_DATA) => {
    try {
      setNodes(roadmap.nodes);
      setEdges(roadmap.edges);
      return roadmap;
    } catch (error) {
      console.error('Failed to initialize roadmap:', error);
      setNodes(MOCK_ROADMAP_DATA.nodes);
      setEdges(MOCK_ROADMAP_DATA.edges);
      return MOCK_ROADMAP_DATA;
    }
  }, [setNodes, setEdges]);

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

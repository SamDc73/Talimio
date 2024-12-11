import { useApi } from './useApi';
import { useNodesState, useEdgesState, addEdge } from '@xyflow/react';
import { useCallback } from 'react';

export function useRoadmap() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const { execute: executeCreateRoadmap } = useApi('/api/v1/roadmaps', {
    method: 'POST'
  });
  // Change this to initialize without an endpoint
  const { execute: executeGetRoadmap } = useApi('');

  const createRoadmap = async (data) => {
    try {
      if (!data.title || !data.description || !data.skill_level) {
        throw new Error('Missing required roadmap fields');
      }

      if (!['beginner', 'intermediate', 'advanced'].includes(data.skill_level)) {
        data.skill_level = 'beginner';
      }

      const response = await executeCreateRoadmap(data);
      return response;
    } catch (error) {
      console.error('Error creating roadmap:', error);
      throw error;
    }
  };

  // Modify getRoadmap to use the correct endpoint format
  const getRoadmap = async (id) => {
    try {
      if (!id) {
        throw new Error('Roadmap ID is required');
      }
      // Use template literal to construct the full URL
      const response = await executeGetRoadmap(null, {
        url: `/api/v1/roadmaps/${id}`,
        method: 'GET'
      });
      return response;
    } catch (error) {
      console.error('Error getting roadmap:', error);
      throw error;
    }
  };

  const initializeRoadmap = useCallback(async (roadmapId) => {
    try {
      if (!roadmapId) {
        return null;
      }

      const roadmap = await getRoadmap(roadmapId);
      if (!roadmap || !roadmap.id) {
        console.error('Invalid roadmap data received:', roadmap);
        return null;
      }

      return roadmap;
    } catch (error) {
      console.error('Failed to initialize roadmap:', error);
      return null;
    }
  }, [getRoadmap]);

  return {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    createRoadmap,
    getRoadmap,
    initializeRoadmap
  };
}

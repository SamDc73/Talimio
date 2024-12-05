import { useApi } from './useApi';

export function useRoadmap() {
  const { execute: createRoadmap } = useApi('/roadmaps', { method: 'POST' });
  const { execute: getRoadmap } = useApi('/roadmaps');
  const { execute: createNode } = useApi('/roadmaps/{roadmapId}/nodes', { method: 'POST' });
  const { execute: updateNode } = useApi('/roadmaps/{roadmapId}/nodes/{nodeId}', { method: 'PUT' });

  const handleCreateRoadmap = async (data) => {
    return await createRoadmap({
      title: data.title,
      description: data.description,
      skill_level: data.skill_level
    });
  };

  const handleGetRoadmap = async (id) => {
    return await getRoadmap(null, { params: { id } });
  };

  const handleCreateNode = async (roadmapId, data) => {
    return await createNode(data, {
      url: `/roadmaps/${roadmapId}/nodes`
    });
  };

  const handleUpdateNode = async (roadmapId, nodeId, data) => {
    return await updateNode(data, {
      url: `/roadmaps/${roadmapId}/nodes/${nodeId}`
    });
  };

  return {
    createRoadmap: handleCreateRoadmap,
    getRoadmap: handleGetRoadmap,
    createNode: handleCreateNode,
    updateNode: handleUpdateNode
  };
}

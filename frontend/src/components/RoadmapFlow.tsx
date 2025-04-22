import dagre from "@dagrejs/dagre";
import {
  Background,
  ConnectionMode,
  Controls,
  type Edge,
  type EdgeChange,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeChange,
  Panel,
  Position,
  ReactFlow,
  applyEdgeChanges,
  applyNodeChanges,
  useReactFlow,
} from "@xyflow/react";
import { useCallback, useEffect, useState } from "react";
import "@xyflow/react/dist/style.css";

// Constants
const NODE_WIDTH = 220;
const NODE_HEIGHT = 80;
const HORIZONTAL_GAP = 250;

// Types
interface RoadmapNode {
  id: string;
  title: string;
  description?: string;
  children?: RoadmapNode[];
}

interface NodeData extends Record<string, unknown> {
  label: string;
  description?: string;
  parentId?: string | null;
  siblingIndex?: number;
  totalSiblings?: number;
  parentX?: number;
}

type CustomNode = Node<NodeData>;

// Update the node components with better styling and keyboard support
const DefaultNode = ({ data }: { data: NodeData }) => (
  <div className="w-[220px] group">
    <Handle type="target" position={Position.Top} className="!bg-gray-400 !w-2 !h-2" />
    <button
      type="button"
      className="w-full p-4 rounded-lg border border-gray-200 bg-white shadow-sm hover:shadow-md hover:border-indigo-200 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 text-left"
      onClick={() => console.log("Node clicked:", data.label)}
      aria-label={`Navigate to ${data.label}`}
    >
      <h3 className="font-medium text-gray-900 truncate" title={data.label}>
        {data.label}
      </h3>
      {data.description && (
        <p className="mt-1 text-sm text-gray-500 line-clamp-2 group-hover:line-clamp-none" title={data.description}>
          {data.description}
        </p>
      )}
    </button>
    <Handle type="source" position={Position.Bottom} className="!bg-gray-400 !w-2 !h-2" />
  </div>
);

const GroupNode = ({ data }: { data: NodeData }) => (
  <div className="w-[220px] group">
    <Handle type="target" position={Position.Top} className="!bg-indigo-400 !w-2 !h-2" />
    <button
      type="button"
      className="w-full p-4 rounded-lg border-2 border-indigo-200 bg-indigo-50 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 text-left"
      onClick={() => console.log("Group clicked:", data.label)}
      aria-label={`Open group ${data.label}`}
    >
      <h3 className="font-medium text-indigo-900 truncate" title={data.label}>
        {data.label}
      </h3>
      {data.description && (
        <p className="mt-1 text-sm text-indigo-600/70 line-clamp-2 group-hover:line-clamp-none" title={data.description}>
          {data.description}
        </p>
      )}
    </button>
    <Handle type="source" position={Position.Bottom} className="!bg-indigo-400 !w-2 !h-2" />
  </div>
);

const nodeTypes = {
  default: DefaultNode,
  group: GroupNode,
};

// Layout utility functions
const processRoadmapData = (roadmap: { nodes: RoadmapNode[] }): { nodes: CustomNode[]; edges: Edge[] } => {
  const nodes: CustomNode[] = [];
  const edges: Edge[] = [];
  let currentY = 0;

  const traverse = (node: RoadmapNode, parentId: string | null = null) => {
    const customNode: CustomNode = {
      id: node.id,
      type: node.children?.length ? "group" : "default",
      position: { x: 0, y: currentY },
      data: {
        label: node.title,
        description: node.description,
        parentId,
      },
    };
    nodes.push(customNode);
    currentY += NODE_HEIGHT + 50;

    if (parentId) {
      edges.push({
        id: `e${parentId}-${node.id}`,
        source: parentId,
        target: node.id,
        type: "smoothstep",
      });
    }

    if (node.children) {
      for (const child of node.children) {
        traverse(child, node.id);
      }
    }
  };

  for (const node of roadmap.nodes) {
    traverse(node);
  }

  return { nodes, edges };
};

const applyDagreLayout = (nodes: CustomNode[], edges: Edge[]): { nodes: CustomNode[]; edges: Edge[] } => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: "TB", nodesep: 70, ranksep: 100 });

  for (const node of nodes) {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  for (const edge of edges) {
    dagreGraph.setEdge(edge.source, edge.target);
  }

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

const applyHierarchicalLayout = (nodes: CustomNode[], edges: Edge[]): { nodes: CustomNode[]; edges: Edge[] } => {
  const childrenMap = new Map<string | null, CustomNode[]>();

  // Group nodes by parent
  for (const node of nodes) {
    const parentId = node.data?.parentId ?? null;
    const children = childrenMap.get(parentId) || [];
    childrenMap.set(parentId, children);
    children.push(node);
  }

  const layoutLevel = (
    levelNodes: CustomNode[],
    level: number,
    startX: number,
    startY: number,
  ): { width: number; height: number } => {
    if (levelNodes.length === 0) {
      return { width: 0, height: 0 };
    }

    let totalWidth = 0;
    let maxHeight = 0;

    // Position nodes at this level
    const nodesWithPositions = levelNodes.map((currentNode, index) => {
      const nodeX = startX + totalWidth;
      const nodeY = startY;

      // Update node position and data
      currentNode.position = { x: nodeX, y: nodeY };
      currentNode.data = {
        ...currentNode.data,
        siblingIndex: index,
        totalSiblings: levelNodes.length,
      };

      // Layout children of this node
      const children = childrenMap.get(currentNode.id) || [];
      const { width: childWidth, height: childHeight } = layoutLevel(
        children,
        level + 1,
        nodeX,
        nodeY + NODE_HEIGHT + HORIZONTAL_GAP,
      );

      const nodeWidth = Math.max(NODE_WIDTH, childWidth);
      totalWidth += nodeWidth + (index < levelNodes.length - 1 ? HORIZONTAL_GAP : 0);
      maxHeight = Math.max(maxHeight, NODE_HEIGHT + childHeight);

      return currentNode;
    });

    // Center nodes if they have less total width than their parent
    const parentWidth = levelNodes.length * NODE_WIDTH + (levelNodes.length - 1) * HORIZONTAL_GAP;
    if (totalWidth < parentWidth) {
      const offset = (parentWidth - totalWidth) / 2;
      for (const node of nodesWithPositions) {
        node.position.x += offset;
      }
      totalWidth = parentWidth;
    }

    return { width: totalWidth, height: maxHeight };
  };

  // Start with root nodes (those without parents)
  const rootNodes = nodes.filter((node) => !node.data.parentId);
  layoutLevel(rootNodes, 0, 100, 100);

  return { nodes, edges };
};

// Main Component
export const RoadmapFlow: React.FC<{ roadmap?: { nodes: RoadmapNode[] } }> = ({ roadmap }) => {
  const [nodes, setNodes] = useState<CustomNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const { fitView } = useReactFlow();

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds) as CustomNode[]);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const onInit = useCallback(() => {
    setTimeout(() => {
      fitView({ padding: 0.2, duration: 200 });
    }, 100);
  }, [fitView]);

  useEffect(() => {
    if (roadmap?.nodes) {
      const { nodes: initialNodes, edges: initialEdges } = processRoadmapData(roadmap);
      const { nodes: layoutedNodes, edges: layoutedEdges } = applyHierarchicalLayout(initialNodes, initialEdges);
      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
    }
  }, [roadmap]);

  const onLayout = useCallback(() => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = applyHierarchicalLayout(nodes, edges);
    setNodes([...layoutedNodes]);
    setEdges([...layoutedEdges]);

    setTimeout(() => {
      fitView({ padding: 0.2, duration: 200 });
    }, 100);
  }, [nodes, edges, fitView]);

  if (!roadmap?.nodes) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">No roadmap data available</p>
      </div>
    );
  }

  return (
    <div className="h-screen w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        fitView={false}
        className="bg-gray-50"
        defaultEdgeOptions={{
          type: "smoothstep",
          animated: true,
          style: { stroke: "#94a3b8", strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#94a3b8",
          },
        }}
        connectionMode={ConnectionMode.Loose}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#e2e8f0" gap={16} size={1} />
        <Controls />
        <MiniMap
          nodeColor={(node) => (node.type === "group" ? "#818cf8" : "#cbd5e1")}
          nodeStrokeWidth={3}
          zoomable
          pannable
        />
        <Panel position="top-right">
          <button
            type="button"
            onClick={onLayout}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
          >
            Reset Layout
          </button>
        </Panel>
      </ReactFlow>
    </div>
  );
};

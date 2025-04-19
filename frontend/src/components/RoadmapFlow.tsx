import { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  Panel
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from '@dagrejs/dagre';

// Define types for roadmap data
interface RoadmapNode {
  id: string;
  title: string;
  description: string;
  content?: string;
  status: string;
  parent_id: string | null;
  order: number;
  prerequisite_ids: string[];
  children: RoadmapNode[];
}

interface Roadmap {
  title: string;
  description: string;
  skill_level: string;
  id: string;
  nodes: RoadmapNode[];
}

// Node dimensions
const NODE_WIDTH = 200;
const NODE_HEIGHT = 100;
const HORIZONTAL_GAP = 250; // Horizontal spacing between nodes
const VERTICAL_GAP = 150;   // Vertical spacing between nodes

// Function to determine if siblings should be displayed horizontally
const shouldDisplayHorizontally = (node: RoadmapNode): boolean => {
  // Check if node is one of the specific ones we want to display horizontally
  if (node.title === "What is FastAPI?" || node.title === "FastAPI vs Other Frameworks") {
    return true;
  }
  return false;
};

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction });

  // Add nodes to dagre
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  // Add edges to dagre
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Layout with dagre
  dagre.layout(dagreGraph);

  // Process the layout but customize for specific nodes
  // Track parent nodes and their children for horizontal layout
  const parentChildMap = new Map<string, Node[]>();

  // First pass: collect all children by parent
  nodes.forEach((node) => {
    if (node.data && node.data.parentId) {
      if (!parentChildMap.has(node.data.parentId)) {
        parentChildMap.set(node.data.parentId, []);
      }
      parentChildMap.get(node.data.parentId)?.push(node);
    }
  });

  // Second pass: apply horizontal layout to specific node children
  const processedNodes = nodes.map((node) => {
    const nodeWithPosition = { ...node };
    const dagreNode = dagreGraph.node(node.id);

    // Basic positioning from dagre
    nodeWithPosition.position = {
      x: dagreNode.x - NODE_WIDTH / 2,
      y: dagreNode.y - NODE_HEIGHT / 2,
    };

    return nodeWithPosition;
  });

  // Third pass: adjust siblings for horizontal layout where needed
  processedNodes.forEach((node) => {
    if (node.data && node.data.horizontalLayout && node.data.siblings && node.data.siblingIndex !== undefined) {
      // Calculate horizontal position based on sibling index
      const horizontalOffset = (node.data.siblingIndex - (node.data.totalSiblings - 1) / 2) * HORIZONTAL_GAP;
      node.position.x = node.data.parentX + horizontalOffset;
    }
  });

  return { nodes: processedNodes, edges };
};

// Transform roadmap data into React Flow nodes and edges
const createNodesAndEdges = (roadmap: Roadmap | null) => {
  if (!roadmap) return { nodes: [], edges: [] };

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Helper function to process nodes recursively
  const processNode = (
    node: RoadmapNode,
    level: number,
    parentX: number | null = null,
    horizontalLayout: boolean = false,
    siblingCount: number = 0,
    siblingIndex: number = 0
  ) => {
    // Determine if this node's children should be horizontal
    const useHorizontalLayout = shouldDisplayHorizontally(node);

    // Create React Flow node
    const flowNode: Node = {
      id: node.id,
      data: {
        label: node.title,
        description: node.description,
        status: node.status,
        level,
        parentId: node.parent_id,
        horizontalLayout,
        parentX,
        siblings: siblingCount,
        siblingIndex,
        totalSiblings: siblingCount
      },
      position: { x: 0, y: 0 }, // Initial position, will be calculated by layout
      type: 'default'
    };

    nodes.push(flowNode);

    // Create edge from parent if exists
    if (node.parent_id) {
      edges.push({
        id: `edge-${node.parent_id}-${node.id}`,
        source: node.parent_id,
        target: node.id,
        type: 'smoothstep',
      });
    }

    // Process children
    if (node.children && node.children.length > 0) {
      const totalChildren = node.children.length;
      node.children.forEach((child, index) => {
        processNode(
          child,
          level + 1,
          null,  // Will be calculated after layout
          useHorizontalLayout,
          totalChildren,
          index
        );
      });
    }
  };

  // Start processing from top-level nodes
  roadmap.nodes.forEach((node, index) => {
    processNode(node, 0);
  });

  return { nodes, edges };
};

// Custom function to apply layout for specific cases
const applyCustomLayout = (nodes: Node[], edges: Edge[]) => {
  // Apply dagre layout first to get general positions
  const { nodes: layoutedNodes } = getLayoutedElements(nodes, edges);

  // Create a map for quick node lookup
  const nodeMap = new Map<string, Node>();
  layoutedNodes.forEach(node => nodeMap.set(node.id, node));

  // Find parent nodes
  const parentChildMap = new Map<string, Node[]>();

  // Group children by parent
  layoutedNodes.forEach(node => {
    if (node.data && node.data.parentId) {
      if (!parentChildMap.has(node.data.parentId)) {
        parentChildMap.set(node.data.parentId, []);
      }
      parentChildMap.get(node.data.parentId)?.push(node);
    }
  });

  // Apply horizontal layout for specific parents
  const horizontalGroups = [
    "fc7bb19f-2cc7-4b6e-be70-82b79d1f4711", // "What is FastAPI?"
    "6ed84bb3-26da-4a07-b157-dea761373a6e"  // "FastAPI vs Other Frameworks"
  ];

  horizontalGroups.forEach(parentId => {
    const children = parentChildMap.get(parentId) || [];
    if (children.length < 2) return;

    const parent = nodeMap.get(parentId);
    if (!parent) return;

    // Calculate center position based on parent
    const parentX = parent.position.x + NODE_WIDTH / 2;
    const parentY = parent.position.y + NODE_HEIGHT + VERTICAL_GAP;

    // Position children horizontally
    children.forEach((child, index) => {
      const offset = (index - (children.length - 1) / 2) * HORIZONTAL_GAP;
      child.position = {
        x: parentX + offset - NODE_WIDTH / 2,
        y: parentY
      };
    });
  });

  return { nodes: layoutedNodes, edges };
};

const RoadmapFlow = ({ roadmapData }: { roadmapData: Roadmap | null }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (roadmapData) {
      const { nodes: initialNodes, edges: initialEdges } = createNodesAndEdges(roadmapData);
      const { nodes: layoutedNodes, edges: layoutedEdges } = applyCustomLayout(initialNodes, initialEdges);

      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
    }
  }, [roadmapData, setNodes, setEdges]);

  const onLayout = useCallback(() => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = applyCustomLayout(nodes, edges);
    setNodes([...layoutedNodes]);
    setEdges([...layoutedEdges]);
  }, [nodes, edges, setNodes, setEdges]);

  return (
    <div style={{ width: '100%', height: '800px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
        <Panel position="top-right">
          <button onClick={onLayout}>Reset Layout</button>
        </Panel>
      </ReactFlow>
    </div>
  );
};

export default RoadmapFlow;

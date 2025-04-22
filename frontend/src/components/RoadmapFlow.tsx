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

// Utility: Check for duplicates in an array
function findDuplicates(arr: string[]): string[] {
  const seen = new Set<string>();
  const duplicates = new Set<string>();
  for (const id of arr) {
    if (seen.has(id)) {
      duplicates.add(id);
    } else {
      seen.add(id);
    }
  }
  return Array.from(duplicates);
}

// Transform roadmap data into React Flow nodes and edges
const createNodesAndEdges = (roadmap: Roadmap | null) => {
  if (!roadmap) return { nodes: [], edges: [] };

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  function traverse(node: RoadmapNode, parentId: string | null, level: number) {
    nodes.push({
      id: node.id,
      data: {
        label: node.title,
        description: node.description,
        status: node.status,
        level,
        parentId: node.parent_id,
      },
      position: { x: 0, y: 0 },
      type: 'default',
    });

    if (parentId) {
      edges.push({
        id: `edge-${parentId}-${node.id}`,
        source: parentId,
        target: node.id,
        type: 'smoothstep',
      });
    }

    if (node.children && node.children.length > 0) {
      node.children.forEach(child => traverse(child, node.id, level + 1));
    }
  }

  roadmap.nodes.forEach(root => traverse(root, null, 0));

  return { nodes, edges };
};

// Custom function to apply a simple tree layout so all siblings are visible
const applyCustomLayout = (nodes: Node[], edges: Edge[]) => {
  // Build a map of parentId -> children
  const childrenMap = new Map<string | null, Node[]>();
  nodes.forEach(node => {
    const parentId = node.data.parentId || null;
    if (!childrenMap.has(parentId)) {
      childrenMap.set(parentId, []);
    }
    childrenMap.get(parentId)?.push(node);
  });

  // Recursive layout assignment
  let yStep = 150;
  let xStep = 220;
  let maxX = 0;

  function layout(node: Node, depth: number, x: number) {
    node.position = { x, y: depth * yStep };
    maxX = Math.max(maxX, x);
    const children = childrenMap.get(node.id) || [];
    if (children.length === 0) return;
    // Space children horizontally
    let startX = x - ((children.length - 1) * xStep) / 2;
    children.forEach((child, idx) => {
      layout(child, depth + 1, startX + idx * xStep);
    });
  }

  // Layout all root nodes
  const roots = childrenMap.get(null) || [];
  roots.forEach((root, i) => {
    layout(root, 0, i * xStep * 2);
  });

  return { nodes, edges };
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
    <div style={{ width: '100%', height: '800px', overflow: 'auto' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        zoomOnScroll={false}
        panOnScroll={false}
        preventScrolling={false}
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

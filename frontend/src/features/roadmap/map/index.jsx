import { Background, Controls, ReactFlow } from "@xyflow/react";
import { X } from "lucide-react";
import React, { useState, useCallback, useMemo } from "react";

import {
	Dialog,
	DialogClose,
	DialogContent,
	DialogDescription,
	DialogTitle,
} from "@/components/dialog";

import { NodeGenerationForm } from "../shared/NodeGenerationForm";
import { NodeProperties } from "../shared/NodeProperties";
import { useRoadmapState } from "../shared/useRoadmapState";
import { DecisionNode } from "./DecisionNode";
import { NodeConnections } from "./NodeConnections";
import { TaskNode } from "./TaskNode";

// Edge styling options
const edgeOptions = {
	type: "smoothstep",
	style: {
		strokeWidth: 3,
		stroke: "#22c55e",
	},
	markerEnd: {
		type: "arrow",
		width: 20,
		height: 20,
		color: "#22c55e",
	},
	animated: true,
};

/**
 * MapView component - Renders the visual map view of the roadmap
 */
const MapView = ({ roadmapId }) => {
	const { nodes, edges, onNodesChange, onEdgesChange, handleConnect } =
		useRoadmapState(roadmapId);

	const [selectedNode, setSelectedNode] = useState(null);
	const [isDialogOpen, setIsDialogOpen] = useState(false);

	// Apply edge styling
	const styledEdges = useMemo(() => {
		return edges.map((edge) => ({
			...edge,
			...edgeOptions,
		}));
	}, [edges]);

	// Handle node click to show properties dialog
	const handleNodeClick = useCallback((_, node) => {
		setSelectedNode(node);
		setIsDialogOpen(true);
	}, []);

	// Handle dialog close
	const handleDialogOpenChange = useCallback((open) => {
		setIsDialogOpen(open);
		if (!open) {
			setSelectedNode(null);
		}
	}, []);

	// Define node types for ReactFlow
	const nodeTypes = {
		decision: DecisionNode,
		task: TaskNode,
	};

	// Get child nodes for the selected node
	const childNodes = selectedNode
		? edges
				.filter((edge) => edge.source === selectedNode.id)
				.map((edge) => edge.target)
		: [];

	// Handle node generation
	const handleNodeGeneration = useCallback(
		async (count) => {
			// This is a placeholder for the actual node generation logic
			console.log(`Generate ${count} nodes from ${selectedNode?.id}`);
			// In a real implementation, this would call an API to generate nodes
			return Promise.resolve();
		},
		[selectedNode],
	);

	if (!nodes.length) {
		return null;
	}

	return (
		<>
			<ReactFlow
				nodes={nodes}
				edges={styledEdges}
				onNodesChange={onNodesChange}
				onEdgesChange={onEdgesChange}
				onConnect={handleConnect}
				onNodeClick={handleNodeClick}
				nodeTypes={nodeTypes}
				defaultEdgeOptions={edgeOptions}
				fitView
				zoomOnScroll={false}
				panOnScroll={true}
				zoomActivationKeyCode={"Control"}
				preventScrolling={false}
				className="bg-background"
				minZoom={0.2}
				maxZoom={1.5}
				snapToGrid={true}
				snapGrid={[15, 15]}
				proOptions={{ hideAttribution: true }}
			>
				<Background variant="dots" gap={12} size={1} />
				<Controls position="bottom-right" />
			</ReactFlow>

			<Dialog open={isDialogOpen} onOpenChange={handleDialogOpenChange}>
				<DialogContent className="sm:max-w-[425px]">
					{selectedNode && (
						<>
							<DialogTitle>
								{selectedNode.data?.label ||
									selectedNode.data?.title ||
									"Node Properties"}
							</DialogTitle>
							<DialogDescription>
								{selectedNode.data?.description ||
									"View and edit node properties"}
							</DialogDescription>

							<div className="mt-6 space-y-6">
								<NodeProperties node={selectedNode} />
								<NodeConnections childNodes={childNodes} />
								<NodeGenerationForm onGenerate={handleNodeGeneration} />
							</div>

							<DialogClose className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none">
								<X className="h-4 w-4" />
								<span className="sr-only">Close</span>
							</DialogClose>
						</>
					)}
				</DialogContent>
			</Dialog>
		</>
	);
};

export default MapView;

import * as Dialog from "@radix-ui/react-dialog";
import { ReactFlow, Controls, MiniMap, Background } from "@xyflow/react";
import { X } from "lucide-react";
import React, { useState, useEffect, useCallback } from "react";

import { DecisionNode } from "./DecisionNode";
import { NodeConnections } from "./NodeConnections";
import { NodeGenerationForm } from "./NodeGenerationForm";
import { NodeProperties } from "./NodeProperties";
import { TaskNode } from "./TaskNode";
import { useRoadmapState } from "./useRoadmapState";
import { useToast } from "@/hooks/use-toast";

const RoadmapFlow = React.forwardRef(({ roadmapId, onError }, ref) => {
  const {
    nodes,
    edges,
    isLoadingRoadmap,
    roadmapError,
    initializeRoadmap,
    onNodesChange,
    onEdgesChange,
    handleConnect,
    handleNodeDragStop,
    generateNodesFromContext,
    setNodes,
    setEdges,
  } = useRoadmapState();

  const [selectedNode, setSelectedNode] = useState(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const { toast } = useToast();
  const flowRef = React.useRef(null);

  useEffect(() => {
    const loadRoadmap = async () => {
      if (!roadmapId) {
        console.error("No roadmap ID provided");
        onError?.();
        return;
      }

      try {
        const roadmap = await initializeRoadmap(roadmapId);

        // Add better validation
        if (!roadmap || !roadmap.id || !Array.isArray(roadmap.nodes)) {
          console.error("Invalid roadmap data:", roadmap);
          onError?.();
          return;
        }

        // Transform nodes for ReactFlow
        const flowNodes = roadmap.nodes.map((node) => ({
          id: node.id,
          type: "default",
          position: {
            x: node.order * 200,
            y: 100 + Math.random() * 50,
          },
          data: {
            label: node.title,
            description: node.description,
            content: node.content,
            status: node.status,
          },
        }));

        setNodes(flowNodes);

        // Only set edges if there are nodes
        if (roadmap.nodes.length > 0) {
          const flowEdges = roadmap.nodes.flatMap((node) =>
            (node.prerequisite_ids || []).map((preId) => ({
              id: `e${preId}-${node.id}`,
              source: preId,
              target: node.id,
              type: "smoothstep",
            }))
          );
          setEdges(flowEdges);
        }
      } catch (error) {
        console.error("Error loading roadmap:", error);
        onError?.();
      }
    };

    loadRoadmap();
  }, [roadmapId, initializeRoadmap, onError, setNodes, setEdges]);

  React.useImperativeHandle(ref, () => ({
    resetFlow: initializeRoadmap,
  }));

  if (isLoadingRoadmap) {
    return (
      <div className="w-screen h-screen flex items-center justify-center">
        <div className="text-lg">Loading your roadmap...</div>
      </div>
    );
  }

  if (roadmapError || !nodes.length) {
    return null;
  }

  const handleNodeClick = useCallback((_, node) => {
    console.log("Node clicked:", node);
    setSelectedNode(node);
    setIsDialogOpen(true);
  }, []);

  const handleDialogOpenChange = useCallback((open) => {
    setIsDialogOpen(open);
    if (!open) {
      setSelectedNode(null);
    }
  }, []);

  const nodeTypes = {
    decision: DecisionNode,
    task: TaskNode,
  };

  const childNodes = edges.filter((edge) => edge.source === selectedNode?.id).map((edge) => edge.target);

  const handleGenerateNodes = async (count) => {
    if (!selectedNode?.id) return;

    try {
      setIsGenerating(true);
      await generateNodesFromContext(selectedNode.id, count);

      toast({
        title: "Success",
        description: `Generated ${count} new nodes.`,
      });
    } catch (error) {
      console.error("Failed to generate nodes:", error);
      toast({
        title: "Error",
        description: "Failed to generate nodes.",
        variant: "destructive",
      });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="w-screen h-screen relative">
      <div className="reactflow-wrapper absolute inset-0">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={handleConnect}
          onNodeDragStop={handleNodeDragStop}
          onNodeClick={handleNodeClick}
          nodeTypes={nodeTypes}
          ref={flowRef}
          fitView
        >
          <Background variant="dots" gap={12} size={1} />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>

      <Dialog.Root open={isDialogOpen} onOpenChange={handleDialogOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed top-0 right-0 h-full w-[400px] bg-white shadow-lg transition-all duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right dark:bg-gray-800 p-6">
            {selectedNode && (
              <>
                <div className="flex flex-col space-y-1.5 text-center sm:text-left mb-6">
                  <Dialog.Title className="text-lg font-semibold leading-none tracking-tight">
                    {selectedNode.data?.label || "Node Properties"}
                  </Dialog.Title>
                  <Dialog.Description className="text-sm text-gray-500 dark:text-gray-400">
                    {selectedNode.data?.description || "View and edit node properties"}
                  </Dialog.Description>
                </div>

                <div className="mt-6 space-y-6">
                  <NodeProperties node={selectedNode} />
                  <NodeConnections childNodes={childNodes} />
                  <NodeGenerationForm onGenerate={handleGenerateNodes} isGenerating={isGenerating} />
                </div>

                <Dialog.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
                  <X className="h-4 w-4" />
                  <span className="sr-only">Close</span>
                </Dialog.Close>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
});

RoadmapFlow.displayName = "RoadmapFlow";

export { RoadmapFlow, useRoadmapState, DecisionNode };
export default RoadmapFlow;

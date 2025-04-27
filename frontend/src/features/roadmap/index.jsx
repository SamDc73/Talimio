import { Background, Controls, MiniMap, ReactFlow } from "@xyflow/react";
import { X } from "lucide-react";
import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";

import { DecisionNode } from "./DecisionNode";
import { useOutlineData } from "./useOutlineData";
import Sidebar from "./sidebar";
import { NodeConnections } from "./NodeConnections";
import { NodeGenerationForm } from "./NodeGenerationForm";
import { NodeProperties } from "./NodeProperties";
import { TaskNode } from "./TaskNode";
import { useRoadmapState } from "./useRoadmapState";
import RoadmapHeader from "./RoadmapHeader";
import OutlineView from "./OutlineView";

import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from "@/components/dialog";

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

const RoadmapFlow = ({ roadmapId, onError }) => {
  const { nodes, edges, onNodesChange, onEdgesChange, handleConnect, initializeRoadmap, roadmap } = useRoadmapState();
  const { modules, isLoading } = useOutlineData(roadmapId);

  const [selectedNode, setSelectedNode] = useState(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const initializedRef = useRef(false);
  const [mode, setMode] = useState("visual");

  const styledEdges = useMemo(() => {
    return edges.map((edge) => ({
      ...edge,
      ...edgeOptions,
    }));
  }, [edges]);

  useEffect(() => {
    if (!roadmapId || initializedRef.current) return;

    initializedRef.current = true;
    initializeRoadmap(roadmapId).catch((error) => {
      console.error("Error loading roadmap:", error);
      onError?.();
    });
  }, [roadmapId, initializeRoadmap, onError]);

  const handleNodeClick = useCallback((_, node) => {
    setSelectedNode(node);
    setIsDialogOpen(true);
  }, []);

  const handleDialogOpenChange = useCallback((open) => {
    setIsDialogOpen(open);
    if (!open) {
      setSelectedNode(null);
    }
  }, []);

  const courseName = roadmap?.title || "Learn FastAPI";

  if (isLoading) {
    return (
      <div className="w-screen h-screen flex items-center justify-center">
        <div className="text-lg">Loading your roadmap...</div>
      </div>
    );
  }

  if (!roadmapId || !nodes.length) {
    return null;
  }

  const nodeTypes = {
    decision: DecisionNode,
    task: TaskNode,
  };

  const childNodes = edges.filter((edge) => edge.source === selectedNode?.id).map((edge) => edge.target);
  const getProgress = () => 42;
  const progress = getProgress();

  return (
    <>
      <RoadmapHeader mode={mode} onModeChange={setMode} progress={progress} courseName={courseName} />

      <div className="flex h-[calc(100vh-4rem)]">
        <Sidebar modules={modules || []} onLessonClick={() => {}} />
        {mode === "outline" ? (
          <div className="flex flex-1">
            <OutlineView roadmapId={roadmapId} />
          </div>
        ) : (
          <div className="flex-1 relative">
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
            >
              <Background variant="dots" gap={12} size={1} />
              <Controls />
              <MiniMap
                nodeStrokeWidth={3}
                nodeColor={(node) => {
                  return node.type === "decision" ? "#f59e0b" : "#10b981";
                }}
              />
            </ReactFlow>
          </div>
        )}
      </div>

      <Dialog open={isDialogOpen} onOpenChange={handleDialogOpenChange}>
        <DialogContent className="sm:max-w-[425px]">
          {selectedNode && (
            <>
              <DialogTitle>{selectedNode.data?.label || selectedNode.data?.title || "Node Properties"}</DialogTitle>
              <DialogDescription>{selectedNode.data?.description || "View and edit node properties"}</DialogDescription>

              <div className="mt-6 space-y-6">
                <NodeProperties node={selectedNode} />
                <NodeConnections childNodes={childNodes} />
                <NodeGenerationForm nodeId={selectedNode.id} />
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

RoadmapFlow.displayName = "RoadmapFlow";

export default RoadmapFlow;

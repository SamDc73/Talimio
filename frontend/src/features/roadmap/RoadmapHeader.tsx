import React from "react";
import { LayoutGrid, List, PanelLeft } from "lucide-react";
import { Button } from "@/components/button";

interface RoadmapHeaderProps {
  mode: "visual" | "text";
  onModeChange: (mode: "visual" | "text") => void;
  onCollapseSidebar: () => void;
  title: string;
  sidebarCollapsed: boolean;
}

export const RoadmapHeader: React.FC<RoadmapHeaderProps> = ({
  mode,
  onModeChange,
  onCollapseSidebar,
  title,
  sidebarCollapsed,
}) => {
  return (
    <header className="sticky top-0 z-40 backdrop-blur-md bg-background/80 border-b border-border">
      <div className="container flex items-center justify-between h-16 px-4 mx-auto">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onCollapseSidebar}
            className="p-2 text-muted-foreground rounded-full hover:bg-accent transition-colors"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <PanelLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold bg-gradient-to-r from-emerald-600 to-teal-600 bg-clip-text text-transparent">
            {title}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex gap-1">
            <Button
              type="button"
              variant={mode === "visual" ? "default" : "outline"}
              size="icon"
              onClick={() => onModeChange("visual")}
              aria-label="Visual Layout"
              title="Visual Layout"
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant={mode === "text" ? "default" : "outline"}
              size="icon"
              onClick={() => onModeChange("text")}
              aria-label="Course Layout"
              title="Course Layout"
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
};

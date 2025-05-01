import { FileText, Layout, PanelLeft } from "lucide-react";
import React from "react";
import { useSidebar } from "./SidebarContext";

/**
 * RoadmapHeader component displays the course title, a progress bar, and a toggle button for the sidebar.
 * @param {Object} props
 * @param {string} props.courseName - The name of the course to display in the header.
 * @param {string} props.mode - Current mode ("visual" or "outline")
 * @param {function} props.onModeChange - Function to change mode
 * @param {number} [props.progress] - Optional progress percentage (0-100)
 */
function RoadmapHeader({ courseName, mode, onModeChange, progress = 3 }) {
  // Get sidebar state and toggle function from context
  const { isOpen, toggleSidebar } = useSidebar();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-white/80 border-b border-zinc-200">
      <div className="flex items-center h-16 w-full max-w-[100vw]">
        <div className="ml-4">
          <button
            className="p-2 text-zinc-500 bg-white rounded-md hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all duration-300"
            aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
            type="button"
            onClick={toggleSidebar}
          >
            <PanelLeft className={`w-5 h-5 transition-transform duration-300 ${isOpen ? "" : "rotate-180"}`} />
          </button>
        </div>
        {/* Title and progress bar, spaced apart and flush with edges */}
        <div className="flex flex-1 min-w-0 items-center justify-between ml-2">
          <h1 className="text-xl font-semibold bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent truncate">
            {courseName}
          </h1>
          <div className="flex items-center gap-4 ml-8 pr-12">
            {/* Mode toggle buttons (to the left of progress bar) */}
            <div className="flex items-center gap-2">
              <button
                className={`flex items-center px-2 py-1 rounded-md text-sm font-medium border min-w-[32px] transition-colors ${
                  mode === "visual"
                    ? "bg-emerald-50 text-emerald-600 border-emerald-200 cursor-default"
                    : "text-zinc-400 bg-zinc-100 border-zinc-200 hover:bg-emerald-50 hover:text-emerald-600 hover:border-emerald-200 cursor-pointer"
                }`}
                type="button"
                onClick={() => mode !== "visual" && onModeChange("visual")}
                aria-pressed={mode === "visual"}
                tabIndex={0}
              >
                <Layout className="w-4 h-4 mr-1" /> Visual
              </button>
              <button
                className={`flex items-center px-2 py-1 rounded-md text-sm font-medium border min-w-[32px] transition-colors ${
                  mode === "outline"
                    ? "bg-emerald-50 text-emerald-600 border-emerald-200 cursor-default"
                    : "text-zinc-400 bg-zinc-100 border-zinc-200 hover:bg-emerald-50 hover:text-emerald-600 hover:border-emerald-200 cursor-pointer"
                }`}
                type="button"
                onClick={() => mode !== "outline" && onModeChange("outline")}
                aria-pressed={mode === "outline"}
                tabIndex={0}
              >
                <FileText className="w-4 h-4 mr-1" /> Outline view
              </button>
            </div>
            {/* Progress bar */}
            <div className="flex items-center gap-2">
              <div className="relative w-32 h-2 bg-zinc-200 rounded-full overflow-hidden">
                <div
                  className="absolute top-0 left-0 h-full bg-gradient-to-r from-emerald-400 to-teal-500 rounded-full"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="text-xs font-medium text-zinc-500">{progress}%</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

export default RoadmapHeader;

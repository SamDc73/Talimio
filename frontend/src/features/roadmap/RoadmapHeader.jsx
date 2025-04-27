import React from "react";
import { PanelLeft } from "lucide-react";

/**
 * RoadmapHeader component displays the course title, a progress bar, and a visually accurate collapse button.
 * @param {Object} props
 * @param {string} props.courseName - The name of the course to display in the header.
 */
function RoadmapHeader({ courseName }) {
  // Placeholder progress value
  const progress = 3;

  return (
    <header className="sticky top-0 z-40 backdrop-blur-md bg-white/80 border-b border-zinc-200">
      <div className="flex items-center h-16 w-full">
        <div className="ml-4">
          <button
            className="p-2 text-zinc-500 bg-white rounded-md hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-emerald-200"
            aria-label="Collapse sidebar (placeholder)"
            type="button"
          >
            <PanelLeft className="w-5 h-5" />
          </button>
        </div>
        {/* Title and progress bar, spaced apart and flush with edges */}
        <div className="flex flex-1 min-w-0 items-center justify-between ml-2">
          <h1 className="text-xl font-semibold bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent truncate">
            {courseName}
          </h1>
          <div className="flex items-center gap-2 ml-8 pr-12">
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
    </header>
  );
}

export default RoadmapHeader;

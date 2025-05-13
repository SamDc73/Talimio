import { FileText, Layout, PanelLeft, GitBranch, ChevronLeft, Settings } from "lucide-react";
import { useSidebar } from "./SidebarContext";
import { Link } from "react-router-dom";
import { useProgress } from "../../hooks/useProgress";
import { Progress } from "@/components/progress";

/**
 * Application header component that provides navigation controls
 *
 * Features:
 * - Collapsible sidebar toggle
 * - Course title display with gradient styling
 * - View mode toggle between map and outline representations
 *
 * The header stays fixed at the top and includes a subtle blur effect for better readability
 * when content scrolls underneath.
 *
 * @param {Object} props
 * @param {string} props.courseName - Course title to display in the header
 * @param {string} props.mode - Current view mode ("visual" for map flowchart or "outline" for text)
 * @param {function} props.onModeChange - Callback handler for mode toggle changes
 * @param {string} props.courseId - ID of the current course
 */
function RoadmapHeader({ courseName, mode, onModeChange, courseId }) {
  const { isOpen, toggleSidebar } = useSidebar();
  // Use the progress hook to get real-time course progress updates
  const { courseProgress } = useProgress();

  // Calculate progress percentage, defaulting to 0 if not available
  const progress = courseProgress?.progress_percentage || 0;

  return (
    <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-white/80 border-b border-zinc-200">
      <div className="flex items-center justify-between h-16 w-full max-w-[100vw] px-4">
        {/* Left section */}
        <div className="flex items-center gap-2">
          <button
            className="p-2 text-zinc-500 bg-white rounded-md hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all duration-300"
            aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
            type="button"
            onClick={toggleSidebar}
          >
            <PanelLeft className={`w-5 h-5 transition-transform duration-300 ${isOpen ? "" : "rotate-180"}`} />
          </button>
          <Link
            to="/library"
            className="flex items-center px-3 py-1.5 text-sm text-zinc-600 hover:text-zinc-900 transition-colors"
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            My Library
          </Link>
        </div>
        {/* Middle section - Course title */}
        <div className="flex-1 flex justify-center min-w-0">
          <h1 className="text-xl font-semibold bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent truncate max-w-[500px]">
            {courseName}
          </h1>
        </div>

        {/* Right section */}
        <div className="flex items-center gap-4">
          {/* Progress indicator */}
          <div className="flex items-center gap-2 mr-2">
            <div className="w-32">
              <Progress value={progress} />
            </div>
            <span className="text-sm font-medium text-zinc-600">{progress}%</span>
          </div>
          {/* View mode toggle - switches between map, outline, and track views */}
          <div className="flex items-center gap-2">
              {/* Map view button temporarily hidden
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
                <Layout className="w-4 h-4 mr-1" /> {mode === "visual" ? "Map" : "Map View"}
              </button>
              */}
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
                <FileText className="w-4 h-4 mr-1" /> {mode === "outline" ? "Outline" : "Outline View"}
              </button>
              <button
                className={`flex items-center px-2 py-1 rounded-md text-sm font-medium border min-w-[32px] transition-colors ${
                  mode === "track"
                    ? "bg-emerald-50 text-emerald-600 border-emerald-200 cursor-default"
                    : "text-zinc-400 bg-zinc-100 border-zinc-200 hover:bg-emerald-50 hover:text-emerald-600 hover:border-emerald-200 cursor-pointer"
                }`}
                type="button"
                onClick={() => mode !== "track" && onModeChange("track")}
                aria-pressed={mode === "track"}
                tabIndex={0}
              >
                <GitBranch className="w-4 h-4 mr-1" /> {mode === "track" ? "Track" : "Track View"}
              </button>
            </div>
            {/* Settings button */}
            <button
              type="button"
              className="p-2 text-zinc-500 hover:text-zinc-700 transition-colors"
              aria-label="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
      </div>
    </header>
  );
}

export default RoadmapHeader;

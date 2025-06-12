import { useState } from "react";

import RoadmapHeader from "@/components/header/RoadmapHeader";
import { CourseSidebar } from "@/components/sidebar";
import { ProgressProvider } from "../../hooks/useProgress";
import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore";
// import MapView from "./map";  // Temporarily hidden
import OutlineView from "./outline";
import { useOutlineData } from "./outline/useOutlineData";
import { useRoadmapState } from "./shared/useRoadmapState";
import TrackView from "./track";

/**
 * Main container component for the Roadmap feature
 * Handles switching between map and outline views
 */
const RoadmapFlow = ({ roadmapId, onError }) => {
	const { isLoading: roadmapLoading, roadmap } = useRoadmapState(
		roadmapId,
		onError,
	);
	const { modules, isLoading: modulesLoading } = useOutlineData(roadmapId);
	const isOpen = useAppStore(selectSidebarOpen);
	const [mode, setMode] = useState("outline"); // Default to outline view

	const isLoading = roadmapLoading || modulesLoading;
	const courseName = roadmap?.title || "Learn FastAPI";

	if (isLoading) {
		return (
			<div className="w-screen h-screen flex items-center justify-center">
				<div className="text-lg">Loading your roadmap...</div>
			</div>
		);
	}

	if (!roadmapId) {
		return null;
	}

	return (
		<ProgressProvider courseId={roadmapId}>
			<div
				className={`roadmap-container ${isOpen ? "sidebar-open" : "sidebar-closed"}`}
				style={{ margin: 0, padding: 0 }}
			>
				<RoadmapHeader
					mode={mode}
					onModeChange={setMode}
					courseId={roadmapId}
					courseName={courseName}
				/>

				<div className="flex h-screen">
					<CourseSidebar
						modules={modules || []}
						onLessonClick={() => {}}
						courseId={roadmapId}
					/>
					{/* Conditional rendering of views */}
					{mode === "outline" ? (
						<div className="flex flex-1 main-content transition-all duration-300 ease-in-out">
							<OutlineView roadmapId={roadmapId} />
						</div>
					) : mode === "track" ? (
						<div className="flex flex-1 main-content transition-all duration-300 ease-in-out">
							<TrackView roadmapId={roadmapId} />
						</div>
					) : // Map view temporarily hidden
					null}
				</div>
			</div>
		</ProgressProvider>
	);
};

RoadmapFlow.displayName = "RoadmapFlow";

export default RoadmapFlow;

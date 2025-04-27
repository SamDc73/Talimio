export interface ApiNode {
  id: string | number;
  title: string;
  description?: string | null;
  content?: string | null;
  order: number;
  status?: string | null;
  parent_id?: string | number | null;
  children?: ApiNode[];
  roadmap_id?: string;
}

export interface Lesson {
  id: string | number;
  title: string;
  description?: string | null;
  content?: string | null;
  order: number;
  completed: boolean;
  locked: boolean;
}

export interface Module {
  id: string | number;
  title: string;
  description?: string | null;
  order: number;
  lessons: Lesson[];
  completed: boolean;
  submodules?: Module[];
}

export interface UserProgress {
  completedLessonIds: (string | number)[];
}

import type { Node, Edge, NodeChange, EdgeChange, Connection } from '@xyflow/react';

export interface RoadmapState {
  nodes: Node[];
  edges: Edge[];
  isLoading: boolean;
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  handleConnect: (connection: Connection) => void;
  initializeRoadmap: (roadmapId: string) => Promise<void>;
  rawApiNodes: ApiNode[] | null;
}

export interface ActiveLesson {
  moduleId: string | number;
  lessonId: string | number;
}

export interface SidebarContentProps {
  modules: Module[];
  expandedModule: string | number | null;
  setExpandedModule: (id: string | number | null) => void;
  activeLesson: ActiveLesson | null;
  setActiveLesson: (lesson: ActiveLesson | null) => void;
  isMobile: boolean;
  overallProgress: number;
}

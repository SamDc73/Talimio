export interface ApiNode {
  id: string | number;
  title: string;
  description?: string | null;
  content?: string | null;
  order: number;
  status?: string | null;
  parent_id?: string | number | null;
  children?: ApiNode[]; // for visual tree, but not required for flat list
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
  completedLessonIds?: (string | number)[];
}

// Main function: build nested modules tree from flat ApiNode[]
export function buildModuleTree(
  apiNodes: ApiNode[],
  progressData: UserProgress,
  isLessonLocked: (
    lessonId: string | number,
    moduleId: string | number,
    currentModules: Module[],
    progressData: UserProgress
  ) => boolean,
  setExpandedModule?: (id: string | number | null) => void,
  setActiveLesson?: (lesson: { moduleId: string | number; lessonId: string | number } | null) => void,
): Module[] {
  // Build parent → children map
  const childrenMap: Record<string | number, ApiNode[]> = {};
  apiNodes.forEach(node => {
    if (node.parent_id != null) {
      if (!childrenMap[node.parent_id]) childrenMap[node.parent_id] = [];
      childrenMap[node.parent_id].push(node);
    }
  });

  // Recursively build module tree
  const buildTree = (node: ApiNode): Module => {
    const children = childrenMap[node.id] || [];
    // Lessons: children with no further children
    const lessons: Lesson[] = children
      .filter(child => !(childrenMap[child.id] && childrenMap[child.id].length > 0))
      .sort((a, b) => a.order - b.order)
      .map(child => ({
        id: child.id,
        title: child.title,
        description: child.description,
        content: child.content,
        order: child.order,
        completed: (progressData.completedLessonIds || []).includes(child.id) || child.status === "completed",
        locked: false,
      }));
    // Submodules: children with further children
    const submodules: Module[] = children
      .filter(child => childrenMap[child.id] && childrenMap[child.id].length > 0)
      .sort((a, b) => a.order - b.order)
      .map(buildTree);
    const moduleCompleted = lessons.length > 0 && lessons.every(l => l.completed);
    return {
      id: node.id,
      title: node.title,
      description: node.description,
      order: node.order,
      lessons,
      completed: moduleCompleted,
      submodules: submodules.length > 0 ? submodules : undefined,
    };
  };

  // Top-level modules: parent_id == null
  const topModules = apiNodes.filter(node => node.parent_id == null).sort((a, b) => a.order - b.order);
  let transformed: Module[] = topModules.map(buildTree);

  // Lock logic for lessons (unchanged)
  const recursivelyLockLessons = (modules: Module[]): Module[] =>
    modules.map(mod => ({
      ...mod,
      lessons: mod.lessons.map(les => ({
        ...les,
        locked: isLessonLocked(les.id, mod.id, modules, progressData),
      })),
      submodules: mod.submodules ? recursivelyLockLessons(mod.submodules) : undefined,
    }));
  const lockedModules = recursivelyLockLessons(transformed);

  // Set expanded/active as before (use first incomplete top-level module/lesson)
  if (setExpandedModule) {
    const firstIncompleteModule = lockedModules.find(m => !m.completed);
    setExpandedModule(firstIncompleteModule?.id ?? (lockedModules.length > 0 ? lockedModules[0].id : null));
  }
  if (setActiveLesson) {
    const findFirstIncompleteLesson = (mods: Module[]): { moduleId: string | number; lessonId: string | number } | null => {
      for (const m of mods) {
        const lesson = m.lessons.find(l => !l.completed && !l.locked);
        if (lesson) return { moduleId: m.id, lessonId: lesson.id };
        if (m.submodules) {
          const found = findFirstIncompleteLesson(m.submodules);
          if (found) return found;
        }
      }
      return null;
    };
    const firstIncompleteLesson = findFirstIncompleteLesson(lockedModules);
    if (firstIncompleteLesson) {
      setActiveLesson(firstIncompleteLesson);
    } else if (lockedModules.length > 0 && lockedModules[0].lessons.length > 0 && !lockedModules[0].lessons[0].locked) {
      setActiveLesson({ moduleId: lockedModules[0].id, lessonId: lockedModules[0].lessons[0].id });
    }
  }
  return lockedModules;
}

import { create } from "zustand";
import { createJSONStorage, devtools, persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";
import { syncToAPI } from "../lib/apiSync.js";

/**
 * Unified Course Store - Replaces roadmap/lesson stores
 * 
 * This store manages the new course-module-lesson hierarchy and provides
 * compatibility with the existing roadmap-node structure during transition.
 */

// Default objects to prevent infinite re-renders
const DEFAULT_COURSE_PROGRESS = {
  totalModules: 0,
  completedModules: 0,
  inProgressModules: 0,
  completionPercentage: 0,
  totalLessons: 0,
  completedLessons: 0,
  lastUpdated: null,
};

const _DEFAULT_MODULE_STATUS = {
  status: 'not_started',
  completionPercentage: 0,
  lastUpdated: null,
};

const DEFAULT_LESSON_STATUS = {
  status: 'not_started',
  startedAt: null,
  completedAt: null,
  lastUpdated: null,
};

const useCourseStore = create(
  devtools(
    persist(
      immer((set, get) => ({
        // ========== COURSE DATA ==========
        courses: {
          // Course metadata cache: courseId -> CourseResponse
          metadata: {},
          // Course list cache with pagination info
          list: {
            courses: [],
            total: 0,
            page: 1,
            perPage: 20,
            lastUpdated: null,
          },
          // Current active course
          activeCourseId: null,
          // Last viewed course for restoration
          lastViewedCourseId: null,
        },

        // ========== MODULE DATA ==========
        modules: {
          // Module metadata cache: courseId -> { moduleId -> ModuleResponse }
          metadata: {},
          // Module status tracking: courseId -> { moduleId -> ModuleStatus }
          status: {},
          // Module progress cache: courseId -> { moduleId -> ProgressData }
          progress: {},
          // Currently active module
          activeModuleId: null,
        },

        // ========== LESSON DATA ==========
        lessons: {
          // Lesson metadata cache: moduleId -> { lessonId -> LessonResponse }
          metadata: {},
          // Lesson status tracking: moduleId -> { lessonId -> LessonStatus }
          status: {},
          // Lesson content cache for offline access
          contentCache: {},
          // Currently active lesson
          activeLessonId: null,
        },

        // ========== COURSE PROGRESS ==========
        progress: {
          // Overall course progress: courseId -> CourseProgressResponse
          courses: {},
          // Detailed module progress: courseId -> { moduleId -> ModuleProgress }
          modules: {},
          // Lesson completion tracking: courseId -> { moduleId -> { lessonId -> LessonProgress } }
          lessons: {},
        },

        // ========== COURSE ACTIONS ==========

        /**
         * Set the active course
         */
        setActiveCourse: (courseId) => {
          set((state) => {
            state.courses.activeCourseId = courseId;
            if (courseId) {
              state.courses.lastViewedCourseId = courseId;
            }
          });
        },

        /**
         * Cache course metadata
         */
        setCourseMetadata: (courseId, courseData) => {
          set((state) => {
            state.courses.metadata[courseId] = {
              ...courseData,
              lastUpdated: Date.now(),
            };
          });
        },

        /**
         * Update course list cache
         */
        setCourseList: (coursesData, pagination = {}) => {
          set((state) => {
            state.courses.list = {
              courses: coursesData,
              total: pagination.total || coursesData.length,
              page: pagination.page || 1,
              perPage: pagination.perPage || 20,
              lastUpdated: Date.now(),
            };
          });
        },

        /**
         * Get course metadata with fallback
         */
        getCourse: (courseId) => {
          const course = get().courses.metadata[courseId];
          return course || null;
        },

        // ========== MODULE ACTIONS ==========

        /**
         * Set the active module
         */
        setActiveModule: (moduleId) => {
          set((state) => {
            state.modules.activeModuleId = moduleId;
          });
        },

        /**
         * Cache module metadata for a course
         */
        setModulesMetadata: (courseId, modulesData) => {
          set((state) => {
            if (!state.modules.metadata[courseId]) {
              state.modules.metadata[courseId] = {};
            }
            
            // Convert array to object keyed by module ID
            if (Array.isArray(modulesData)) {
              for (const module of modulesData) {
                state.modules.metadata[courseId][module.id] = {
                  ...module,
                  lastUpdated: Date.now(),
                };
              }
            } else {
              // Single module update
              state.modules.metadata[courseId][modulesData.id] = {
                ...modulesData,
                lastUpdated: Date.now(),
              };
            }
          });
        },

        /**
         * Update module status
         */
        updateModuleStatus: (courseId, moduleId, status, skipSync = false) => {
          set((state) => {
            if (!state.modules.status[courseId]) {
              state.modules.status[courseId] = {};
            }
            state.modules.status[courseId][moduleId] = {
              ...state.modules.status[courseId][moduleId],
              status,
              lastUpdated: Date.now(),
            };
          });

          // Sync to API
          if (!skipSync) {
            syncToAPI("courses", courseId, {
              moduleStatus: { moduleId, status },
            });
          }

          // Recalculate course progress
          get().recalculateCourseProgress(courseId);
        },

        /**
         * Get modules for a course
         */
        getModules: (courseId) => {
          const modules = get().modules.metadata[courseId];
          return modules ? Object.values(modules) : [];
        },

        /**
         * Get specific module
         */
        getModule: (courseId, moduleId) => {
          return get().modules.metadata[courseId]?.[moduleId] || null;
        },

        // ========== LESSON ACTIONS ==========

        /**
         * Set the active lesson
         */
        setActiveLesson: (lessonId) => {
          set((state) => {
            state.lessons.activeLessonId = lessonId;
          });
        },

        /**
         * Cache lesson metadata for a module
         */
        setLessonsMetadata: (moduleId, lessonsData) => {
          set((state) => {
            if (!state.lessons.metadata[moduleId]) {
              state.lessons.metadata[moduleId] = {};
            }
            
            if (Array.isArray(lessonsData)) {
              for (const lesson of lessonsData) {
                state.lessons.metadata[moduleId][lesson.id] = {
                  ...lesson,
                  lastUpdated: Date.now(),
                };
              }
            } else {
              state.lessons.metadata[moduleId][lessonsData.id] = {
                ...lessonsData,
                lastUpdated: Date.now(),
              };
            }
          });
        },

        /**
         * Update lesson status with progress tracking
         */
        updateLessonStatus: (courseId, moduleId, lessonId, status, skipSync = false) => {
          const now = Date.now();
          
          set((state) => {
            // Initialize nested objects if needed
            if (!state.lessons.status[moduleId]) {
              state.lessons.status[moduleId] = {};
            }
            if (!state.progress.lessons[courseId]) {
              state.progress.lessons[courseId] = {};
            }
            if (!state.progress.lessons[courseId][moduleId]) {
              state.progress.lessons[courseId][moduleId] = {};
            }

            const currentStatus = state.lessons.status[moduleId][lessonId] || {};
            
            // Update lesson status
            state.lessons.status[moduleId][lessonId] = {
              ...currentStatus,
              status,
              lastUpdated: now,
              ...(status === 'in_progress' && !currentStatus.startedAt && { startedAt: now }),
              ...(status === 'done' && { completedAt: now }),
            };

            // Update progress tracking
            state.progress.lessons[courseId][moduleId][lessonId] = {
              status,
              lastUpdated: now,
            };
          });

          // Sync to API
          if (!skipSync) {
            syncToAPI("courses", courseId, {
              lessonStatus: { moduleId, lessonId, status },
            });
          }

          // Recalculate module and course progress
          get().recalculateModuleProgress(courseId, moduleId);
          get().recalculateCourseProgress(courseId);
        },

        /**
         * Get lessons for a module
         */
        getLessons: (moduleId) => {
          const lessons = get().lessons.metadata[moduleId];
          return lessons ? Object.values(lessons) : [];
        },

        /**
         * Get specific lesson
         */
        getLesson: (moduleId, lessonId) => {
          return get().lessons.metadata[moduleId]?.[lessonId] || null;
        },

        /**
         * Get lesson status
         */
        getLessonStatus: (moduleId, lessonId) => {
          return get().lessons.status[moduleId]?.[lessonId] || DEFAULT_LESSON_STATUS;
        },

        // ========== PROGRESS CALCULATIONS ==========

        /**
         * Recalculate module progress based on lesson completion
         */
        recalculateModuleProgress: (courseId, moduleId) => {
          const lessons = get().getLessons(moduleId);
          const moduleProgressData = get().progress.lessons[courseId]?.[moduleId] || {};
          
          if (lessons.length === 0) return;

          const completedLessons = Object.values(moduleProgressData).filter(
            lesson => lesson.status === 'done'
          ).length;
          
          const inProgressLessons = Object.values(moduleProgressData).filter(
            lesson => lesson.status === 'in_progress'
          ).length;

          const completionPercentage = Math.round((completedLessons / lessons.length) * 100);
          
          let status = 'not_started';
          if (completedLessons === lessons.length) {
            status = 'completed';
          } else if (completedLessons > 0 || inProgressLessons > 0) {
            status = 'in_progress';
          }

          set((state) => {
            if (!state.progress.modules[courseId]) {
              state.progress.modules[courseId] = {};
            }
            state.progress.modules[courseId][moduleId] = {
              totalLessons: lessons.length,
              completedLessons,
              inProgressLessons,
              completionPercentage,
              status,
              lastUpdated: Date.now(),
            };
          });

          // Update module status in the modules slice as well
          get().updateModuleStatus(courseId, moduleId, status, true); // Skip sync to avoid loop
        },

        /**
         * Recalculate overall course progress
         */
        recalculateCourseProgress: (courseId) => {
          const modules = get().getModules(courseId);
          const moduleProgressData = get().progress.modules[courseId] || {};
          
          if (modules.length === 0) return;

          const completedModules = Object.values(moduleProgressData).filter(
            module => module.status === 'completed'
          ).length;
          
          const inProgressModules = Object.values(moduleProgressData).filter(
            module => module.status === 'in_progress'
          ).length;

          const totalLessons = Object.values(moduleProgressData).reduce(
            (sum, module) => sum + (module.totalLessons || 0), 0
          );
          
          const completedLessons = Object.values(moduleProgressData).reduce(
            (sum, module) => sum + (module.completedLessons || 0), 0
          );

          const completionPercentage = totalLessons > 0 
            ? Math.round((completedLessons / totalLessons) * 100) 
            : 0;

          set((state) => {
            state.progress.courses[courseId] = {
              totalModules: modules.length,
              completedModules,
              inProgressModules,
              completionPercentage,
              totalLessons,
              completedLessons,
              lastUpdated: Date.now(),
            };
          });

          // Emit custom event for components listening to progress changes
          if (typeof window !== "undefined") {
            window.dispatchEvent(
              new CustomEvent("courseProgressUpdate", {
                detail: { courseId, progress: get().progress.courses[courseId] },
              })
            );
          }
        },

        /**
         * Get course progress
         */
        getCourseProgress: (courseId) => {
          return get().progress.courses[courseId] || DEFAULT_COURSE_PROGRESS;
        },

        /**
         * Get module progress
         */
        getModuleProgress: (courseId, moduleId) => {
          return get().progress.modules[courseId]?.[moduleId] || {
            totalLessons: 0,
            completedLessons: 0,
            inProgressLessons: 0,
            completionPercentage: 0,
            status: 'not_started',
            lastUpdated: null,
          };
        },

        // Legacy compatibility methods removed - use course methods directly

        // ========== CACHE MANAGEMENT ==========

        /**
         * Clear cache for a specific course
         */
        clearCourseCache: (courseId) => {
          set((state) => {
            // Clear course metadata
            delete state.courses.metadata[courseId];
            
            // Clear modules for this course
            delete state.modules.metadata[courseId];
            delete state.modules.status[courseId];
            delete state.modules.progress[courseId];
            
            // Clear lessons for modules in this course
            const modules = Object.keys(state.modules.metadata[courseId] || {});
            for (const moduleId of modules) {
              delete state.lessons.metadata[moduleId];
              delete state.lessons.status[moduleId];
            }
            
            // Clear progress data
            delete state.progress.courses[courseId];
            delete state.progress.modules[courseId];
            delete state.progress.lessons[courseId];
          });
        },

        /**
         * Clear all cached data
         */
        clearAllCache: () => {
          set((state) => {
            state.courses.metadata = {};
            state.courses.list = {
              courses: [],
              total: 0,
              page: 1,
              perPage: 20,
              lastUpdated: null,
            };
            state.modules.metadata = {};
            state.modules.status = {};
            state.modules.progress = {};
            state.lessons.metadata = {};
            state.lessons.status = {};
            state.lessons.contentCache = {};
            state.progress.courses = {};
            state.progress.modules = {};
            state.progress.lessons = {};
          });
        },

        /**
         * Initialize course data from API response
         */
        initializeCourseData: (courseId, courseData) => {
          get().setCourseMetadata(courseId, courseData);
          
          if (courseData.modules) {
            get().setModulesMetadata(courseId, courseData.modules);
            
            // Initialize progress for existing modules
            for (const module of courseData.modules) {
              get().recalculateModuleProgress(courseId, module.id);
            }
          }
          
          get().recalculateCourseProgress(courseId);
        },

        // ========== BULK OPERATIONS ==========

        /**
         * Batch update lesson statuses (useful for offline sync)
         */
        batchUpdateLessonStatuses: (updates, skipSync = false) => {
          for (const { courseId, moduleId, lessonId, status } of updates) {
            get().updateLessonStatus(courseId, moduleId, lessonId, status, true);
          }
          
          // Single sync call for all updates
          if (!skipSync) {
            syncToAPI("courses", "batch", { lessonStatusUpdates: updates });
          }
        },

        // ========== SELECTORS & GETTERS ==========

        /**
         * Get active course data
         */
        getActiveCourse: () => {
          const courseId = get().courses.activeCourseId;
          return courseId ? get().getCourse(courseId) : null;
        },

        /**
         * Get all courses from cache
         */
        getAllCourses: () => {
          return get().courses.list.courses;
        },

        /**
         * Check if course data is stale and needs refresh
         */
        isCourseDataStale: (courseId, maxAge = 5 * 60 * 1000) => {
          const course = get().courses.metadata[courseId];
          if (!course || !course.lastUpdated) return true;
          return Date.now() - course.lastUpdated > maxAge;
        },
      })),
      {
        name: "course-store",
        storage: createJSONStorage(() => localStorage),
        partialize: (state) => ({
          courses: state.courses,
          modules: state.modules,
          lessons: state.lessons,
          progress: state.progress,
        }),
      }
    ),
    {
      name: "course-store",
    }
  )
);

// Optimized selectors to prevent unnecessary re-renders
export const selectActiveCourse = (state) => state.getActiveCourse();
export const selectCourseProgress = (courseId) => (state) => state.getCourseProgress(courseId);
export const selectModules = (courseId) => (state) => state.getModules(courseId);
export const selectLessons = (moduleId) => (state) => state.getLessons(moduleId);
export const selectLessonStatus = (moduleId, lessonId) => (state) => 
  state.getLessonStatus(moduleId, lessonId);
export const selectModuleProgress = (courseId, moduleId) => (state) => 
  state.getModuleProgress(courseId, moduleId);

export default useCourseStore;
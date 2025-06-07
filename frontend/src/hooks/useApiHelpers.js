/**
 * Helper hooks for specific API operations in Phase 3
 */

import { useApi } from './useApi';

/**
 * Hook for node operations
 * @param {string} nodeId - The node ID
 */
export function useNodeApi(nodeId = null) {
  const getNode = useApi('/nodes/{nodeId}');
  const updateNode = useApi('/nodes/{nodeId}', { method: 'PATCH' });
  const updateStatus = useApi('/nodes/{nodeId}/status', { method: 'PUT' });

  return {
    // Get node data
    async fetchNode() {
      if (!nodeId) throw new Error('Node ID required');
      return await getNode.execute(null, { pathParams: { nodeId } });
    },

    // Update node
    async updateNode(data) {
      if (!nodeId) throw new Error('Node ID required');
      return await updateNode.execute(data, { pathParams: { nodeId } });
    },

    // Update node status
    async updateStatus(status) {
      if (!nodeId) throw new Error('Node ID required');
      return await updateStatus.execute({ status }, { pathParams: { nodeId } });
    },

    // Loading states
    isLoading: getNode.isLoading || updateNode.isLoading || updateStatus.isLoading,
    error: getNode.error || updateNode.error || updateStatus.error,
  };
}

/**
 * Hook for roadmap nodes operations
 * @param {string} roadmapId - The roadmap ID
 */
export function useRoadmapNodesApi(roadmapId = null) {
  const getRoadmapNodes = useApi('/roadmaps/{roadmapId}/nodes');

  return {
    // Get all nodes for a roadmap
    async fetchNodes() {
      if (!roadmapId) throw new Error('Roadmap ID required');
      return await getRoadmapNodes.execute(null, { pathParams: { roadmapId } });
    },

    // Loading states
    isLoading: getRoadmapNodes.isLoading,
    error: getRoadmapNodes.error,
    data: getRoadmapNodes.data,
  };
}

/**
 * Hook for book chapter operations
 * @param {string} bookId - The book ID
 */
export function useBookChaptersApi(bookId = null) {
  const getChapters = useApi('/books/{bookId}/chapters');
  const getChapter = useApi('/books/{bookId}/chapters/{chapterId}');
  const updateChapterStatus = useApi('/books/{bookId}/chapters/{chapterId}/status', { method: 'PUT' });
  const extractChapters = useApi('/books/{bookId}/extract-chapters', { method: 'POST' });

  return {
    // Get all chapters for a book
    async fetchChapters() {
      if (!bookId) throw new Error('Book ID required');
      return await getChapters.execute(null, { pathParams: { bookId } });
    },

    // Get a specific chapter
    async fetchChapter(chapterId) {
      if (!bookId || !chapterId) throw new Error('Book ID and Chapter ID required');
      return await getChapter.execute(null, { pathParams: { bookId, chapterId } });
    },

    // Update chapter status
    async updateChapterStatus(chapterId, status) {
      if (!bookId || !chapterId) throw new Error('Book ID and Chapter ID required');
      return await updateChapterStatus.execute({ status }, { pathParams: { bookId, chapterId } });
    },

    // Extract chapters from book
    async extractChapters() {
      if (!bookId) throw new Error('Book ID required');
      return await extractChapters.execute(null, { pathParams: { bookId } });
    },

    // Loading states
    isLoading: getChapters.isLoading || getChapter.isLoading || updateChapterStatus.isLoading || extractChapters.isLoading,
    error: getChapters.error || getChapter.error || updateChapterStatus.error || extractChapters.error,
    data: getChapters.data,
  };
}

/**
 * Hook for video chapter operations
 * @param {string} videoUuid - The video UUID
 */
export function useVideoChaptersApi(videoUuid = null) {
  const getChapters = useApi('/videos/{videoUuid}/chapters');
  const getChapter = useApi('/videos/{videoUuid}/chapters/{chapterId}');
  const updateChapterStatus = useApi('/videos/{videoUuid}/chapters/{chapterId}/status', { method: 'PUT' });
  const extractChapters = useApi('/videos/{videoUuid}/extract-chapters', { method: 'POST' });

  return {
    // Get all chapters for a video
    async fetchChapters() {
      if (!videoUuid) throw new Error('Video UUID required');
      return await getChapters.execute(null, { pathParams: { videoUuid } });
    },

    // Get a specific chapter
    async fetchChapter(chapterId) {
      if (!videoUuid || !chapterId) throw new Error('Video UUID and Chapter ID required');
      return await getChapter.execute(null, { pathParams: { videoUuid, chapterId } });
    },

    // Update chapter status
    async updateChapterStatus(chapterId, status) {
      if (!videoUuid || !chapterId) throw new Error('Video UUID and Chapter ID required');
      return await updateChapterStatus.execute({ status }, { pathParams: { videoUuid, chapterId } });
    },

    // Extract chapters from video
    async extractChapters() {
      if (!videoUuid) throw new Error('Video UUID required');
      return await extractChapters.execute(null, { pathParams: { videoUuid } });
    },

    // Loading states
    isLoading: getChapters.isLoading || getChapter.isLoading || updateChapterStatus.isLoading || extractChapters.isLoading,
    error: getChapters.error || getChapter.error || updateChapterStatus.error || extractChapters.error,
    data: getChapters.data,
  };
}

/**
 * Hook for course operations (UI convenience layer)
 * @param {string} courseId - The course ID (roadmap ID)
 */
export function useCourseApi(courseId = null) {
  const getCourses = useApi('/courses');
  const getCourse = useApi('/courses/{id}');
  const getCurriculum = useApi('/courses/{id}/curriculum');
  const getLesson = useApi('/courses/{id}/lesson/{nodeId}');

  return {
    // Get all courses
    async fetchCourses() {
      return await getCourses.execute();
    },

    // Get course details
    async fetchCourse() {
      if (!courseId) throw new Error('Course ID required');
      return await getCourse.execute(null, { pathParams: { id: courseId } });
    },

    // Get course curriculum
    async fetchCurriculum() {
      if (!courseId) throw new Error('Course ID required');
      return await getCurriculum.execute(null, { pathParams: { id: courseId } });
    },

    // Get lesson for a node
    async fetchLesson(nodeId) {
      if (!courseId || !nodeId) throw new Error('Course ID and Node ID required');
      return await getLesson.execute(null, { pathParams: { id: courseId, nodeId } });
    },

    // Loading states
    isLoading: getCourses.isLoading || getCourse.isLoading || getCurriculum.isLoading || getLesson.isLoading,
    error: getCourses.error || getCourse.error || getCurriculum.error || getLesson.error,
  };
}
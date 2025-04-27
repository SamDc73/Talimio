// OutlineItem.jsx
// Renders a single module card with its lessons (and sub-lessons if present)
// Type hints are in comments for clarity

import React, { useState } from 'react';

/**
 * @param {Object} props
 * @param {Object} props.module - The module object (with lessons)
 * @param {number} props.index - The module index (for numbering)
 * @param {Function} [props.onLessonClick] - Optional handler for lesson click
 * @returns {JSX.Element}
 */
function OutlineItem({ module, index, onLessonClick }) {
  const [expanded, setExpanded] = useState(false);

  // Calculate completed lessons (including nested ones)
  const countLessons = (items) => {
    let total = items.length;
    let completed = items.filter(l => l.status === 'completed').length;

    // Count nested lessons
    items.forEach(item => {
      if (item.lessons && item.lessons.length > 0) {
        const [subTotal, subCompleted] = countLessons(item.lessons);
        total += subTotal;
        completed += subCompleted;
      }
    });

    return [total, completed];
  };

  const [totalLessons, completedLessons] = countLessons(module.lessons);
  const progress = totalLessons > 0 ? (completedLessons / totalLessons) * 100 : 0;

  // Helper to render lessons recursively (for sub-lessons)
  const renderLessons = (lessons, depth = 0, parentIndex = '') => (
    <div className={`space-y-3 ${depth > 0 ? 'ml-6 mt-3 border-l-2 border-emerald-100 pl-4' : ''}`}>
      {lessons.map((lesson, idx) => (
        <div key={lesson.id}>
          <div
            className={`flex items-center justify-between p-4 transition-all border rounded-lg
              ${lesson.status === 'completed'
                ? 'bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-100'
                : 'bg-white border-zinc-200 hover:border-emerald-200 hover:bg-emerald-50/30'}`}
          >
            <div className="flex items-center gap-3 flex-1">
              {/* Lesson number circle */}
              <div className={`flex items-center justify-center w-5 h-5 rounded-full text-xs font-medium
                ${lesson.status === 'completed'
                  ? 'bg-emerald-500 text-white'
                  : 'bg-zinc-100 text-zinc-700'}`}
              >
                {parentIndex ? `${parentIndex}.${idx + 1}` : idx + 1}
              </div>
              <div className="flex flex-col">
                <span className="font-medium">{lesson.title}</span>
                {lesson.description && (
                  <span className="text-sm text-zinc-500">{lesson.description}</span>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => onLessonClick?.(index, idx)}
              className={`flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors
                ${lesson.status === 'completed'
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600'
                  : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'}`}
            >
              {lesson.status === 'completed' ? 'Review' : 'Start'}
            </button>
          </div>
          {/* Render nested lessons if any */}
          {lesson.lessons && lesson.lessons.length > 0 && (
            renderLessons(
              lesson.lessons,
              depth + 1,
              parentIndex ? `${parentIndex}.${idx + 1}` : `${idx + 1}`
            )
          )}
        </div>
      ))}
    </div>
  );

  return (
    <div className="p-6 mb-8 bg-white border border-zinc-200 rounded-xl shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
      {/* Module Title Section */}
      <div className="mb-6 flex items-center gap-2 select-none">
        <button
          type="button"
          className="text-xl font-semibold text-zinc-900 flex items-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-400"
          onClick={() => setExpanded(e => !e)}
          onKeyDown={e => {
            if (e.key === 'Enter' || e.key === ' ') setExpanded(val => !val);
          }}
          tabIndex={0}
          aria-expanded={expanded}
          aria-label={expanded ? 'Collapse module' : 'Expand module'}
          title={expanded ? 'Collapse module' : 'Expand module'}
        >
          {/* Expand/Collapse Icon */}
          <span
            className={`transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
            style={{ display: 'inline-flex', alignItems: 'center' }}
          >
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" role="img" aria-label="Expand/collapse indicator">
              <path d="M7 7L10 10L13 7" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </span>
          {/* Module number circle */}
          <div className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium transition-all duration-300
            ${completedLessons === totalLessons && totalLessons > 0
              ? 'bg-emerald-500 text-white'
              : 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white'}`}
          >
            {completedLessons === totalLessons && totalLessons > 0 ? <span title="Completed">&#10003;</span> : index + 1}
          </div>
          <span>{module.title}</span>
          {/* Completed badge */}
          {completedLessons === totalLessons && totalLessons > 0 && (
            <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-800 rounded-full">
              Completed
            </span>
          )}
        </button>
      </div>
      {/* Progress Bar Section */}
      <div className="flex items-center gap-2 mt-2 mb-4">
        <div className="text-xs text-zinc-500">
          {completedLessons} of {totalLessons} lessons completed
        </div>
        <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 rounded-full"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      {/* Lessons List (collapsible) */}
      {expanded && renderLessons(module.lessons, 0, (index + 1).toString())}
    </div>
  );
}

export default OutlineItem;

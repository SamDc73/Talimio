import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

export function CollapsibleDescription({ description }) {
  const [isCollapsed, setIsCollapsed] = useState(true);

  if (!description) {
    return null;
  }

  return (
    <div className="video-description-container">
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="collapse-button"
      >
        {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
        <span className="description-title">Description</span>
      </button>
      {!isCollapsed && (
        <div className="video-description-content">
          <p>{description}</p>
        </div>
      )}
    </div>
  );
}

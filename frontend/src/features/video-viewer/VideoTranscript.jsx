import { useCallback, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';

import { videoApi } from '@/services/videoApi';
import './VideoTranscript.css';

const VideoTranscript = ({ videoUuid, currentTime, onSeek }) => {
  const [transcript, setTranscript] = useState({ segments: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeCueIndex, setActiveCueIndex] = useState(-1);
  const transcriptRef = useRef(null);
  const activeLineRef = useRef(null);

  // Fetch transcript when component mounts
  useEffect(() => {
    const loadTranscript = async () => {
      if (!videoUuid) return;
      
      setLoading(true);
      setError(null);
      
      try {
        const data = await videoApi.fetchTranscript(videoUuid);
        setTranscript(data);
      } catch (err) {
        console.error('Failed to load transcript:', err);
        setError('Failed to load transcript');
      } finally {
        setLoading(false);
      }
    };

    loadTranscript();
  }, [videoUuid]);

  // Find active segment using simple linear search (more reliable for transcript data)
  const findActiveSegment = useCallback((time, segments) => {
    if (!segments || segments.length === 0) return -1;
    
    // Find the last segment that has started
    let activeIndex = -1;
    for (let i = 0; i < segments.length; i++) {
      if (time >= segments[i].startTime) {
        // Check if we're still within this segment
        if (time <= segments[i].endTime) {
          return i;
        }
        // Keep track of the last segment we've passed
        activeIndex = i;
      } else {
        // We've gone past the current time, break
        break;
      }
    }
    
    // Return the last segment that started, or -1 if none
    return activeIndex;
  }, []);

  // Update active cue based on current time
  useEffect(() => {
    if (!transcript.segments || transcript.segments.length === 0) return;
    
    // Find active segment
    const segmentIndex = findActiveSegment(currentTime, transcript.segments);
    
    // Update active cue index
    setActiveCueIndex(segmentIndex);
  }, [currentTime, transcript.segments, findActiveSegment]);


  // Auto-scroll to active line
  useEffect(() => {
    if (activeCueIndex >= 0 && activeLineRef.current && transcriptRef.current) {
      const container = transcriptRef.current;
      const activeLine = activeLineRef.current;
      
      
      // Calculate scroll position to center the active line
      const containerHeight = container.clientHeight;
      const lineTop = activeLine.offsetTop;
      const lineHeight = activeLine.offsetHeight;
      const scrollTo = lineTop - (containerHeight / 2) + (lineHeight / 2);
      
      container.scrollTo({
        top: scrollTo,
        behavior: 'smooth'
      });
    }
  }, [activeCueIndex]);

  const handleLineClick = (startTime) => {
    console.log('Transcript line clicked, seeking to:', startTime);
    if (onSeek) {
      onSeek(startTime);
    }
  };

  const formatTime = (seconds, includeHours = false) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (includeHours || hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="video-transcript loading">
        <div className="transcript-loader">Loading transcript...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="video-transcript error">
        <div className="transcript-error">{error}</div>
      </div>
    );
  }

  if (!transcript.segments || transcript.segments.length === 0) {
    return (
      <div className="video-transcript empty">
        <div className="transcript-empty">No transcript available for this video</div>
      </div>
    );
  }

  
  return (
    <div className="video-transcript" ref={transcriptRef}>
      <div className="transcript-header">
        <h3>Transcript</h3>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          {/* Time Display - now shows real YouTube player time */}
          <span style={{ 
            fontSize: '18px', 
            fontWeight: 'bold', 
            fontFamily: 'monospace',
            color: 'hsl(var(--primary))'
          }}>
            {formatTime(currentTime, true)}
          </span>
          <span className="transcript-count">{transcript.totalSegments} segments</span>
        </div>
      </div>
      <div className="transcript-content">
        {transcript.segments.map((segment, index) => {
          const isActive = index === activeCueIndex;
          
          // Style for active segment
          const activeStyle = {
            backgroundColor: 'rgba(34, 197, 94, 0.15)', // Subtle green background
            borderLeft: '4px solid rgb(34, 197, 94)', // Green accent border
            padding: '12px 20px',
            transition: 'all 0.3s ease',
            transform: 'translateX(4px)'
          };
          
          const inactiveStyle = {
            backgroundColor: 'transparent',
            borderLeft: '4px solid transparent',
            padding: '12px 20px',
            transform: 'translateX(0)',
            transition: 'all 0.3s ease'
          };
          
          // Let's wrap in a div to test if button styles are the issue
          return (
            <div
              key={`${segment.startTime}-${segment.endTime}`}
              ref={isActive ? activeLineRef : null}
              className="transcript-line-wrapper"
              style={isActive ? activeStyle : inactiveStyle}
            >
              <button
                className={`transcript-line ${isActive ? 'active' : ''}`}
                onClick={() => handleLineClick(segment.startTime)}
                type="button"
                aria-label={`Jump to ${formatTime(segment.startTime)}`}
                data-active={isActive ? "true" : "false"}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '0'
                }}
              >
                <span className="transcript-time">{formatTime(segment.startTime)}</span>
                <span className="transcript-text">{segment.text}</span>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

VideoTranscript.propTypes = {
  videoUuid: PropTypes.string.isRequired,
  currentTime: PropTypes.number.isRequired,
  onSeek: PropTypes.func.isRequired,
};

export default VideoTranscript;
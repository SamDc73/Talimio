import { useEffect, useCallback } from 'react';
import { useTextSelection } from '@/components/ui/GlobalTextSelectionTooltip';

export const useTextSelectionTooltip = (onHighlight, onAskAI) => {
  const { setSelectionHandlers } = useTextSelection();

  // Memoize the handlers to prevent infinite loops
  const memoizedOnHighlight = useCallback(onHighlight, []);
  const memoizedOnAskAI = useCallback(onAskAI, []);

  useEffect(() => {
    setSelectionHandlers(memoizedOnHighlight, memoizedOnAskAI);
    
    return () => {
      // Clear handlers when component unmounts
      setSelectionHandlers(null, null);
    };
  }, [memoizedOnHighlight, memoizedOnAskAI, setSelectionHandlers]);
};
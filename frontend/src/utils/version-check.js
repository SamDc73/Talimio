import React from 'react';

// Version compatibility check
const checkReactVersion = () => {
  const reactVersion = React.version;
  console.log(`[Debug] React version: ${reactVersion}`);

  // Check for React 19
  if (reactVersion.startsWith('19')) {
    console.log('[Debug] Using React 19 - Experimental Features Enabled');

    // Log which experimental features are available
    const experimentalFeatures = Object.keys(React).filter(key => key.startsWith('experimental') || key.startsWith('use'));
    console.log('[Debug] Available experimental features:', experimentalFeatures);

    // Check for specific APIs we're using
    const requiredAPIs = ['createRoot', 'Fragment', 'forwardRef'];
    const missingAPIs = requiredAPIs.filter(api => !React[api]);

    if (missingAPIs.length > 0) {
      console.warn('[Warning] Missing required React APIs:', missingAPIs);
    }
  }
};

// Check Radix UI component availability
const checkRadixComponents = async () => {
  try {
    const tooltipModule = await import('@radix-ui/react-tooltip');
    console.log('[Debug] Tooltip component loaded:', !!tooltipModule.TooltipProvider);

    const radioGroupModule = await import('@radix-ui/react-radio-group');
    console.log('[Debug] RadioGroup component loaded:', !!radioGroupModule.Root);

    const separatorModule = await import('@radix-ui/react-separator');
    console.log('[Debug] Separator component loaded:', !!separatorModule.Root);

    return true;
  } catch (error) {
    console.error('[Error] Failed to load Radix UI components:', error);
    return false;
  }
};

export { checkReactVersion, checkRadixComponents };

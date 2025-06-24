/**
 * DocumentStatusBadge Component
 * 
 * Displays the processing status of documents with appropriate colors and icons:
 * - pending: Gray with clock icon
 * - processing: Blue with spinner
 * - embedded/ready: Green with check icon
 * - failed: Red with error icon
 * 
 * Supports hover tooltips and different sizes.
 */

import { Clock, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

const DocumentStatusBadge = ({ 
  status, 
  size = 'default', 
  showIcon = true, 
  showText = true,
  className = '' 
}) => {
  // Status configuration
  const statusConfig = {
    pending: {
      label: 'Pending',
      color: 'bg-gray-100 text-gray-700 border-gray-200',
      icon: Clock,
      description: 'Document is queued for processing'
    },
    processing: {
      label: 'Processing',
      color: 'bg-blue-100 text-blue-700 border-blue-200',
      icon: Loader2,
      description: 'Document is being processed and chunked',
      animated: true
    },
    embedded: {
      label: 'Ready',
      color: 'bg-green-100 text-green-700 border-green-200',
      icon: CheckCircle2,
      description: 'Document is ready and searchable'
    },
    failed: {
      label: 'Failed',
      color: 'bg-red-100 text-red-700 border-red-200',
      icon: AlertCircle,
      description: 'Document processing failed'
    }
  };

  // Size configurations
  const sizeConfig = {
    sm: {
      container: 'px-2 py-1 text-xs',
      icon: 'w-3 h-3',
      gap: 'gap-1'
    },
    default: {
      container: 'px-2.5 py-1.5 text-sm',
      icon: 'w-4 h-4',
      gap: 'gap-1.5'
    },
    lg: {
      container: 'px-3 py-2 text-base',
      icon: 'w-5 h-5',
      gap: 'gap-2'
    }
  };

  const config = statusConfig[status] || statusConfig.pending;
  const sizes = sizeConfig[size];
  const Icon = config.icon;

  return (
    <span
      className={`
        inline-flex items-center rounded-full border font-medium
        ${config.color}
        ${sizes.container}
        ${sizes.gap}
        ${className}
      `}
      title={config.description}
    >
      {showIcon && (
        <Icon
          className={`
            ${sizes.icon}
            ${config.animated ? 'animate-spin' : ''}
          `}
        />
      )}
      {showText && config.label}
    </span>
  );
};

/**
 * DocumentStatusIndicator - Minimalist version for tight spaces
 */
export const DocumentStatusIndicator = ({ status, className = '' }) => {
  const statusConfig = {
    pending: 'bg-gray-400',
    processing: 'bg-blue-500 animate-pulse',
    embedded: 'bg-green-500',
    failed: 'bg-red-500'
  };

  const color = statusConfig[status] || statusConfig.pending;

  return (
    <div
      className={`w-2 h-2 rounded-full ${color} ${className}`}
      title={status}
    />
  );
};

/**
 * DocumentStatusProgress - Progress bar version for processing states
 */
export const DocumentStatusProgress = ({ 
  status, 
  progress = null, 
  className = '' 
}) => {
  const isProcessing = status === 'processing';
  const progressValue = progress !== null ? progress : (isProcessing ? 50 : 0);

  return (
    <div className={`space-y-1 ${className}`}>
      <div className="flex items-center justify-between text-sm">
        <DocumentStatusBadge status={status} size="sm" />
        {isProcessing && progress !== null && (
          <span className="text-xs text-gray-500">{progress}%</span>
        )}
      </div>
      
      {(isProcessing || status === 'embedded') && (
        <div className="w-full bg-gray-200 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full transition-all duration-300 ${
              status === 'embedded' 
                ? 'bg-green-500' 
                : 'bg-blue-500'
            } ${isProcessing && progress === null ? 'animate-pulse' : ''}`}
            style={{ 
              width: status === 'embedded' ? '100%' : `${progressValue}%` 
            }}
          />
        </div>
      )}
    </div>
  );
};

/**
 * Utility function to get status display text
 */
export const getStatusText = (status) => {
  const statusConfig = {
    pending: 'Pending',
    processing: 'Processing',
    embedded: 'Ready',
    failed: 'Failed'
  };
  
  return statusConfig[status] || 'Unknown';
};

/**
 * Utility function to check if document is ready
 */
export const isDocumentReady = (document) => {
  return document?.status === 'embedded';
};

/**
 * Utility function to check if document is processing
 */
export const isDocumentProcessing = (document) => {
  return document?.status === 'processing' || document?.status === 'pending';
};

/**
 * Utility function to check if document failed
 */
export const isDocumentFailed = (document) => {
  return document?.status === 'failed';
};

/**
 * DocumentStatusSummary - Shows aggregated status for multiple documents
 */
export const DocumentStatusSummary = ({ documents, className = '' }) => {
  const counts = documents.reduce((acc, doc) => {
    acc[doc.status] = (acc[doc.status] || 0) + 1;
    return acc;
  }, {});

  const total = documents.length;
  const ready = counts.embedded || 0;
  const processing = (counts.processing || 0) + (counts.pending || 0);
  const failed = counts.failed || 0;

  if (total === 0) {
    return (
      <div className={`text-sm text-gray-500 ${className}`}>
        No documents
      </div>
    );
  }

  return (
    <div className={`flex items-center space-x-2 text-sm ${className}`}>
      <span className="font-medium">{total} document{total !== 1 ? 's' : ''}</span>
      <span className="text-gray-400">•</span>
      
      {ready > 0 && (
        <>
          <span className="text-green-600">{ready} ready</span>
          {(processing > 0 || failed > 0) && <span className="text-gray-400">•</span>}
        </>
      )}
      
      {processing > 0 && (
        <>
          <span className="text-blue-600">{processing} processing</span>
          {failed > 0 && <span className="text-gray-400">•</span>}
        </>
      )}
      
      {failed > 0 && (
        <span className="text-red-600">{failed} failed</span>
      )}
    </div>
  );
};

export default DocumentStatusBadge;
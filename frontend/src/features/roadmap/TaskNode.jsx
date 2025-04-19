import { Handle, Position } from '@xyflow/react';
import React from 'react';

export const TaskNode = ({ data }) => {
  return (
    <div className="px-4 py-3 shadow-lg rounded-full bg-white border-2 border-emerald-500 hover:border-emerald-600 transition-colors w-[220px] h-[80px] flex items-center justify-center">
      <Handle type="target" position={Position.Top} className="!bg-emerald-500 w-2 h-10" />
      <div className="text-center">
        <div className="font-medium text-gray-800">{data.label}</div>
        {data.description && (
          <div className="text-xs text-gray-500 mt-1 max-w-[200px] truncate">{data.description}</div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-emerald-500 w-2 h-10" />
    </div>
  );
};

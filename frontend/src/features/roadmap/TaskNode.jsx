import React from 'react';
import { Handle, Position } from '@xyflow/react';

export const TaskNode = ({ data }) => {
  return (
    <div className="px-4 py-2 shadow-lg rounded-md bg-white border-2 border-gray-200">
      <Handle type="target" position={Position.Top} />
      <div className="font-medium">{data.label}</div>
      {data.description && (
        <div className="text-sm text-gray-500">{data.description}</div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

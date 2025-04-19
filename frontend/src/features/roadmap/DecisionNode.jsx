import { Handle, Position } from "@xyflow/react";
import React from "react";

export const DecisionNode = ({ data }) => {
  return (
    <div className="px-4 py-3 shadow-lg rounded-full bg-amber-100 border-2 border-amber-500 hover:border-amber-600 transition-colors w-[220px] h-[80px] flex items-center justify-center">
      <Handle type="target" position={Position.Top} className="w-2 h-10 !bg-amber-500" />
      <div className="text-center">
        <div className="text-base font-bold text-amber-800">{data.title || data.label}</div>
        {data.description && (
          <div className="text-xs text-amber-700 mt-1 max-w-[200px] truncate">{data.description}</div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="w-2 h-10 !bg-amber-500" />
    </div>
  );
};

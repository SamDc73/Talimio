import { Handle, Position } from "@xyflow/react";
import React from "react";

export const DecisionNode = ({ data }) => {
  return (
    <div className="px-4 py-2 shadow-md rounded-md bg-white border-2 border-stone-400 dark:bg-gray-800 dark:border-gray-600">
      <Handle type="target" position={Position.Top} className="w-16 !bg-teal-500" />
      <div className="flex">
        <div className="ml-2">
          <div className="text-lg font-bold">{data.title}</div>
          <div className="text-gray-500 dark:text-gray-400">{data.description}</div>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-16 !bg-teal-500" />
    </div>
  );
};

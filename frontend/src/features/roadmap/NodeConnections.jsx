import { ArrowRight } from "lucide-react";

export const NodeConnections = ({ childNodes = [] }) => {
  if (!childNodes || childNodes.length === 0) {
    return null;
  }

  return (
    <div className="border rounded-lg p-4">
      <h4 className="text-sm font-medium leading-none mb-3">Connected Nodes</h4>
      <div className="space-y-2">
        {childNodes.map(nodeId => (
          <div key={nodeId} className="flex items-center text-sm">
            <ArrowRight className="h-4 w-4 mr-2" />
            <span>{nodeId}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

import { format } from "date-fns";
import { Box, Calendar, Tag } from "lucide-react";

export const NodeProperties = ({ node }) => {
  if (!node?.data) return null;

  return (
    <div className="border rounded-lg p-4">
      <h4 className="text-sm font-medium leading-none mb-3">Properties</h4>
      <div className="space-y-2">
        <div className="flex items-center text-sm">
          <Box className="h-4 w-4 mr-2" />
          <span className="text-muted-foreground">Type:</span>
          <span className="ml-2">{node.data.metadata?.type || "default"}</span>
        </div>
        <div className="flex items-center text-sm">
          <Tag className="h-4 w-4 mr-2" />
          <span className="text-muted-foreground">Category:</span>
          <span className="ml-2">{node.data.metadata?.category || "none"}</span>
        </div>
        {node.data.metadata?.generation && (
          <>
            <div className="flex items-center text-sm">
              <span className="text-muted-foreground">Prompt:</span>
              <span className="ml-2">{node.data.metadata.generation.prompt}</span>
            </div>
            <div className="flex items-center text-sm">
              <span className="text-muted-foreground">Sequence:</span>
              <span className="ml-2">{node.data.metadata.generation.sequence}</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

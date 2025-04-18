/**
 * @typedef {Object} RoadmapNode
 * @property {string} id
 * @property {string} title
 * @property {string} [parent_id]
 * @property {RoadmapNode[]} [children]
 * @property {string} [type]
 * @property {any} [data]
 */

/**
 * @typedef {Object} ReactFlowNode
 * @property {string} id
 * @property {string} type
 * @property {{ x: number, y: number }} position
 * @property {any} data
 */

/**
 * @typedef {Object} ReactFlowEdge
 * @property {string} id
 * @property {string} source
 * @property {string} target
 * @property {string} type
 */

/**
 * Compute a layout where root nodes are centered vertically, children branch left/right.
 * @param {RoadmapNode[]} apiNodes
 * @returns {{ nodes: ReactFlowNode[], edges: ReactFlowEdge[] }}
 */
export function getCenteredBranchingLayout(apiNodes) {
  // Layout constants
  const CENTER_X = 500; // px
  const ROOT_Y_START = 100;
  const ROOT_Y_GAP = 180;
  const CHILD_X_OFFSET = 260;
  const CHILD_Y_GAP = 90;

  /** @type {ReactFlowNode[]} */
  const flowNodes = [];
  /** @type {ReactFlowEdge[]} */
  const flowEdges = [];

  // 1. Find all root nodes (no parent_id)
  const roots = apiNodes.filter(n => !n.parent_id);

  roots.forEach((root, rootIdx) => {
    // Center root node
    const rootY = ROOT_Y_START + rootIdx * ROOT_Y_GAP;
    flowNodes.push({
      id: root.id,
      type: root.type || 'decision',
      position: { x: CENTER_X, y: rootY },
      data: { label: root.title, ...root }
    });

    // Children: alternate left/right
    const children = root.children || [];
    children.forEach((child, childIdx) => {
      const isLeft = childIdx % 2 === 0;
      const childX = CENTER_X + (isLeft ? -CHILD_X_OFFSET : CHILD_X_OFFSET);
      const childY = rootY + (childIdx - (children.length-1)/2) * CHILD_Y_GAP;
      flowNodes.push({
        id: child.id,
        type: child.type || 'task',
        position: { x: childX, y: childY },
        data: { label: child.title, ...child }
      });
      flowEdges.push({
        id: `e${root.id}-${child.id}`,
        source: root.id,
        target: child.id,
        type: 'smoothstep'
      });
      // Optionally handle grandchildren (one more level)
      if (child.children && child.children.length > 0) {
        child.children.forEach((grand, grandIdx) => {
          const grandX = childX + (isLeft ? -CHILD_X_OFFSET : CHILD_X_OFFSET);
          const grandY = childY + (grandIdx - (child.children.length-1)/2) * (CHILD_Y_GAP * 0.7);
          flowNodes.push({
            id: grand.id,
            type: grand.type || 'task',
            position: { x: grandX, y: grandY },
            data: { label: grand.title, ...grand }
          });
          flowEdges.push({
            id: `e${child.id}-${grand.id}`,
            source: child.id,
            target: grand.id,
            type: 'smoothstep'
          });
        });
      }
    });
  });

  return { nodes: flowNodes, edges: flowEdges };
}

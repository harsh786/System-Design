import java.util.*;
/**
 * Problem 36: All Nodes Distance K in Binary Tree (LeetCode 863)
 * 
 * Approach: Build parent map via DFS, then BFS from target node k levels.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding all services within k hops of a failing node for blast radius analysis.
 */
public class Problem36_AllNodesDistanceK {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<Integer> distanceK(TreeNode root, TreeNode target, int k) {
        Map<TreeNode, TreeNode> parentMap = new HashMap<>();
        buildParentMap(root, null, parentMap);
        
        Queue<TreeNode> queue = new LinkedList<>();
        Set<TreeNode> visited = new HashSet<>();
        queue.offer(target);
        visited.add(target);
        int dist = 0;
        while (!queue.isEmpty()) {
            if (dist == k) {
                List<Integer> result = new ArrayList<>();
                for (TreeNode n : queue) result.add(n.val);
                return result;
            }
            int size = queue.size();
            for (int i = 0; i < size; i++) {
                TreeNode node = queue.poll();
                for (TreeNode next : new TreeNode[]{node.left, node.right, parentMap.get(node)}) {
                    if (next != null && !visited.contains(next)) {
                        visited.add(next);
                        queue.offer(next);
                    }
                }
            }
            dist++;
        }
        return new ArrayList<>();
    }

    private static void buildParentMap(TreeNode node, TreeNode parent, Map<TreeNode, TreeNode> map) {
        if (node == null) return;
        map.put(node, parent);
        buildParentMap(node.left, node, map);
        buildParentMap(node.right, node, map);
    }

    public static void main(String[] args) {
        TreeNode n5 = new TreeNode(5, new TreeNode(6), new TreeNode(2, new TreeNode(7), new TreeNode(4)));
        TreeNode root = new TreeNode(3, n5, new TreeNode(1, new TreeNode(0), new TreeNode(8)));
        System.out.println("Test 1 (k=2): " + distanceK(root, n5, 2)); // [7,4,1]
        System.out.println("Test 2 (k=0): " + distanceK(root, n5, 0)); // [5]
    }
}

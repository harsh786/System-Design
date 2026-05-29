import java.util.*;

public class Problem37_AllNodesDistanceKInBinaryTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static List<Integer> distanceK(TreeNode root, TreeNode target, int k) {
        Map<TreeNode, TreeNode> parent = new HashMap<>();
        buildParent(root, null, parent);
        Queue<TreeNode> q = new LinkedList<>();
        Set<TreeNode> visited = new HashSet<>();
        q.offer(target); visited.add(target);
        int dist = 0;
        while (!q.isEmpty()) {
            if (dist == k) { List<Integer> res = new ArrayList<>(); for (TreeNode n : q) res.add(n.val); return res; }
            dist++;
            for (int sz = q.size(); sz > 0; sz--) {
                TreeNode n = q.poll();
                for (TreeNode next : new TreeNode[]{n.left, n.right, parent.get(n)}) {
                    if (next != null && visited.add(next)) q.offer(next);
                }
            }
        }
        return new ArrayList<>();
    }
    static void buildParent(TreeNode node, TreeNode par, Map<TreeNode, TreeNode> map) {
        if (node == null) return;
        map.put(node, par);
        buildParent(node.left, node, map); buildParent(node.right, node, map);
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(5); root.right = new TreeNode(1);
        root.left.left = new TreeNode(6); root.left.right = new TreeNode(2);
        root.left.right.left = new TreeNode(7); root.left.right.right = new TreeNode(4);
        System.out.println(distanceK(root, root.left, 2)); // [7,4,1]
    }
}

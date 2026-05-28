import java.util.*;
/**
 * Problem 27: Vertical Order Traversal of a Binary Tree (LeetCode 987)
 * 
 * Approach: BFS/DFS tracking (col, row, val). Sort by col, then row, then val.
 * Use TreeMap<col, PriorityQueue<(row, val)>>.
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: Organizing microservices by vertical business domain for team ownership mapping.
 */
public class Problem27_VerticalOrderTraversal {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<List<Integer>> verticalTraversal(TreeNode root) {
        TreeMap<Integer, List<int[]>> map = new TreeMap<>(); // col -> list of (row, val)
        dfs(root, 0, 0, map);
        List<List<Integer>> result = new ArrayList<>();
        for (List<int[]> entries : map.values()) {
            entries.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
            List<Integer> col = new ArrayList<>();
            for (int[] e : entries) col.add(e[1]);
            result.add(col);
        }
        return result;
    }

    private static void dfs(TreeNode node, int row, int col, TreeMap<Integer, List<int[]>> map) {
        if (node == null) return;
        map.computeIfAbsent(col, k -> new ArrayList<>()).add(new int[]{row, node.val});
        dfs(node.left, row + 1, col - 1, map);
        dfs(node.right, row + 1, col + 1, map);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(3, new TreeNode(9, new TreeNode(4), new TreeNode(0)),
                new TreeNode(8, new TreeNode(1), new TreeNode(7)));
        System.out.println("Test 1: " + verticalTraversal(t1)); // [[4],[9],[3,0,1],[8],[7]]

        TreeNode t2 = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)),
                new TreeNode(3, new TreeNode(6), new TreeNode(7)));
        System.out.println("Test 2: " + verticalTraversal(t2));
    }
}

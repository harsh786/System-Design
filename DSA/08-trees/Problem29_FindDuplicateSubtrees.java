import java.util.*;
/**
 * Problem 29: Find Duplicate Subtrees (LeetCode 652)
 * 
 * Approach: Serialize each subtree, use HashMap to track occurrences. Add to result on second occurrence.
 * Time: O(n^2) due to string building, Space: O(n^2)
 * 
 * Production Analogy: Detecting duplicate component subtrees in a UI framework for deduplication/caching.
 */
public class Problem29_FindDuplicateSubtrees {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<TreeNode> findDuplicateSubtrees(TreeNode root) {
        List<TreeNode> result = new ArrayList<>();
        Map<String, Integer> map = new HashMap<>();
        serialize(root, map, result);
        return result;
    }

    private static String serialize(TreeNode node, Map<String, Integer> map, List<TreeNode> result) {
        if (node == null) return "#";
        String s = node.val + "," + serialize(node.left, map, result) + "," + serialize(node.right, map, result);
        map.put(s, map.getOrDefault(s, 0) + 1);
        if (map.get(s) == 2) result.add(node);
        return s;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, new TreeNode(4), null),
                new TreeNode(3, new TreeNode(2, new TreeNode(4), null), new TreeNode(4)));
        List<TreeNode> res = findDuplicateSubtrees(t1);
        System.out.print("Test 1 duplicates: ");
        for (TreeNode n : res) System.out.print(n.val + " ");
        System.out.println(); // 4 2 (subtrees rooted at 4 and 2)

        System.out.println("Test 2 (no dup): " + findDuplicateSubtrees(new TreeNode(1)).size()); // 0
    }
}

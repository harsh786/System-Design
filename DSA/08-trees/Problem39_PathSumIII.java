import java.util.*;
/**
 * Problem 39: Path Sum III (LeetCode 437)
 * 
 * Approach: Prefix sum with HashMap. Track running sum from root. Count paths where
 * currentSum - targetSum exists in prefix map.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding subarrays of API latencies in a call tree that sum to a threshold.
 */
public class Problem39_PathSumIII {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int pathSum(TreeNode root, int targetSum) {
        Map<Long, Integer> prefixMap = new HashMap<>();
        prefixMap.put(0L, 1);
        return dfs(root, 0L, targetSum, prefixMap);
    }

    private static int dfs(TreeNode node, long currentSum, int target, Map<Long, Integer> prefixMap) {
        if (node == null) return 0;
        currentSum += node.val;
        int count = prefixMap.getOrDefault(currentSum - target, 0);
        prefixMap.put(currentSum, prefixMap.getOrDefault(currentSum, 0) + 1);
        count += dfs(node.left, currentSum, target, prefixMap);
        count += dfs(node.right, currentSum, target, prefixMap);
        prefixMap.put(currentSum, prefixMap.get(currentSum) - 1);
        return count;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(10, new TreeNode(5, new TreeNode(3, new TreeNode(3), new TreeNode(-2)),
                new TreeNode(2, null, new TreeNode(1))), new TreeNode(-3, null, new TreeNode(11)));
        System.out.println("Test 1: " + pathSum(t1, 8)); // 3

        TreeNode t2 = new TreeNode(5, new TreeNode(4, new TreeNode(11, new TreeNode(7), new TreeNode(2)), null),
                new TreeNode(8, new TreeNode(13), new TreeNode(4, new TreeNode(5), new TreeNode(1))));
        System.out.println("Test 2: " + pathSum(t2, 22)); // 3

        System.out.println("Test 3: " + pathSum(null, 0)); // 0
    }
}

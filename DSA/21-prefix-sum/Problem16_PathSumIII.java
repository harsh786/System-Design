/**
 * Problem 16: Path Sum III (LeetCode 437)
 * 
 * Pattern: Prefix sum on tree paths with backtracking HashMap
 * 
 * DFS with running sum; use map of prefix sums to count paths summing to target.
 * Remove prefix sum from map on backtrack.
 * 
 * Time: O(n), Space: O(n) for map + recursion stack
 * 
 * Production Analogy: Finding paths in a dependency tree where cumulative latency
 * equals a specific SLA threshold.
 */
import java.util.*;

public class Problem16_PathSumIII {

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

    private static int dfs(TreeNode node, long currSum, int target, Map<Long, Integer> prefixMap) {
        if (node == null) return 0;
        currSum += node.val;
        int count = prefixMap.getOrDefault(currSum - target, 0);
        prefixMap.merge(currSum, 1, Integer::sum);
        count += dfs(node.left, currSum, target, prefixMap);
        count += dfs(node.right, currSum, target, prefixMap);
        prefixMap.merge(currSum, -1, Integer::sum);
        return count;
    }

    public static void main(String[] args) {
        // Tree: [10,5,-3,3,2,null,11,3,-2,null,1]
        TreeNode root = new TreeNode(10,
            new TreeNode(5, new TreeNode(3, new TreeNode(3), new TreeNode(-2)),
                         new TreeNode(2, null, new TreeNode(1))),
            new TreeNode(-3, null, new TreeNode(11)));
        assert pathSum(root, 8) == 3;

        // Single node
        assert pathSum(new TreeNode(1), 1) == 1;
        assert pathSum(null, 0) == 0;
        System.out.println("All tests passed!");
    }
}

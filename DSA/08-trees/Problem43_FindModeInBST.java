import java.util.*;
/**
 * Problem 43: Find Mode in Binary Search Tree (LeetCode 501)
 * 
 * Approach: Inorder traversal tracking current streak. O(1) extra space (Morris or two-pass).
 * Here using simple inorder with state variables.
 * Time: O(n), Space: O(1) extra (excluding output)
 * 
 * Production Analogy: Finding the most frequent error code in a sorted error log index.
 */
public class Problem43_FindModeInBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static int curVal, curCount, maxCount;
    static List<Integer> modes;

    public static int[] findMode(TreeNode root) {
        modes = new ArrayList<>();
        curCount = 0; maxCount = 0; curVal = Integer.MIN_VALUE;
        inorder(root);
        int[] res = new int[modes.size()];
        for (int i = 0; i < modes.size(); i++) res[i] = modes.get(i);
        return res;
    }

    private static void inorder(TreeNode node) {
        if (node == null) return;
        inorder(node.left);
        if (node.val == curVal) curCount++;
        else { curVal = node.val; curCount = 1; }
        if (curCount > maxCount) { maxCount = curCount; modes.clear(); modes.add(curVal); }
        else if (curCount == maxCount) modes.add(curVal);
        inorder(node.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, null, new TreeNode(2, new TreeNode(2), null));
        System.out.println("Test 1: " + Arrays.toString(findMode(t1))); // [2]

        TreeNode t2 = new TreeNode(0);
        System.out.println("Test 2: " + Arrays.toString(findMode(t2))); // [0]

        TreeNode t3 = new TreeNode(1, new TreeNode(1), new TreeNode(2, new TreeNode(2), null));
        System.out.println("Test 3: " + Arrays.toString(findMode(t3))); // [1,2]
    }
}

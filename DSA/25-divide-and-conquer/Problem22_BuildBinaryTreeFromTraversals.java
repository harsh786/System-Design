import java.util.*;

/**
 * Problem 22: Build Binary Tree from Preorder and Inorder Traversals (LeetCode 105)
 * 
 * D&C Approach:
 * - DIVIDE: First element of preorder is root. Find root in inorder to split left/right.
 * - CONQUER: Recursively build left subtree and right subtree
 * - COMBINE: Connect subtrees to root
 * 
 * Time: O(n) with HashMap, O(n^2) without
 * Space: O(n)
 * 
 * Production Analogy:
 * - Reconstructing hierarchical data from flattened serialization formats
 * - Rebuilding DOM tree from serialized event stream
 */
public class Problem22_BuildBinaryTreeFromTraversals {

    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    private static Map<Integer, Integer> inorderMap;
    private static int preIdx;

    public static TreeNode buildTree(int[] preorder, int[] inorder) {
        inorderMap = new HashMap<>();
        for (int i = 0; i < inorder.length; i++) inorderMap.put(inorder[i], i);
        preIdx = 0;
        return build(preorder, 0, inorder.length - 1);
    }

    private static TreeNode build(int[] preorder, int inLo, int inHi) {
        if (inLo > inHi) return null;
        int rootVal = preorder[preIdx++];
        TreeNode root = new TreeNode(rootVal);
        int inIdx = inorderMap.get(rootVal);
        root.left = build(preorder, inLo, inIdx - 1);
        root.right = build(preorder, inIdx + 1, inHi);
        return root;
    }

    private static void printPreorder(TreeNode root) {
        if (root == null) return;
        System.out.print(root.val + " ");
        printPreorder(root.left);
        printPreorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = buildTree(new int[]{3,9,20,15,7}, new int[]{9,3,15,20,7});
        printPreorder(t1); System.out.println(); // 3 9 20 15 7

        TreeNode t2 = buildTree(new int[]{-1}, new int[]{-1});
        printPreorder(t2); System.out.println(); // -1

        TreeNode t3 = buildTree(new int[]{1,2,3}, new int[]{3,2,1});
        printPreorder(t3); System.out.println(); // 1 2 3
    }
}

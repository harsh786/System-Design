import java.util.*;
/**
 * Problem 9: Construct Binary Tree from Preorder and Inorder Traversal (LeetCode 105)
 * 
 * Approach: First element of preorder is root. Find it in inorder to split left/right subtrees.
 * Use hashmap for O(1) inorder index lookup.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Reconstructing a decision tree model from its serialized traversal logs.
 */
public class Problem09_ConstructFromPreorderInorder {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
    }

    static int preIdx;
    static Map<Integer, Integer> inorderMap;

    public static TreeNode buildTree(int[] preorder, int[] inorder) {
        preIdx = 0;
        inorderMap = new HashMap<>();
        for (int i = 0; i < inorder.length; i++) inorderMap.put(inorder[i], i);
        return build(preorder, 0, inorder.length - 1);
    }

    private static TreeNode build(int[] preorder, int left, int right) {
        if (left > right) return null;
        int rootVal = preorder[preIdx++];
        TreeNode root = new TreeNode(rootVal);
        int mid = inorderMap.get(rootVal);
        root.left = build(preorder, left, mid - 1);
        root.right = build(preorder, mid + 1, right);
        return root;
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = buildTree(new int[]{3,9,20,15,7}, new int[]{9,3,15,20,7});
        System.out.print("Test 1 inorder: "); printInorder(t1); System.out.println(); // 9 3 15 20 7

        TreeNode t2 = buildTree(new int[]{-1}, new int[]{-1});
        System.out.println("Test 2 single: " + t2.val); // -1

        TreeNode t3 = buildTree(new int[]{1,2}, new int[]{2,1});
        System.out.print("Test 3: "); printInorder(t3); System.out.println(); // 2 1
    }
}

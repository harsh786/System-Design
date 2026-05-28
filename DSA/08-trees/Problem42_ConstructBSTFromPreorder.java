/**
 * Problem 42: Construct BST from Preorder Traversal (LeetCode 1008)
 * 
 * Approach: Use upper bound approach. Iterate preorder, assign values within valid range.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Rebuilding a search index from a preorder log dump.
 */
public class Problem42_ConstructBSTFromPreorder {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
    }

    static int idx;

    public static TreeNode bstFromPreorder(int[] preorder) {
        idx = 0;
        return build(preorder, Integer.MAX_VALUE);
    }

    private static TreeNode build(int[] preorder, int bound) {
        if (idx == preorder.length || preorder[idx] > bound) return null;
        TreeNode node = new TreeNode(preorder[idx++]);
        node.left = build(preorder, node.val);
        node.right = build(preorder, bound);
        return node;
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = bstFromPreorder(new int[]{8, 5, 1, 7, 10, 12});
        System.out.print("Test 1: "); printInorder(t1); System.out.println(); // 1 5 7 8 10 12

        TreeNode t2 = bstFromPreorder(new int[]{1, 3});
        System.out.print("Test 2: "); printInorder(t2); System.out.println(); // 1 3
    }
}

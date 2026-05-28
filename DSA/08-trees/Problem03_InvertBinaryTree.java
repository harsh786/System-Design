/**
 * Problem 3: Invert Binary Tree (LeetCode 226)
 * 
 * Approach: DFS - swap left and right children recursively.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Mirroring a directory structure for a failover deployment.
 */
public class Problem03_InvertBinaryTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode invertTree(TreeNode root) {
        if (root == null) return null;
        TreeNode temp = root.left;
        root.left = invertTree(root.right);
        root.right = invertTree(temp);
        return root;
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(4, new TreeNode(2, new TreeNode(1), new TreeNode(3)),
                                      new TreeNode(7, new TreeNode(6), new TreeNode(9)));
        System.out.print("Before: "); printInorder(t1); System.out.println();
        invertTree(t1);
        System.out.print("After:  "); printInorder(t1); System.out.println();

        System.out.println("Null test: " + invertTree(null)); // null
        
        TreeNode t2 = new TreeNode(1);
        invertTree(t2);
        System.out.println("Single node: " + t2.val); // 1
    }
}

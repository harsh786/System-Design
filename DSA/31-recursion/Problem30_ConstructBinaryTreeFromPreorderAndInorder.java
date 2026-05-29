import java.util.*;

public class Problem30_ConstructBinaryTreeFromPreorderAndInorder {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static int preIdx;
    static Map<Integer, Integer> inMap;
    public static TreeNode buildTree(int[] preorder, int[] inorder) {
        preIdx = 0;
        inMap = new HashMap<>();
        for (int i = 0; i < inorder.length; i++) inMap.put(inorder[i], i);
        return build(preorder, 0, inorder.length - 1);
    }
    static TreeNode build(int[] preorder, int l, int r) {
        if (l > r) return null;
        TreeNode root = new TreeNode(preorder[preIdx++]);
        int mid = inMap.get(root.val);
        root.left = build(preorder, l, mid - 1);
        root.right = build(preorder, mid + 1, r);
        return root;
    }
    public static void main(String[] args) {
        TreeNode root = buildTree(new int[]{3,9,20,15,7}, new int[]{9,3,15,20,7});
        System.out.println(root.val + " " + root.left.val + " " + root.right.val); // 3 9 20
    }
}

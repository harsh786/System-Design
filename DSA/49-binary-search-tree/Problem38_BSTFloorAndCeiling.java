public class Problem38_BSTFloorAndCeiling {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static Integer floor(TreeNode root, int key) {
        Integer res = null;
        while (root != null) {
            if (root.val == key) return key;
            if (root.val < key) { res = root.val; root = root.right; }
            else root = root.left;
        }
        return res;
    }

    public static Integer ceiling(TreeNode root, int key) {
        Integer res = null;
        while (root != null) {
            if (root.val == key) return key;
            if (root.val > key) { res = root.val; root = root.left; }
            else root = root.right;
        }
        return res;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(8);
        root.left = new TreeNode(4); root.right = new TreeNode(12);
        root.left.left = new TreeNode(2); root.left.right = new TreeNode(6);
        System.out.println(floor(root, 5));   // 4
        System.out.println(ceiling(root, 5)); // 6
        System.out.println(floor(root, 1));   // null
    }
}

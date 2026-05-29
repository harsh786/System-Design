public class Problem13_ClosestBinarySearchTreeValue {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static int closestValue(TreeNode root, double target) {
        int closest = root.val;
        while (root != null) {
            if (Math.abs(root.val - target) < Math.abs(closest - target)) closest = root.val;
            root = target < root.val ? root.left : root.right;
        }
        return closest;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(4);
        root.left = new TreeNode(2); root.right = new TreeNode(5);
        root.left.left = new TreeNode(1); root.left.right = new TreeNode(3);
        System.out.println(closestValue(root, 3.714286)); // 4
    }
}

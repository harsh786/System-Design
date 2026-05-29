import java.util.*;

public class Problem23_FindModeInBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static int curVal, curCount, maxCount;
    static List<Integer> modes;

    public static int[] findMode(TreeNode root) {
        modes = new ArrayList<>(); curCount = 0; maxCount = 0; curVal = Integer.MIN_VALUE;
        inorder(root);
        return modes.stream().mapToInt(i -> i).toArray();
    }

    private static void inorder(TreeNode n) {
        if (n == null) return;
        inorder(n.left);
        if (n.val == curVal) curCount++;
        else { curVal = n.val; curCount = 1; }
        if (curCount > maxCount) { maxCount = curCount; modes.clear(); modes.add(curVal); }
        else if (curCount == maxCount) modes.add(curVal);
        inorder(n.right);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1);
        root.right = new TreeNode(2); root.right.left = new TreeNode(2);
        System.out.println(Arrays.toString(findMode(root))); // [2]
    }
}

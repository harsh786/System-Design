import java.util.*;

public class Problem32_UniqueBinarySearchTreesII {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static List<TreeNode> generateTrees(int n) {
        if (n == 0) return new ArrayList<>();
        return generate(1, n);
    }

    private static List<TreeNode> generate(int lo, int hi) {
        List<TreeNode> res = new ArrayList<>();
        if (lo > hi) { res.add(null); return res; }
        for (int i = lo; i <= hi; i++) {
            for (TreeNode left : generate(lo, i - 1)) {
                for (TreeNode right : generate(i + 1, hi)) {
                    TreeNode node = new TreeNode(i);
                    node.left = left; node.right = right;
                    res.add(node);
                }
            }
        }
        return res;
    }

    public static void main(String[] args) {
        System.out.println(generateTrees(3).size()); // 5
    }
}

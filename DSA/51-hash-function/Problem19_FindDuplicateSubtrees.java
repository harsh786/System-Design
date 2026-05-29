import java.util.*;

public class Problem19_FindDuplicateSubtrees {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    private Map<String, Integer> count = new HashMap<>();
    private List<TreeNode> result = new ArrayList<>();

    public List<TreeNode> findDuplicateSubtrees(TreeNode root) {
        serialize(root);
        return result;
    }

    private String serialize(TreeNode node) {
        if (node == null) return "#";
        String s = node.val + "," + serialize(node.left) + "," + serialize(node.right);
        count.merge(s, 1, Integer::sum);
        if (count.get(s) == 2) result.add(node);
        return s;
    }

    public static void main(String[] args) {
        Problem19_FindDuplicateSubtrees sol = new Problem19_FindDuplicateSubtrees();
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.left = new TreeNode(4); root.right.left = new TreeNode(2);
        root.right.left.left = new TreeNode(4); root.right.right = new TreeNode(4);
        List<TreeNode> dups = sol.findDuplicateSubtrees(root);
        System.out.println("Duplicate subtree roots: " + dups.size()); // 2
    }
}

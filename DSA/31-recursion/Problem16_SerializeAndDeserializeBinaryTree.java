import java.util.*;

public class Problem16_SerializeAndDeserializeBinaryTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static String serialize(TreeNode root) {
        if (root == null) return "null";
        return root.val + "," + serialize(root.left) + "," + serialize(root.right);
    }
    public static TreeNode deserialize(String data) {
        Queue<String> q = new LinkedList<>(Arrays.asList(data.split(",")));
        return build(q);
    }
    static TreeNode build(Queue<String> q) {
        String val = q.poll();
        if ("null".equals(val)) return null;
        TreeNode node = new TreeNode(Integer.parseInt(val));
        node.left = build(q); node.right = build(q);
        return node;
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.right.left = new TreeNode(4); root.right.right = new TreeNode(5);
        String s = serialize(root);
        System.out.println(s);
        TreeNode res = deserialize(s);
        System.out.println(res.val + " " + res.right.left.val); // 1 4
    }
}

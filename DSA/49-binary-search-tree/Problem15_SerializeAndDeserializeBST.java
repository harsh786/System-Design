import java.util.*;

public class Problem15_SerializeAndDeserializeBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static String serialize(TreeNode root) {
        StringBuilder sb = new StringBuilder();
        serHelper(root, sb);
        return sb.toString();
    }

    private static void serHelper(TreeNode node, StringBuilder sb) {
        if (node == null) return;
        sb.append(node.val).append(",");
        serHelper(node.left, sb);
        serHelper(node.right, sb);
    }

    public static TreeNode deserialize(String data) {
        if (data.isEmpty()) return null;
        Queue<Integer> q = new LinkedList<>();
        for (String s : data.split(",")) q.offer(Integer.parseInt(s));
        return desHelper(q, Integer.MIN_VALUE, Integer.MAX_VALUE);
    }

    private static TreeNode desHelper(Queue<Integer> q, int min, int max) {
        if (q.isEmpty() || q.peek() < min || q.peek() > max) return null;
        int val = q.poll();
        TreeNode node = new TreeNode(val);
        node.left = desHelper(q, min, val);
        node.right = desHelper(q, val, max);
        return node;
    }

    static void inorder(TreeNode n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(5);
        root.left = new TreeNode(3); root.right = new TreeNode(7);
        root.left.left = new TreeNode(1);
        String s = serialize(root);
        System.out.println(s);
        TreeNode restored = deserialize(s);
        inorder(restored); System.out.println();
    }
}

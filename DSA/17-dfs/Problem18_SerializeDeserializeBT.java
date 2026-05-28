import java.util.*;

/**
 * Problem: Serialize and Deserialize Binary Tree (LeetCode 297)
 * Approach: Pre-order DFS with null markers for serialization
 * Time: O(N), Space: O(N)
 * Production Analogy: Serializing hierarchical data structures for network transmission/caching
 */
public class Problem18_SerializeDeserializeBT {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public String serialize(TreeNode root) {
        StringBuilder sb = new StringBuilder();
        serDfs(root, sb);
        return sb.toString();
    }

    private void serDfs(TreeNode node, StringBuilder sb) {
        if (node == null) { sb.append("null,"); return; }
        sb.append(node.val).append(",");
        serDfs(node.left, sb);
        serDfs(node.right, sb);
    }

    public TreeNode deserialize(String data) {
        Queue<String> q = new LinkedList<>(Arrays.asList(data.split(",")));
        return desDfs(q);
    }

    private TreeNode desDfs(Queue<String> q) {
        String val = q.poll();
        if ("null".equals(val)) return null;
        TreeNode node = new TreeNode(Integer.parseInt(val));
        node.left = desDfs(q);
        node.right = desDfs(q);
        return node;
    }

    public static void main(String[] args) {
        Problem18_SerializeDeserializeBT codec = new Problem18_SerializeDeserializeBT();
        TreeNode root = new TreeNode(1); root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.right.left = new TreeNode(4); root.right.right = new TreeNode(5);
        String s = codec.serialize(root);
        System.out.println(s);
        TreeNode r = codec.deserialize(s);
        System.out.println(codec.serialize(r));
    }
}

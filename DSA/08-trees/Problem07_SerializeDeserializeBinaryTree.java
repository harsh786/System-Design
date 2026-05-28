import java.util.*;
/**
 * Problem 7: Serialize and Deserialize Binary Tree (LeetCode 297)
 * 
 * Approach: Preorder DFS with "null" markers. Serialize to comma-separated string.
 * Deserialize using queue of tokens.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Serializing an in-memory tree structure (like DOM or AST)
 * for network transfer or persistent storage (Redis, Kafka messages).
 */
public class Problem07_SerializeDeserializeBinaryTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static String serialize(TreeNode root) {
        StringBuilder sb = new StringBuilder();
        serializeHelper(root, sb);
        return sb.toString();
    }

    private static void serializeHelper(TreeNode node, StringBuilder sb) {
        if (node == null) { sb.append("null,"); return; }
        sb.append(node.val).append(",");
        serializeHelper(node.left, sb);
        serializeHelper(node.right, sb);
    }

    public static TreeNode deserialize(String data) {
        Queue<String> queue = new LinkedList<>(Arrays.asList(data.split(",")));
        return deserializeHelper(queue);
    }

    private static TreeNode deserializeHelper(Queue<String> queue) {
        String val = queue.poll();
        if (val.equals("null")) return null;
        TreeNode node = new TreeNode(Integer.parseInt(val));
        node.left = deserializeHelper(queue);
        node.right = deserializeHelper(queue);
        return node;
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2), new TreeNode(3, new TreeNode(4), new TreeNode(5)));
        String s = serialize(t1);
        System.out.println("Serialized: " + s);
        TreeNode d = deserialize(s);
        System.out.print("Deserialized inorder: "); printInorder(d); System.out.println();

        // Null tree
        System.out.println("Null: " + serialize(null));
        System.out.println("Deserialize null: " + deserialize("null,"));
    }
}

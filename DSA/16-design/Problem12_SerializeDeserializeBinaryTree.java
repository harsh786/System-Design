import java.util.*;

/**
 * Problem 12: Serialize and Deserialize Binary Tree
 * 
 * API Contract:
 * - serialize(root): Encode tree to string
 * - deserialize(data): Decode string to tree
 * 
 * Complexity: O(n) for both operations
 * Data Structure: Preorder traversal with null markers
 * 
 * Production Analogy: Protocol Buffers serialization, JSON marshaling of tree structures,
 * database B-tree page serialization, network message encoding
 */
public class Problem12_SerializeDeserializeBinaryTree {

    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
    }

    static class Codec {
        public String serialize(TreeNode root) {
            StringBuilder sb = new StringBuilder();
            serHelper(root, sb);
            return sb.toString();
        }

        private void serHelper(TreeNode node, StringBuilder sb) {
            if (node == null) { sb.append("#,"); return; }
            sb.append(node.val).append(",");
            serHelper(node.left, sb);
            serHelper(node.right, sb);
        }

        public TreeNode deserialize(String data) {
            Queue<String> queue = new LinkedList<>(Arrays.asList(data.split(",")));
            return desHelper(queue);
        }

        private TreeNode desHelper(Queue<String> queue) {
            String val = queue.poll();
            if (val.equals("#")) return null;
            TreeNode node = new TreeNode(Integer.parseInt(val));
            node.left = desHelper(queue);
            node.right = desHelper(queue);
            return node;
        }
    }

    public static void main(String[] args) {
        Codec codec = new Codec();

        // Test: [1,2,3,null,null,4,5]
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(2);
        root.right = new TreeNode(3);
        root.right.left = new TreeNode(4);
        root.right.right = new TreeNode(5);

        String s = codec.serialize(root);
        TreeNode res = codec.deserialize(s);
        assert res.val == 1;
        assert res.left.val == 2;
        assert res.right.val == 3;
        assert res.right.left.val == 4;

        // Edge: null tree
        assert codec.deserialize(codec.serialize(null)) == null;

        // Edge: single node
        TreeNode single = new TreeNode(42);
        TreeNode r2 = codec.deserialize(codec.serialize(single));
        assert r2.val == 42 && r2.left == null && r2.right == null;

        System.out.println("All tests passed!");
    }
}

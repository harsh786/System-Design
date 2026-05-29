import java.util.*;

/**
 * Problem 22: Design File System
 * 
 * Create paths with associated values. Parent path must exist.
 * 
 * Time Complexity: O(m) per operation where m = path length (components)
 * Space Complexity: O(total path components)
 * 
 * Production Analogy: Unix filesystem path resolution, REST API route registration,
 * configuration key-value stores (etcd, Consul), registry systems (Windows Registry).
 */
public class Problem22_DesignFileSystem {

    static class TrieNode {
        Map<String, TrieNode> children = new HashMap<>();
        int value = -1;
    }

    static class FileSystem {
        TrieNode root = new TrieNode();

        public boolean createPath(String path, int value) {
            String[] parts = path.split("/");
            TrieNode node = root;
            for (int i = 1; i < parts.length - 1; i++) {
                if (!node.children.containsKey(parts[i])) return false;
                node = node.children.get(parts[i]);
            }
            String last = parts[parts.length - 1];
            if (node.children.containsKey(last)) return false;
            node.children.put(last, new TrieNode());
            node.children.get(last).value = value;
            return true;
        }

        public int get(String path) {
            String[] parts = path.split("/");
            TrieNode node = root;
            for (int i = 1; i < parts.length; i++) {
                if (!node.children.containsKey(parts[i])) return -1;
                node = node.children.get(parts[i]);
            }
            return node.value;
        }
    }

    public static void main(String[] args) {
        FileSystem fs = new FileSystem();
        System.out.println(fs.createPath("/a", 1));       // true
        System.out.println(fs.createPath("/a/b", 2));     // true
        System.out.println(fs.get("/a/b"));               // 2
        System.out.println(fs.createPath("/a/b/c", 3));   // true
        System.out.println(fs.createPath("/c/d", 4));     // false (parent /c doesn't exist)
        System.out.println(fs.get("/c/d"));               // -1
        System.out.println(fs.createPath("/a", 5));       // false (already exists)
    }
}

import java.util.*;

/**
 * Problem 23: Design File System (Path-based)
 * 
 * API Contract:
 * - createPath(path, value): Create path with value. Parent must exist. Return true/false.
 * - get(path): Return value at path or -1.
 * 
 * Complexity: O(L) where L = path length (number of components)
 * Data Structure: Trie where each node is a path component
 * 
 * Production Analogy: ZooKeeper znodes, etcd key-value paths,
 * Consul KV store, configuration registries
 */
public class Problem23_DesignFileSystem {

    static class FileSystem {
        private Map<String, Integer> paths;

        public FileSystem() {
            paths = new HashMap<>();
            paths.put("", -1); // root
        }

        public boolean createPath(String path, int value) {
            if (paths.containsKey(path)) return false;
            String parent = path.substring(0, path.lastIndexOf('/'));
            if (!paths.containsKey(parent)) return false;
            paths.put(path, value);
            return true;
        }

        public int get(String path) {
            return paths.getOrDefault(path, -1);
        }
    }

    public static void main(String[] args) {
        FileSystem fs = new FileSystem();
        assert fs.createPath("/a", 1);
        assert fs.get("/a") == 1;
        assert !fs.createPath("/a/b/c", 3); // /a/b doesn't exist
        assert fs.createPath("/a/b", 2);
        assert fs.createPath("/a/b/c", 3);
        assert fs.get("/a/b/c") == 3;
        assert !fs.createPath("/a", 10); // already exists
        assert fs.get("/nonexistent") == -1;

        System.out.println("All tests passed!");
    }
}

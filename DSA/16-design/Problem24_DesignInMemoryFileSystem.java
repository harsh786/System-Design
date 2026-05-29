import java.util.*;

/**
 * Problem 24: Design In-Memory File System
 * 
 * API Contract:
 * - ls(path): List directory contents sorted, or file name if path is file
 * - mkdir(path): Create directory path (all intermediate dirs)
 * - addContentToFile(path, content): Append content to file
 * - readContentFromFile(path): Return file content
 * 
 * Complexity: O(L + k log k) for ls, O(L) for others where L=path depth, k=children
 * Data Structure: Trie of directory/file nodes
 * 
 * Production Analogy: In-memory FS like tmpfs/ramfs, virtual file systems,
 * Docker overlay FS, IDE virtual workspace
 */
public class Problem24_DesignInMemoryFileSystem {

    static class FileSystemNode {
        Map<String, FileSystemNode> children = new TreeMap<>();
        boolean isFile;
        StringBuilder content = new StringBuilder();
    }

    static class InMemoryFileSystem {
        private FileSystemNode root;

        public InMemoryFileSystem() { root = new FileSystemNode(); }

        public List<String> ls(String path) {
            FileSystemNode node = traverse(path);
            if (node.isFile) {
                String name = path.substring(path.lastIndexOf('/') + 1);
                return Arrays.asList(name);
            }
            return new ArrayList<>(node.children.keySet());
        }

        public void mkdir(String path) { traverse(path); }

        public void addContentToFile(String filePath, String content) {
            FileSystemNode node = traverse(filePath);
            node.isFile = true;
            node.content.append(content);
        }

        public String readContentFromFile(String filePath) {
            return traverse(filePath).content.toString();
        }

        private FileSystemNode traverse(String path) {
            FileSystemNode node = root;
            if (path.equals("/")) return node;
            String[] parts = path.split("/");
            for (int i = 1; i < parts.length; i++) {
                node.children.putIfAbsent(parts[i], new FileSystemNode());
                node = node.children.get(parts[i]);
            }
            return node;
        }
    }

    public static void main(String[] args) {
        InMemoryFileSystem fs = new InMemoryFileSystem();
        assert fs.ls("/").isEmpty();
        fs.mkdir("/a/b/c");
        fs.addContentToFile("/a/b/c/d", "hello");
        assert fs.ls("/").equals(Arrays.asList("a"));
        assert fs.readContentFromFile("/a/b/c/d").equals("hello");
        fs.addContentToFile("/a/b/c/d", " world");
        assert fs.readContentFromFile("/a/b/c/d").equals("hello world");
        assert fs.ls("/a/b/c/d").equals(Arrays.asList("d"));
        assert fs.ls("/a/b/c").equals(Arrays.asList("d"));

        System.out.println("All tests passed!");
    }
}

import java.util.*;

/**
 * Problem 23: Design In-Memory File System
 * 
 * Support: ls, mkdir, addContentToFile, readContentFromFile
 * 
 * Time Complexity: O(m + n*log(n)) for ls (m=path depth, n=entries), O(m) for others
 * Space Complexity: O(total content + total paths)
 * 
 * Production Analogy: In-memory filesystems (tmpfs), virtual file systems in Docker,
 * mock filesystems in unit tests, browser-based IDEs (CodeSandbox).
 */
public class Problem23_DesignInMemoryFileSystem {

    static class TrieNode {
        Map<String, TrieNode> children = new TreeMap<>();
        String content = "";
        boolean isFile = false;
    }

    static class FileSystem {
        TrieNode root = new TrieNode();

        public List<String> ls(String path) {
            TrieNode node = traverse(path);
            if (node.isFile) {
                String[] parts = path.split("/");
                return Arrays.asList(parts[parts.length - 1]);
            }
            return new ArrayList<>(node.children.keySet());
        }

        public void mkdir(String path) { traverse(path); }

        public void addContentToFile(String filePath, String content) {
            TrieNode node = traverse(filePath);
            node.isFile = true;
            node.content += content;
        }

        public String readContentFromFile(String filePath) {
            return traverse(filePath).content;
        }

        TrieNode traverse(String path) {
            TrieNode node = root;
            if (path.equals("/")) return node;
            String[] parts = path.split("/");
            for (int i = 1; i < parts.length; i++) {
                node.children.putIfAbsent(parts[i], new TrieNode());
                node = node.children.get(parts[i]);
            }
            return node;
        }
    }

    public static void main(String[] args) {
        FileSystem fs = new FileSystem();
        System.out.println(fs.ls("/"));                    // []
        fs.mkdir("/a/b/c");
        fs.addContentToFile("/a/b/c/d", "hello");
        System.out.println(fs.ls("/"));                    // [a]
        System.out.println(fs.readContentFromFile("/a/b/c/d")); // hello
        System.out.println(fs.ls("/a/b/c"));               // [d]
        System.out.println(fs.ls("/a/b/c/d"));             // [d] (file)
        fs.addContentToFile("/a/b/c/d", " world");
        System.out.println(fs.readContentFromFile("/a/b/c/d")); // hello world
    }
}

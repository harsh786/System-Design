import java.util.*;

/**
 * Problem 26: Remove Sub-Folders from the Filesystem
 * 
 * Given a list of folder paths, remove all sub-folders and return remaining folders.
 * 
 * Time Complexity: O(n * m) where n = folders, m = max path depth
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: .gitignore processing, backup exclusion lists,
 * filesystem permissions (parent overrides child), CDN cache invalidation.
 */
public class Problem26_RemoveSubFolders {

    static class TrieNode {
        Map<String, TrieNode> children = new HashMap<>();
        boolean isFolder = false;
    }

    public static List<String> removeSubfolders(String[] folder) {
        TrieNode root = new TrieNode();
        for (String f : folder) {
            TrieNode node = root;
            String[] parts = f.split("/");
            for (int i = 1; i < parts.length; i++) {
                node.children.putIfAbsent(parts[i], new TrieNode());
                node = node.children.get(parts[i]);
            }
            node.isFolder = true;
        }

        List<String> result = new ArrayList<>();
        for (String f : folder) {
            TrieNode node = root;
            String[] parts = f.split("/");
            boolean isSubfolder = false;
            for (int i = 1; i < parts.length - 1; i++) {
                node = node.children.get(parts[i]);
                if (node.isFolder) { isSubfolder = true; break; }
            }
            if (!isSubfolder) result.add(f);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(removeSubfolders(new String[]{"/a","/a/b","/c/d","/c/d/e","/c/f"}));
        // [/a, /c/d, /c/f]
        System.out.println(removeSubfolders(new String[]{"/a","/a/b/c","/a/b/d"}));
        // [/a]
        System.out.println(removeSubfolders(new String[]{"/a/b/c","/a/b/ca","/a/b/d"}));
        // [/a/b/c, /a/b/ca, /a/b/d] (none are subfolders of each other)
    }
}

import java.util.*;

/**
 * Problem 25: Find Duplicate Folders in System
 * 
 * Two folders are identical if they have the same sub-folder structure.
 * Find and delete all duplicate folder groups.
 * 
 * Time Complexity: O(n * m) for building + serialization
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: Deduplication in backup systems, detecting duplicate directory
 * structures in cloud storage, filesystem cleanup tools.
 */
public class Problem25_FindDuplicateFolders {

    static class TrieNode {
        TreeMap<String, TrieNode> children = new TreeMap<>();
        String serial = "";
        boolean deleted = false;
    }

    public static List<List<String>> deleteDuplicateFolder(List<List<String>> paths) {
        TrieNode root = new TrieNode();
        // Build trie
        for (List<String> path : paths) {
            TrieNode node = root;
            for (String p : path) {
                node.children.putIfAbsent(p, new TrieNode());
                node = node.children.get(p);
            }
        }
        // Serialize subtrees
        Map<String, List<TrieNode>> serialMap = new HashMap<>();
        serialize(root, serialMap);
        // Mark duplicates
        for (List<TrieNode> nodes : serialMap.values()) {
            if (nodes.size() > 1) {
                for (TrieNode node : nodes) node.deleted = true;
            }
        }
        // Collect remaining paths
        List<List<String>> result = new ArrayList<>();
        List<String> current = new ArrayList<>();
        collectPaths(root, current, result);
        return result;
    }

    static String serialize(TrieNode node, Map<String, List<TrieNode>> map) {
        if (node.children.isEmpty()) return "";
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, TrieNode> e : node.children.entrySet()) {
            sb.append("(").append(e.getKey()).append(serialize(e.getValue(), map)).append(")");
        }
        node.serial = sb.toString();
        map.computeIfAbsent(node.serial, k -> new ArrayList<>()).add(node);
        return node.serial;
    }

    static void collectPaths(TrieNode node, List<String> current, List<List<String>> result) {
        for (Map.Entry<String, TrieNode> e : node.children.entrySet()) {
            if (!e.getValue().deleted) {
                current.add(e.getKey());
                result.add(new ArrayList<>(current));
                collectPaths(e.getValue(), current, result);
                current.remove(current.size() - 1);
            }
        }
    }

    public static void main(String[] args) {
        List<List<String>> paths = Arrays.asList(
            Arrays.asList("a"), Arrays.asList("c"),
            Arrays.asList("a","b"), Arrays.asList("c","b"),
            Arrays.asList("a","b","x"), Arrays.asList("c","b","x"));
        System.out.println(deleteDuplicateFolder(paths));
        // Both a and c have identical subtree structure -> deleted
    }
}

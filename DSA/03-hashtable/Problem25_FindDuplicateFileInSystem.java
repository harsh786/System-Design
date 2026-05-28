import java.util.*;

/**
 * Problem 25: Find Duplicate File in System
 * Given paths with file contents, group files with duplicate content.
 *
 * Time Complexity: O(n * k) where k is average content length
 * Space Complexity: O(n * k)
 *
 * Production Analogy: Content-addressable storage deduplication (like git objects).
 * Files are grouped by content hash to eliminate redundant storage.
 */
public class Problem25_FindDuplicateFileInSystem {
    public List<List<String>> findDuplicate(String[] paths) {
        Map<String, List<String>> contentMap = new HashMap<>();
        for (String path : paths) {
            String[] parts = path.split(" ");
            String dir = parts[0];
            for (int i = 1; i < parts.length; i++) {
                int paren = parts[i].indexOf('(');
                String file = parts[i].substring(0, paren);
                String content = parts[i].substring(paren + 1, parts[i].length() - 1);
                contentMap.computeIfAbsent(content, k -> new ArrayList<>()).add(dir + "/" + file);
            }
        }
        List<List<String>> result = new ArrayList<>();
        for (List<String> files : contentMap.values()) {
            if (files.size() > 1) result.add(files);
        }
        return result;
    }

    public static void main(String[] args) {
        Problem25_FindDuplicateFileInSystem sol = new Problem25_FindDuplicateFileInSystem();
        String[] paths = {"root/a 1.txt(abcd) 2.txt(efgh)", "root/c 3.txt(abcd)", "root/c/d 4.txt(efgh)"};
        System.out.println(sol.findDuplicate(paths));
        // [[root/a/1.txt, root/c/3.txt], [root/a/2.txt, root/c/d/4.txt]]
    }
}

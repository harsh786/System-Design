/**
 * Problem: Find Duplicate File in System (LeetCode 609)
 * Approach: Group files by content using HashMap
 * Complexity: O(n * k) time, O(n * k) space
 * Production Analogy: Content-based deduplication in distributed file systems
 */
import java.util.*;
public class Problem42_FindDuplicateFileInSystem {
    public List<List<String>> findDuplicate(String[] paths) {
        Map<String, List<String>> map = new HashMap<>();
        for (String path : paths) {
            String[] parts = path.split(" ");
            String dir = parts[0];
            for (int i = 1; i < parts.length; i++) {
                int paren = parts[i].indexOf('(');
                String file = parts[i].substring(0, paren);
                String content = parts[i].substring(paren+1, parts[i].length()-1);
                map.computeIfAbsent(content, k -> new ArrayList<>()).add(dir + "/" + file);
            }
        }
        List<List<String>> res = new ArrayList<>();
        for (List<String> group : map.values()) if (group.size() > 1) res.add(group);
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new Problem42_FindDuplicateFileInSystem().findDuplicate(new String[]{
            "root/a 1.txt(abcd) 2.txt(efgh)", "root/c 3.txt(abcd)", "root/c/d 4.txt(efgh)"}));
    }
}

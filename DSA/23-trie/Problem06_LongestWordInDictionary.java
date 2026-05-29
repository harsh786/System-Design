import java.util.*;

/**
 * Problem 6: Longest Word in Dictionary
 * 
 * Find the longest word that can be built one character at a time by other words in the array.
 * If multiple answers, return lexicographically smallest.
 * 
 * Time Complexity: O(n * m) where n = number of words, m = max word length
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: Progressive disclosure in UI (showing increasingly detailed info),
 * incremental build systems validating each build step exists.
 */
public class Problem06_LongestWordInDictionary {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    public static String longestWord(String[] words) {
        TrieNode root = new TrieNode();
        root.isEnd = true; // empty string is buildable
        for (String w : words) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
        }

        String result = "";
        // BFS - only follow paths where every prefix is a complete word
        Queue<TrieNode> queue = new LinkedList<>();
        Queue<String> paths = new LinkedList<>();
        for (int i = 0; i < 26; i++) {
            if (root.children[i] != null && root.children[i].isEnd) {
                queue.offer(root.children[i]);
                paths.offer(String.valueOf((char)('a' + i)));
            }
        }
        while (!queue.isEmpty()) {
            TrieNode node = queue.poll();
            String path = paths.poll();
            if (path.length() > result.length() || 
                (path.length() == result.length() && path.compareTo(result) < 0)) {
                result = path;
            }
            for (int i = 0; i < 26; i++) {
                if (node.children[i] != null && node.children[i].isEnd) {
                    queue.offer(node.children[i]);
                    paths.offer(path + (char)('a' + i));
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(longestWord(new String[]{"w","wo","wor","worl","world"})); // "world"
        System.out.println(longestWord(new String[]{"a","banana","app","appl","ap","apply","apple"})); // "apple"
        System.out.println(longestWord(new String[]{"b","br","bre","brea","break","breakf","breakfast"})); // "breakfast"
    }
}

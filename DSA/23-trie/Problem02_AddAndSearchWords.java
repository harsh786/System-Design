/**
 * Problem 2: Design Add and Search Words Data Structure
 * 
 * Support '.' wildcard that can match any letter.
 * 
 * Time Complexity: Insert O(m), Search O(26^m) worst case with all dots, O(m) typical
 * Space Complexity: O(n * m)
 * 
 * Production Analogy: Regex-like pattern matching in text editors, DNS wildcard records,
 * fuzzy search in databases.
 */
public class Problem02_AddAndSearchWords {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    static class WordDictionary {
        TrieNode root = new TrieNode();

        public void addWord(String word) {
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
        }

        public boolean search(String word) {
            return dfs(word, 0, root);
        }

        private boolean dfs(String word, int i, TrieNode node) {
            if (i == word.length()) return node.isEnd;
            char c = word.charAt(i);
            if (c == '.') {
                for (TrieNode child : node.children) {
                    if (child != null && dfs(word, i + 1, child)) return true;
                }
                return false;
            } else {
                int idx = c - 'a';
                if (node.children[idx] == null) return false;
                return dfs(word, i + 1, node.children[idx]);
            }
        }
    }

    public static void main(String[] args) {
        WordDictionary wd = new WordDictionary();
        wd.addWord("bad");
        wd.addWord("dad");
        wd.addWord("mad");
        System.out.println(wd.search("pad"));  // false
        System.out.println(wd.search("bad"));  // true
        System.out.println(wd.search(".ad"));  // true
        System.out.println(wd.search("b.."));  // true
        System.out.println(wd.search("..."));  // true
        System.out.println(wd.search("...."));// false
        System.out.println(wd.search(""));    // false
    }
}

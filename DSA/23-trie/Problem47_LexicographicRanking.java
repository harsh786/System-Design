/**
 * Problem 47: Lexicographic Ranking with Trie
 * 
 * Given a set of strings, find the lexicographic rank of a query string.
 * Use trie with subtree counts to efficiently compute rank.
 * 
 * Time Complexity: O(m) per query where m = query length
 * Space Complexity: O(n*m) for trie
 * 
 * Production Analogy: Database index positioning, sorted list pagination,
 * leaderboard ranking, version comparison systems.
 */
public class Problem47_LexicographicRanking {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        int wordsHere = 0;     // words ending at this node
        int wordsBelow = 0;    // total words in this subtree (including here)
    }

    static class LexRanker {
        TrieNode root = new TrieNode();

        void insert(String word) {
            TrieNode node = root;
            node.wordsBelow++;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
                node.wordsBelow++;
            }
            node.wordsHere++;
        }

        // Returns 1-based rank of the word (assumes word exists)
        int getRank(String word) {
            TrieNode node = root;
            int rank = 0;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                // Count all words in subtrees of children < current char
                for (int i = 0; i < idx; i++) {
                    if (node.children[i] != null) rank += node.children[i].wordsBelow;
                }
                // Count words ending at current node (they come before deeper words)
                rank += node.wordsHere;
                node = node.children[idx];
            }
            return rank + 1; // 1-based
        }
    }

    public static void main(String[] args) {
        LexRanker ranker = new LexRanker();
        String[] words = {"apple","app","banana","bat","ball","cat"};
        for (String w : words) ranker.insert(w);

        for (String w : words) {
            System.out.println(w + " -> rank " + ranker.getRank(w));
        }
        // Sorted: app(1), apple(2), ball(3), banana(4), bat(5), cat(6)
    }
}

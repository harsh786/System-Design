import java.util.*;

/**
 * Problem 41: Autocomplete with Hotness/Frequency
 * 
 * Autocomplete that ranks suggestions by frequency/hotness score.
 * Returns top-k results for any prefix.
 * 
 * Time Complexity: O(prefix_len + k*log(k)) per query
 * Space Complexity: O(n*m) for trie
 * 
 * Production Analogy: Google Trends-aware search suggestions, trending hashtag completion,
 * e-commerce "popular products" autocomplete, Spotify song search by play count.
 */
public class Problem41_AutocompleteWithFrequency {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        // Store top suggestions at each node for O(1) retrieval
        PriorityQueue<int[]> topK = new PriorityQueue<>((a, b) -> a[1] - b[1]); // [wordId, freq]
        boolean isEnd = false;
        int freq = 0;
    }

    static class HotAutocomplete {
        TrieNode root = new TrieNode();
        List<String> words = new ArrayList<>();
        int k;

        HotAutocomplete(int k) { this.k = k; }

        void addWord(String word, int frequency) {
            int wordId = words.size();
            words.add(word);
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
                node.topK.offer(new int[]{wordId, frequency});
                if (node.topK.size() > k) node.topK.poll();
            }
            node.isEnd = true;
            node.freq = frequency;
        }

        List<String> suggest(String prefix) {
            TrieNode node = root;
            for (char c : prefix.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) return new ArrayList<>();
                node = node.children[idx];
            }
            List<String> result = new ArrayList<>();
            PriorityQueue<int[]> copy = new PriorityQueue<>(node.topK);
            LinkedList<String> temp = new LinkedList<>();
            while (!copy.isEmpty()) temp.addFirst(words.get(copy.poll()[0]));
            return temp;
        }
    }

    public static void main(String[] args) {
        HotAutocomplete ac = new HotAutocomplete(3);
        ac.addWord("amazon", 100);
        ac.addWord("apple", 80);
        ac.addWord("apache", 50);
        ac.addWord("application", 30);
        ac.addWord("azure", 70);

        System.out.println(ac.suggest("a"));   // top 3 of all: amazon, apple, azure
        System.out.println(ac.suggest("ap"));  // apple, apache, application
        System.out.println(ac.suggest("az"));  // azure
        System.out.println(ac.suggest("b"));   // []
    }
}

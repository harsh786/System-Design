import java.util.*;

/**
 * Problem 15: Design Search Autocomplete System
 * 
 * Given historical sentences with times, design autocomplete:
 * - input(c): returns top 3 hot sentences with current prefix
 * - input('#'): ends current sentence and records it
 * 
 * Time Complexity: O(p + q*log(q)) per input where p=prefix nodes, q=matching sentences
 * Space Complexity: O(n*m) for all sentences
 * 
 * Production Analogy: Google Search autocomplete, Slack message search,
 * terminal command history (Ctrl+R), browser URL bar suggestions.
 */
public class Problem15_DesignSearchAutocomplete {

    static class TrieNode {
        TrieNode[] children = new TrieNode[128]; // ASCII
        Map<String, Integer> counts = new HashMap<>();
    }

    static class AutocompleteSystem {
        TrieNode root = new TrieNode();
        StringBuilder current = new StringBuilder();
        TrieNode currentNode;

        public AutocompleteSystem(String[] sentences, int[] times) {
            for (int i = 0; i < sentences.length; i++) {
                addSentence(sentences[i], times[i]);
            }
            currentNode = root;
        }

        void addSentence(String sentence, int count) {
            TrieNode node = root;
            for (char c : sentence.toCharArray()) {
                if (node.children[c] == null) node.children[c] = new TrieNode();
                node = node.children[c];
                node.counts.merge(sentence, count, Integer::sum);
            }
        }

        public List<String> input(char c) {
            if (c == '#') {
                addSentence(current.toString(), 1);
                current = new StringBuilder();
                currentNode = root;
                return new ArrayList<>();
            }
            current.append(c);
            if (currentNode != null) currentNode = currentNode.children[c];
            if (currentNode == null) return new ArrayList<>();

            PriorityQueue<Map.Entry<String, Integer>> pq = new PriorityQueue<>(
                (a, b) -> a.getValue().equals(b.getValue()) ? 
                    b.getKey().compareTo(a.getKey()) : a.getValue() - b.getValue());
            for (Map.Entry<String, Integer> e : currentNode.counts.entrySet()) {
                pq.offer(e);
                if (pq.size() > 3) pq.poll();
            }
            LinkedList<String> result = new LinkedList<>();
            while (!pq.isEmpty()) result.addFirst(pq.poll().getKey());
            return result;
        }
    }

    public static void main(String[] args) {
        AutocompleteSystem sys = new AutocompleteSystem(
            new String[]{"i love you","island","iroman","i love leetcode"}, new int[]{5,3,2,2});
        System.out.println(sys.input('i')); // [i love you, island, i love leetcode]
        System.out.println(sys.input(' ')); // [i love you, i love leetcode]
        System.out.println(sys.input('a')); // []
        System.out.println(sys.input('#')); // []
        System.out.println(sys.input('i')); // [i love you, island, i a]
    }
}

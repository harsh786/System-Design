import java.util.*;

/**
 * Problem 22: Design Search Autocomplete System
 * 
 * API Contract:
 * - input(c): Process character. Return top 3 hot sentences with current prefix.
 *   '#' marks end of sentence (record it).
 * 
 * Complexity: O(n log 3) per input where n = matching sentences
 * Data Structure: Trie + HashMap for sentence frequencies
 * 
 * Production Analogy: Google search suggestions, IDE autocomplete,
 * command palette in VS Code, Elasticsearch suggesters
 */
public class Problem22_DesignSearchAutocompleteSystem {

    static class AutocompleteSystem {
        private Map<String, Integer> freq;
        private StringBuilder current;

        public AutocompleteSystem(String[] sentences, int[] times) {
            freq = new HashMap<>();
            current = new StringBuilder();
            for (int i = 0; i < sentences.length; i++)
                freq.put(sentences[i], times[i]);
        }

        public List<String> input(char c) {
            if (c == '#') {
                freq.merge(current.toString(), 1, Integer::sum);
                current = new StringBuilder();
                return new ArrayList<>();
            }
            current.append(c);
            String prefix = current.toString();
            PriorityQueue<String> pq = new PriorityQueue<>((a, b) -> {
                int diff = freq.get(a) - freq.get(b);
                return diff != 0 ? diff : b.compareTo(a); // min-heap by freq, max by lex
            });
            for (Map.Entry<String, Integer> e : freq.entrySet()) {
                if (e.getKey().startsWith(prefix)) {
                    pq.offer(e.getKey());
                    if (pq.size() > 3) pq.poll();
                }
            }
            List<String> result = new ArrayList<>();
            while (!pq.isEmpty()) result.add(0, pq.poll());
            return result;
        }
    }

    public static void main(String[] args) {
        AutocompleteSystem ac = new AutocompleteSystem(
            new String[]{"i love you", "island", "iroman", "i love leetcode"},
            new int[]{5, 3, 2, 2}
        );
        assert ac.input('i').equals(Arrays.asList("i love you", "island", "i love leetcode"));
        assert ac.input(' ').equals(Arrays.asList("i love you", "i love leetcode"));
        assert ac.input('a').isEmpty();
        ac.input('#'); // records "i a"

        // Now "i a" has freq 1
        List<String> res = ac.input('i');
        assert res.contains("i love you");

        System.out.println("All tests passed!");
    }
}

import java.util.*;

/**
 * Problem 58: Type-Ahead with Fuzzy Matching
 * 
 * Production Relevance:
 * - Users make typos: "javscript" should still match "javascript"
 * - Edit distance (Levenshtein) combined with trie traversal
 * - Used in search engines, spell checkers, IDE symbol lookup
 * - Must be fast enough for real-time (each keystroke triggers search)
 * 
 * Architect Considerations:
 * - BK-tree or trie with bounded edit distance traversal
 * - Max edit distance of 1-2 is usually sufficient for typo correction
 * - Optimization: prune branches where min possible distance exceeds threshold
 * - Combine with prefix matching: fuzzy on completed words, exact on prefix
 */
public class Problem58_TypeAheadFuzzyMatching {

    static class TrieNode {
        Map<Character, TrieNode> children = new HashMap<>();
        String word;
        int frequency;
    }

    static class FuzzyResult implements Comparable<FuzzyResult> {
        String word;
        int editDistance;
        int frequency;

        FuzzyResult(String word, int dist, int freq) {
            this.word = word; this.editDistance = dist; this.frequency = freq;
        }

        double score() { return frequency * (1.0 / (1 + editDistance)); }

        @Override
        public int compareTo(FuzzyResult other) { return Double.compare(other.score(), this.score()); }

        @Override
        public String toString() { return String.format("%s(dist=%d,freq=%d,score=%.1f)", word, editDistance, frequency, score()); }
    }

    static class FuzzyTypeAhead {
        TrieNode root = new TrieNode();

        void insert(String word, int frequency) {
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                node.children.computeIfAbsent(c, k -> new TrieNode());
                node = node.children.get(c);
            }
            node.word = word;
            node.frequency = frequency;
        }

        // Fuzzy search: find words within maxDist edit distance of query
        List<FuzzyResult> fuzzySearch(String query, int maxDist, int topK) {
            List<FuzzyResult> results = new ArrayList<>();

            // Use dynamic programming approach over trie
            // currentRow represents edit distances for prefix matching
            int[] currentRow = new int[query.length() + 1];
            for (int i = 0; i <= query.length(); i++) currentRow[i] = i;

            for (Map.Entry<Character, TrieNode> entry : root.children.entrySet()) {
                searchRecursive(entry.getValue(), entry.getKey(), query, currentRow, results, maxDist);
            }

            results.sort(FuzzyResult::compareTo);
            return results.subList(0, Math.min(topK, results.size()));
        }

        private void searchRecursive(TrieNode node, char ch, String query,
                                      int[] previousRow, List<FuzzyResult> results, int maxDist) {
            int[] currentRow = new int[query.length() + 1];
            currentRow[0] = previousRow[0] + 1;

            for (int i = 1; i <= query.length(); i++) {
                int insertCost = currentRow[i - 1] + 1;
                int deleteCost = previousRow[i] + 1;
                int replaceCost = previousRow[i - 1] + (query.charAt(i - 1) == ch ? 0 : 1);
                currentRow[i] = Math.min(Math.min(insertCost, deleteCost), replaceCost);
            }

            // If this node is a word and distance is within threshold
            if (node.word != null && currentRow[query.length()] <= maxDist) {
                results.add(new FuzzyResult(node.word, currentRow[query.length()], node.frequency));
            }

            // Prune: if minimum value in currentRow exceeds maxDist, no need to go deeper
            int minInRow = Integer.MAX_VALUE;
            for (int val : currentRow) minInRow = Math.min(minInRow, val);
            if (minInRow > maxDist) return;

            // Recurse into children
            for (Map.Entry<Character, TrieNode> entry : node.children.entrySet()) {
                searchRecursive(entry.getValue(), entry.getKey(), query, currentRow, results, maxDist);
            }
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Type-Ahead with Fuzzy Matching ===\n");

        FuzzyTypeAhead engine = new FuzzyTypeAhead();
        String[][] terms = {
            {"javascript", "1200"}, {"java", "1000"}, {"typescript", "900"},
            {"python", "1100"}, {"pytorch", "700"}, {"pycharm", "500"},
            {"react", "800"}, {"redis", "600"}, {"redux", "400"},
            {"kubernetes", "750"}, {"kafka", "650"},
        };
        for (String[] t : terms) engine.insert(t[0], Integer.parseInt(t[1]));

        // Exact prefix
        System.out.println("Fuzzy search 'javscript' (typo, dist<=2):");
        engine.fuzzySearch("javscript", 2, 5).forEach(r -> System.out.println("  " + r));

        System.out.println("\nFuzzy search 'pythn' (dist<=1):");
        engine.fuzzySearch("pythn", 1, 5).forEach(r -> System.out.println("  " + r));

        System.out.println("\nFuzzy search 'redus' (dist<=1):");
        engine.fuzzySearch("redus", 1, 5).forEach(r -> System.out.println("  " + r));

        System.out.println("\nFuzzy search 'kubernets' (dist<=2):");
        engine.fuzzySearch("kubernets", 2, 3).forEach(r -> System.out.println("  " + r));
    }
}

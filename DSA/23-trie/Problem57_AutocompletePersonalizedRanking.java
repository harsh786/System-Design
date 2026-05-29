import java.util.*;

/**
 * Problem 57: Autocomplete with Personalized Ranking
 * 
 * Production Relevance:
 * - Search engines, IDE code completion, e-commerce search bars
 * - Personalization: user's history, context, popularity all affect ranking
 * - Must respond in <50ms for good UX (keyboard-to-screen latency)
 * - Used in Google Search, VS Code IntelliSense, Slack search
 * 
 * Architect Considerations:
 * - Trie for prefix matching + scoring function for ranking
 * - Per-user frequency boosting (recently used terms ranked higher)
 * - Global popularity as baseline, personalized as boost
 * - Top-K retrieval without scanning all matches (heap-based pruning)
 */
public class Problem57_AutocompletePersonalizedRanking {

    static class TrieNode {
        Map<Character, TrieNode> children = new HashMap<>();
        String word; // non-null at word endings
        long globalPopularity;
    }

    static class UserProfile {
        Map<String, Integer> queryHistory = new LinkedHashMap<>(); // query -> frequency
        Map<String, Long> recentQueries = new LinkedHashMap<>(); // query -> timestamp

        void recordQuery(String query) {
            queryHistory.merge(query, 1, Integer::sum);
            recentQueries.put(query, System.currentTimeMillis());
        }

        double personalScore(String candidate) {
            double freqScore = queryHistory.getOrDefault(candidate, 0) * 10.0;
            Long lastUsed = recentQueries.get(candidate);
            double recencyScore = lastUsed != null ? 5.0 / (1 + (System.currentTimeMillis() - lastUsed) / 1000.0) : 0;
            return freqScore + recencyScore;
        }
    }

    static class PersonalizedAutocomplete {
        TrieNode root = new TrieNode();
        Map<String, UserProfile> users = new HashMap<>();

        void indexTerm(String term, long popularity) {
            TrieNode node = root;
            for (char c : term.toLowerCase().toCharArray()) {
                node.children.computeIfAbsent(c, k -> new TrieNode());
                node = node.children.get(c);
            }
            node.word = term;
            node.globalPopularity = popularity;
        }

        // Get personalized suggestions
        List<String> suggest(String prefix, String userId, int topK) {
            UserProfile profile = users.computeIfAbsent(userId, k -> new UserProfile());

            // Navigate to prefix node
            TrieNode node = root;
            for (char c : prefix.toLowerCase().toCharArray()) {
                node = node.children.get(c);
                if (node == null) return List.of();
            }

            // Collect all words under this prefix
            PriorityQueue<Map.Entry<String, Double>> heap = new PriorityQueue<>(
                    Comparator.comparingDouble(Map.Entry::getValue));
            collectWords(node, profile, heap, topK);

            // Extract top-K in descending order
            List<String> results = new ArrayList<>();
            while (!heap.isEmpty()) results.add(0, heap.poll().getKey());
            return results;
        }

        private void collectWords(TrieNode node, UserProfile profile,
                                   PriorityQueue<Map.Entry<String, Double>> heap, int k) {
            if (node.word != null) {
                double score = node.globalPopularity + profile.personalScore(node.word);
                if (heap.size() < k) {
                    heap.offer(Map.entry(node.word, score));
                } else if (score > heap.peek().getValue()) {
                    heap.poll();
                    heap.offer(Map.entry(node.word, score));
                }
            }
            for (TrieNode child : node.children.values()) {
                collectWords(child, profile, heap, k);
            }
        }

        void recordUserQuery(String userId, String query) {
            users.computeIfAbsent(userId, k -> new UserProfile()).recordQuery(query);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Autocomplete with Personalized Ranking ===\n");

        PersonalizedAutocomplete ac = new PersonalizedAutocomplete();

        // Index terms with global popularity
        ac.indexTerm("java", 1000);
        ac.indexTerm("javascript", 1200);
        ac.indexTerm("java spring", 800);
        ac.indexTerm("java streams", 600);
        ac.indexTerm("jackson json", 400);
        ac.indexTerm("jar file", 300);

        // User history: this user frequently searches "java streams"
        ac.recordUserQuery("user1", "java streams");
        ac.recordUserQuery("user1", "java streams");
        ac.recordUserQuery("user1", "java streams");

        System.out.println("Generic user (no history):");
        System.out.println("  'ja' -> " + ac.suggest("ja", "generic", 3));

        System.out.println("\nUser1 (frequently uses 'java streams'):");
        System.out.println("  'ja' -> " + ac.suggest("ja", "user1", 3));

        System.out.println("\nUser1 prefix 'java ':");
        System.out.println("  'java ' -> " + ac.suggest("java s", "user1", 3));
    }
}

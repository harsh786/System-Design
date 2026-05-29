import java.util.*;

/**
 * Problem 50: Design Twitter Hashtag Autocomplete
 * 
 * Design a hashtag autocomplete system that:
 * - Adds new hashtags with timestamps
 * - Returns top trending hashtags matching a prefix (recent + frequency weighted)
 * - Supports time-decay (recent usage counts more)
 * 
 * Time Complexity: O(m) per insert, O(m + k*log(k)) per suggest
 * Space Complexity: O(n*m) for all hashtags
 * 
 * Production Analogy: Twitter/Instagram hashtag suggestions, trending topics,
 * real-time search suggestions with freshness boost, Slack channel suggestions.
 */
public class Problem50_TwitterHashtagAutocomplete {

    static class TrieNode {
        TrieNode[] children = new TrieNode[37]; // a-z, 0-9, _
        Map<String, double[]> hashtags = new HashMap<>(); // tag -> [score, lastTimestamp]
    }

    static int charToIdx(char c) {
        if (c >= 'a' && c <= 'z') return c - 'a';
        if (c >= '0' && c <= '9') return 26 + (c - '0');
        return 36; // underscore
    }

    static class HashtagAutocomplete {
        TrieNode root = new TrieNode();
        double decayFactor = 0.9; // time decay

        void addHashtag(String tag, long timestamp) {
            String lower = tag.toLowerCase();
            TrieNode node = root;
            for (char c : lower.toCharArray()) {
                int idx = charToIdx(c);
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
                double[] data = node.hashtags.getOrDefault(tag, new double[]{0, 0});
                data[0] += 1.0; // increment frequency
                data[1] = timestamp; // update last seen
                node.hashtags.put(tag, data);
            }
        }

        List<String> suggest(String prefix, int k, long currentTime) {
            TrieNode node = root;
            for (char c : prefix.toLowerCase().toCharArray()) {
                int idx = charToIdx(c);
                if (node.children[idx] == null) return new ArrayList<>();
                node = node.children[idx];
            }

            // Score = frequency * decay^(timeDiff)
            PriorityQueue<Map.Entry<String, double[]>> pq = new PriorityQueue<>(
                (a, b) -> Double.compare(score(a.getValue(), currentTime), score(b.getValue(), currentTime)));

            for (Map.Entry<String, double[]> e : node.hashtags.entrySet()) {
                pq.offer(e);
                if (pq.size() > k) pq.poll();
            }

            LinkedList<String> result = new LinkedList<>();
            while (!pq.isEmpty()) result.addFirst(pq.poll().getKey());
            return result;
        }

        double score(double[] data, long currentTime) {
            double freq = data[0];
            double timeDiff = currentTime - data[1];
            return freq * Math.pow(decayFactor, timeDiff);
        }
    }

    public static void main(String[] args) {
        HashtagAutocomplete ac = new HashtagAutocomplete();
        ac.addHashtag("#coding", 1);
        ac.addHashtag("#coffee", 2);
        ac.addHashtag("#coding", 3);
        ac.addHashtag("#coding", 4);
        ac.addHashtag("#covid", 5);
        ac.addHashtag("#covid", 6);
        ac.addHashtag("#cool", 7);

        System.out.println(ac.suggest("#co", 3, 8));
        // Top 3 with prefix "co" - should favor recent and frequent: [#coding, #covid, #cool/#coffee]

        ac.addHashtag("#conference", 8);
        ac.addHashtag("#conference", 9);
        ac.addHashtag("#conference", 10);
        System.out.println(ac.suggest("#con", 2, 10));
        // [#conference]

        System.out.println(ac.suggest("#x", 3, 10));
        // []
    }
}

/**
 * Problem 49: Shortest Word Distance
 * 
 * Given a list of words and two words, find shortest distance between them.
 * 
 * Approach: Single pass, track last positions of word1 and word2, update min distance.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the minimum hop count between two services
 * in a sequential service registry listing.
 */
public class Problem49_ShortestWordDistance {
    public static int shortestDistance(String[] wordsDict, String word1, String word2) {
        int idx1 = -1, idx2 = -1, min = Integer.MAX_VALUE;
        for (int i = 0; i < wordsDict.length; i++) {
            if (wordsDict[i].equals(word1)) idx1 = i;
            else if (wordsDict[i].equals(word2)) idx2 = i;
            if (idx1 != -1 && idx2 != -1) min = Math.min(min, Math.abs(idx1 - idx2));
        }
        return min;
    }

    public static void main(String[] args) {
        String[] words = {"practice","makes","perfect","coding","makes"};
        System.out.println(shortestDistance(words, "coding", "practice")); // 3
        System.out.println(shortestDistance(words, "makes", "coding")); // 1
    }
}

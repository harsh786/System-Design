import java.util.*;

/**
 * Problem 22: Sentence Similarity II (LeetCode 737)
 * 
 * Words are similar transitively. Check if two sentences are similar.
 * 
 * Approach: Union all similar word pairs. For each word pair in sentences,
 * check if they have the same root.
 * 
 * Time: O(P * α(P) + n) where P = pairs, n = sentence length, Space: O(words)
 * 
 * Production Analogy: Synonym resolution in search engines - "car" and "automobile"
 * and "vehicle" should all match the same search intent.
 */
public class Problem22_SentenceSimilarityII {
    
    Map<String, String> parent = new HashMap<>();
    
    public boolean areSentencesSimilarTwo(String[] s1, String[] s2, List<List<String>> pairs) {
        if (s1.length != s2.length) return false;
        
        for (List<String> p : pairs) {
            union(p.get(0), p.get(1));
        }
        
        for (int i = 0; i < s1.length; i++) {
            if (!find(s1[i]).equals(find(s2[i]))) return false;
        }
        return true;
    }
    
    private String find(String x) {
        parent.putIfAbsent(x, x);
        if (!parent.get(x).equals(x)) parent.put(x, find(parent.get(x)));
        return parent.get(x);
    }
    
    private void union(String x, String y) {
        String px = find(x), py = find(y);
        if (!px.equals(py)) parent.put(px, py);
    }
    
    public static void main(String[] args) {
        Problem22_SentenceSimilarityII sol = new Problem22_SentenceSimilarityII();
        List<List<String>> pairs = Arrays.asList(
            Arrays.asList("great","good"), Arrays.asList("fine","good"), Arrays.asList("acting","drama"), Arrays.asList("skills","talent"));
        System.out.println(sol.areSentencesSimilarTwo(
            new String[]{"great","acting","skills"},
            new String[]{"fine","drama","talent"}, pairs)); // true
    }
}

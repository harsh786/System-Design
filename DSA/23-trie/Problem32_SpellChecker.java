import java.util.*;

/**
 * Problem 32: Trie for Spell Checker
 * 
 * Implement spell checker: exact match > capitalization match > vowel error match.
 * 
 * Time Complexity: O(n*m) for building, O(m) per query
 * Space Complexity: O(n*m)
 * 
 * Production Analogy: Gmail/Word spell checker, search engine "did you mean",
 * voice assistant input correction, code linter suggestions.
 */
public class Problem32_SpellChecker {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        String word = null;
    }

    public static String[] spellchecker(String[] wordlist, String[] queries) {
        Set<String> exact = new HashSet<>(Arrays.asList(wordlist));
        Map<String, String> capMap = new HashMap<>();
        Map<String, String> vowelMap = new HashMap<>();

        for (String w : wordlist) {
            String lower = w.toLowerCase();
            capMap.putIfAbsent(lower, w);
            vowelMap.putIfAbsent(devowel(lower), w);
        }

        String[] result = new String[queries.length];
        for (int i = 0; i < queries.length; i++) {
            String q = queries[i];
            if (exact.contains(q)) { result[i] = q; continue; }
            String lower = q.toLowerCase();
            if (capMap.containsKey(lower)) { result[i] = capMap.get(lower); continue; }
            String dv = devowel(lower);
            if (vowelMap.containsKey(dv)) { result[i] = vowelMap.get(dv); continue; }
            result[i] = "";
        }
        return result;
    }

    static String devowel(String s) {
        StringBuilder sb = new StringBuilder();
        for (char c : s.toCharArray()) {
            sb.append("aeiou".indexOf(c) >= 0 ? '*' : c);
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        String[] wordlist = {"KiTe","kite","hare","Hare"};
        String[] queries = {"kite","Kite","KiTe","Hare","HARE","Hear","hear","keti","keet","keto"};
        System.out.println(Arrays.toString(spellchecker(wordlist, queries)));
        // [kite, KiTe, KiTe, Hare, hare, , , KiTe, , KiTe]
    }
}

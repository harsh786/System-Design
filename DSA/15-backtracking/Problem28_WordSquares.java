import java.util.*;

/**
 * Problem 28: Word Squares (LeetCode 425)
 * 
 * Find all word squares formed from a list of words. A word square reads the same
 * horizontally and vertically (word[i][j] == word[j][i]).
 * 
 * Search Tree:
 * - Build row by row. After placing k rows, the prefix for row k+1 is determined
 *   by reading column k+1 from rows 0..k
 * 
 * Pruning Strategy:
 * - Use a Trie/HashMap of prefixes to quickly find candidate words for next row
 * - If no word matches required prefix, prune
 * 
 * Time Complexity: O(n * 26^L) where L = word length, n = number of words
 * Space Complexity: O(n*L) for prefix map
 * 
 * Production Analogy:
 * - Crossword puzzle generation / constraint grid filling in content systems.
 */
public class Problem28_WordSquares {

    public List<List<String>> wordSquares(String[] words) {
        int len = words[0].length();
        Map<String, List<String>> prefixMap = new HashMap<>();
        for (String w : words) {
            for (int i = 0; i <= w.length(); i++) {
                String prefix = w.substring(0, i);
                prefixMap.computeIfAbsent(prefix, k -> new ArrayList<>()).add(w);
            }
        }
        List<List<String>> result = new ArrayList<>();
        for (String w : words) {
            List<String> square = new ArrayList<>();
            square.add(w);
            backtrack(square, len, prefixMap, result);
        }
        return result;
    }

    private void backtrack(List<String> square, int len, Map<String, List<String>> prefixMap, List<List<String>> result) {
        if (square.size() == len) {
            result.add(new ArrayList<>(square));
            return;
        }
        int idx = square.size();
        StringBuilder prefix = new StringBuilder();
        for (String s : square) prefix.append(s.charAt(idx));
        List<String> candidates = prefixMap.getOrDefault(prefix.toString(), Collections.emptyList());
        for (String cand : candidates) {
            square.add(cand);
            backtrack(square, len, prefixMap, result);
            square.remove(square.size() - 1);
        }
    }

    public static void main(String[] args) {
        Problem28_WordSquares sol = new Problem28_WordSquares();

        System.out.println(sol.wordSquares(new String[]{"area","lead","wall","lady","ball"}));
        // [[wall, area, lead, lady], [ball, area, lead, lady]]

        System.out.println(sol.wordSquares(new String[]{"abat","baba","atan","atal"}));
    }
}

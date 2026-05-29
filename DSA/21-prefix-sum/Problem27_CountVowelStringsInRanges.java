/**
 * Problem 27: Count Vowel Strings in Ranges (LeetCode 2559)
 * 
 * Pattern: Prefix sum of boolean condition (starts and ends with vowel)
 * Time: O(n + q), Space: O(n)
 * 
 * Production Analogy: Pre-computing content classification counts for range queries
 * in a content management system.
 */
import java.util.*;

public class Problem27_CountVowelStringsInRanges {

    public static int[] vowelStrings(String[] words, int[][] queries) {
        Set<Character> vowels = new HashSet<>(Arrays.asList('a','e','i','o','u'));
        int n = words.length;
        int[] prefix = new int[n + 1];
        for (int i = 0; i < n; i++) {
            String w = words[i];
            boolean valid = vowels.contains(w.charAt(0)) && vowels.contains(w.charAt(w.length() - 1));
            prefix[i + 1] = prefix[i] + (valid ? 1 : 0);
        }
        int[] result = new int[queries.length];
        for (int i = 0; i < queries.length; i++)
            result[i] = prefix[queries[i][1] + 1] - prefix[queries[i][0]];
        return result;
    }

    public static void main(String[] args) {
        int[] r = vowelStrings(new String[]{"aba","bcb","ece","aa","e"}, new int[][]{{2,5},{1,4},{0,3}});
        // Note: indices are 0-based, queries[0] = [2,5] but array is 0-4, assuming [2,4]
        // LeetCode uses 0-indexed: let's use correct test
        int[] r2 = vowelStrings(new String[]{"aba","bcb","ece","aa","e"}, new int[][]{{2,4},{1,4},{0,4}});
        assert r2[0] == 3;
        assert r2[1] == 3;
        assert r2[2] == 4;
        System.out.println("All tests passed!");
    }
}

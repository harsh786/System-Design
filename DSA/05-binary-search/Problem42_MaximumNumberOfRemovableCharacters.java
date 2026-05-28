/**
 * Problem 42: Maximum Number of Removable Characters
 * 
 * Given s, p (subsequence of s), and removable indices. Find max k such that
 * after removing first k indices from removable, p is still subsequence of s.
 * 
 * Approach: Binary search on k. Check if p is subsequence after removal.
 * 
 * Time: O(n * log(removable.length)), Space: O(n)
 * 
 * Production Analogy: Finding maximum number of feature flags that can be
 * disabled while maintaining backward compatibility with client contracts.
 */
public class Problem42_MaximumNumberOfRemovableCharacters {
    public static int maximumRemovals(String s, String p, int[] removable) {
        int lo = 0, hi = removable.length;
        while (lo < hi) {
            int mid = lo + (hi - lo + 1) / 2;
            if (isSubsequence(s, p, removable, mid)) lo = mid;
            else hi = mid - 1;
        }
        return lo;
    }

    private static boolean isSubsequence(String s, String p, int[] removable, int k) {
        boolean[] removed = new boolean[s.length()];
        for (int i = 0; i < k; i++) removed[removable[i]] = true;
        int j = 0;
        for (int i = 0; i < s.length() && j < p.length(); i++) {
            if (!removed[i] && s.charAt(i) == p.charAt(j)) j++;
        }
        return j == p.length();
    }

    public static void main(String[] args) {
        System.out.println(maximumRemovals("abcacb", "ab", new int[]{3,1,0}));       // 2
        System.out.println(maximumRemovals("abcbddddd", "abcd", new int[]{3,2,1,4,5,6})); // 1
        System.out.println(maximumRemovals("abcab", "abc", new int[]{0,1,2,3,4}));   // 0
    }
}

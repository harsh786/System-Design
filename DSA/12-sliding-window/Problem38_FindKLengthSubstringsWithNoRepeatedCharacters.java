/**
 * Problem 38: Find K-Length Substrings With No Repeated Characters (LeetCode 1100)
 * 
 * Approach: Fixed window of size k with unique character check.
 * Window invariant: window size == k AND all chars unique.
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Like counting valid authentication tokens of fixed length
 * with no repeated characters.
 */
public class Problem38_FindKLengthSubstringsWithNoRepeatedCharacters {
    public static int numKLenSubstrNoRepeats(String s, int k) {
        if (k > 26 || k > s.length()) return 0;
        int[] freq = new int[26];
        int duplicates = 0, count = 0;
        for (int i = 0; i < s.length(); i++) {
            int c = s.charAt(i) - 'a';
            freq[c]++;
            if (freq[c] == 2) duplicates++;
            if (i >= k) {
                int lc = s.charAt(i - k) - 'a';
                freq[lc]--;
                if (freq[lc] == 1) duplicates--;
            }
            if (i >= k - 1 && duplicates == 0) count++;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(numKLenSubstrNoRepeats("havefunonleetcode", 5)); // 6
        System.out.println(numKLenSubstrNoRepeats("home", 5));               // 0
        System.out.println(numKLenSubstrNoRepeats("abcabc", 3));            // 4
    }
}

/**
 * Problem 34: Take K of Each Character From Left and Right (LeetCode 2516)
 * 
 * Approach: Equivalent to finding longest middle subarray to SKIP such that
 * remaining (left+right) still has >= k of each char.
 * Window invariant: chars removed from middle don't exceed (total[c] - k) for each c.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the longest break you can take while still
 * meeting minimum processing quotas from both ends of a queue.
 */
public class Problem34_TakeKOfEachCharacterFromLeftAndRight {
    public static int takeCharacters(String s, int k) {
        int[] total = new int[3];
        for (char c : s.toCharArray()) total[c - 'a']++;
        for (int i = 0; i < 3; i++) {
            if (total[i] < k) return -1;
        }
        // Max window where removed[c] <= total[c] - k
        int[] limit = {total[0] - k, total[1] - k, total[2] - k};
        int[] window = new int[3];
        int left = 0, maxWindow = 0;
        for (int right = 0; right < s.length(); right++) {
            window[s.charAt(right) - 'a']++;
            while (window[0] > limit[0] || window[1] > limit[1] || window[2] > limit[2]) {
                window[s.charAt(left) - 'a']--;
                left++;
            }
            maxWindow = Math.max(maxWindow, right - left + 1);
        }
        return s.length() - maxWindow;
    }

    public static void main(String[] args) {
        System.out.println(takeCharacters("aabaaaacaabc", 2)); // 8
        System.out.println(takeCharacters("a", 1));             // -1
        System.out.println(takeCharacters("abc", 1));           // 3
    }
}

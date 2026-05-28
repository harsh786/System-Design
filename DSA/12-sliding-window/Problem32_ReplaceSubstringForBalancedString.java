/**
 * Problem 32: Replace the Substring for Balanced String (LeetCode 1234)
 * 
 * Approach: Find minimum window to replace such that chars outside window
 * each have count <= n/4. Sliding window on the substring to replace.
 * Window invariant: all chars outside window have frequency <= n/4.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the minimum code segment to refactor
 * so that all module responsibilities are balanced.
 */
public class Problem32_ReplaceSubstringForBalancedString {
    public static int balancedString(String s) {
        int n = s.length(), target = n / 4;
        int[] count = new int[128];
        for (char c : s.toCharArray()) count[c]++;
        if (count['Q'] <= target && count['W'] <= target && count['E'] <= target && count['R'] <= target)
            return 0;
        int left = 0, minLen = n;
        for (int right = 0; right < n; right++) {
            count[s.charAt(right)]--;
            while (count['Q'] <= target && count['W'] <= target && count['E'] <= target && count['R'] <= target) {
                minLen = Math.min(minLen, right - left + 1);
                count[s.charAt(left)]++;
                left++;
            }
        }
        return minLen;
    }

    public static void main(String[] args) {
        System.out.println(balancedString("QWER"));   // 0
        System.out.println(balancedString("QQWE"));   // 1
        System.out.println(balancedString("QQQW"));   // 2
        System.out.println(balancedString("QQQQ"));   // 3
    }
}

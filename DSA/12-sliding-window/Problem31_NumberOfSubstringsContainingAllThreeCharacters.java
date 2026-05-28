/**
 * Problem 31: Number of Substrings Containing All Three Characters (LeetCode 1358)
 * 
 * Approach: Sliding window. When window contains all 3 (a,b,c), all extensions
 * to the right are valid. Count += (n - right).
 * Window invariant: track count of a, b, c. Shrink left when all present.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like counting log windows that contain all required
 * severity levels (INFO, WARN, ERROR) for compliance.
 */
public class Problem31_NumberOfSubstringsContainingAllThreeCharacters {
    public static int numberOfSubstrings(String s) {
        int[] count = new int[3];
        int left = 0, result = 0;
        for (int right = 0; right < s.length(); right++) {
            count[s.charAt(right) - 'a']++;
            while (count[0] > 0 && count[1] > 0 && count[2] > 0) {
                result += s.length() - right;
                count[s.charAt(left) - 'a']--;
                left++;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(numberOfSubstrings("abcabc")); // 10
        System.out.println(numberOfSubstrings("aaacb"));  // 3
        System.out.println(numberOfSubstrings("abc"));    // 1
    }
}

/**
 * Problem 15: Find the Difference
 * String t is s with one extra char. Find it.
 * 
 * Approach: XOR all chars of both strings. Result is the extra char.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Detecting injected header field in HTTP request.
 */
public class Problem15_FindTheDifference {
    public static char findTheDifference(String s, String t) {
        int xor = 0;
        for (char c : s.toCharArray()) xor ^= c;
        for (char c : t.toCharArray()) xor ^= c;
        return (char) xor;
    }

    public static void main(String[] args) {
        System.out.println(findTheDifference("abcd", "abcde")); // e
        System.out.println(findTheDifference("", "y")); // y
        System.out.println(findTheDifference("a", "aa")); // a
    }
}

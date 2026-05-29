/**
 * Problem 25: Maximum Product of Word Lengths
 * Find max product of lengths of two words that share no common letters.
 * 
 * Approach: Represent each word as 26-bit mask. Two words share no letters if masks AND = 0.
 * Time: O(n^2 + L) where L = total chars, Space: O(n)
 * 
 * Production Analogy: Finding non-overlapping resource allocations for max throughput.
 */
public class Problem25_MaxProductWordLengths {
    public static int maxProduct(String[] words) {
        int n = words.length;
        int[] masks = new int[n];
        for (int i = 0; i < n; i++) {
            for (char c : words[i].toCharArray()) {
                masks[i] |= 1 << (c - 'a');
            }
        }
        int max = 0;
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++)
                if ((masks[i] & masks[j]) == 0)
                    max = Math.max(max, words[i].length() * words[j].length());
        return max;
    }

    public static void main(String[] args) {
        System.out.println(maxProduct(new String[]{"abcw","baz","foo","bar","xtfn","abcdef"})); // 16
        System.out.println(maxProduct(new String[]{"a","ab","abc","d","cd","bcd","abcd"})); // 4
    }
}

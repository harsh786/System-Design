/**
 * Problem 30: Shifting Letters (LeetCode 848)
 * 
 * Pattern: Suffix sum of shifts (each position i gets sum of shifts[i..n-1])
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Cascading configuration changes where later services inherit
 * all upstream transformations.
 */
public class Problem30_ShiftingLetters {

    public static String shiftingLetters(String s, int[] shifts) {
        int n = shifts.length;
        long sum = 0;
        char[] arr = s.toCharArray();
        for (int i = n - 1; i >= 0; i--) {
            sum += shifts[i];
            arr[i] = (char) ('a' + (arr[i] - 'a' + sum) % 26);
        }
        return new String(arr);
    }

    public static void main(String[] args) {
        assert shiftingLetters("abc", new int[]{3, 5, 9}).equals("rpl");
        assert shiftingLetters("aaa", new int[]{1, 2, 3}).equals("gfd");
        System.out.println("All tests passed!");
    }
}

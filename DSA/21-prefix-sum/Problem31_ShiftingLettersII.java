/**
 * Problem 31: Shifting Letters II (LeetCode 2381)
 * 
 * Pattern: Difference array for range shifts, then prefix sum to get final shifts
 * 
 * Time: O(n + k), Space: O(n)
 * 
 * Production Analogy: Batch applying character encoding transformations to
 * overlapping text ranges in a collaborative editor.
 */
public class Problem31_ShiftingLettersII {

    public static String shiftingLetters(String s, int[][] shifts) {
        int n = s.length();
        int[] diff = new int[n + 1];
        for (int[] sh : shifts) {
            int val = sh[2] == 1 ? 1 : -1;
            diff[sh[0]] += val;
            diff[sh[1] + 1] -= val;
        }
        char[] arr = s.toCharArray();
        int shift = 0;
        for (int i = 0; i < n; i++) {
            shift += diff[i];
            int newChar = ((arr[i] - 'a' + shift) % 26 + 26) % 26;
            arr[i] = (char) ('a' + newChar);
        }
        return new String(arr);
    }

    public static void main(String[] args) {
        assert shiftingLetters("abc", new int[][]{{0,1,0},{1,2,1},{0,2,1}}).equals("ace");
        assert shiftingLetters("dztz", new int[][]{{0,0,0},{1,1,1}}).equals("catz");
        System.out.println("All tests passed!");
    }
}

/**
 * Problem 37: Minimum Recolors to Get K Consecutive Black Blocks (LeetCode 2379)
 * 
 * Approach: Fixed window of size k, count 'W' (white) blocks. Minimize whites.
 * Window invariant: window size == k, track white count.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the cheapest k-slot window to reserve
 * by converting minimum idle slots to active.
 */
public class Problem37_MinimumRecolorsToGetKConsecutiveBlackBlocks {
    public static int minimumRecolors(String blocks, int k) {
        int whites = 0;
        for (int i = 0; i < k; i++) {
            if (blocks.charAt(i) == 'W') whites++;
        }
        int min = whites;
        for (int i = k; i < blocks.length(); i++) {
            if (blocks.charAt(i) == 'W') whites++;
            if (blocks.charAt(i - k) == 'W') whites--;
            min = Math.min(min, whites);
        }
        return min;
    }

    public static void main(String[] args) {
        System.out.println(minimumRecolors("WBBWWBBWBW", 7)); // 3
        System.out.println(minimumRecolors("WBWBBBW", 2));     // 0
        System.out.println(minimumRecolors("BBBB", 2));        // 0
    }
}

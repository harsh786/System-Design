import java.util.*;

/**
 * Problem 46: Zuma Game (LeetCode 488)
 * 
 * Find minimum balls to insert into board to clear all balls (3+ consecutive same color removed).
 * 
 * Search Tree:
 * - For each ball in hand, try inserting at each position in board
 * - After insertion, remove consecutive groups of 3+, then recurse
 * 
 * Pruning Strategy:
 * - Only insert next to same-colored balls (or between two same-colored)
 * - Skip if inserting produces no progress
 * - Use memoization on board state + hand state
 * 
 * Time Complexity: O(exponential) but bounded by small inputs (board <= 16, hand <= 5)
 * Space Complexity: O(states) for memoization
 * 
 * Production Analogy:
 * - Minimum interventions to reach a clean/stable state in a cascading system.
 */
public class Problem46_ZumaGame {

    public int findMinStep(String board, String hand) {
        int[] handCount = new int[26];
        for (char c : hand.toCharArray()) handCount[c - 'A']++;
        int res = dfs(board, handCount, new HashMap<>());
        return res == Integer.MAX_VALUE ? -1 : res;
    }

    private int dfs(String board, int[] hand, Map<String, Integer> memo) {
        if (board.isEmpty()) return 0;
        String key = board + Arrays.toString(hand);
        if (memo.containsKey(key)) return memo.get(key);

        int min = Integer.MAX_VALUE;
        int i = 0;
        while (i < board.length()) {
            int j = i;
            while (j < board.length() && board.charAt(j) == board.charAt(i)) j++;
            int color = board.charAt(i) - 'A';
            int need = 3 - (j - i); // balls needed to complete group
            if (hand[color] >= need) {
                hand[color] -= need;
                String newBoard = remove(board.substring(0, i) + board.substring(j));
                int sub = dfs(newBoard, hand, memo);
                if (sub != Integer.MAX_VALUE) min = Math.min(min, sub + need);
                hand[color] += need;
            }
            i = j;
        }
        memo.put(key, min);
        return min;
    }

    private String remove(String board) {
        int i = 0;
        while (i < board.length()) {
            int j = i;
            while (j < board.length() && board.charAt(j) == board.charAt(i)) j++;
            if (j - i >= 3) {
                board = board.substring(0, i) + board.substring(j);
                i = 0; // restart after removal (cascade)
            } else {
                i = j;
            }
        }
        return board;
    }

    public static void main(String[] args) {
        Problem46_ZumaGame sol = new Problem46_ZumaGame();

        System.out.println(sol.findMinStep("WRRBBW", "RB"));    // -1
        System.out.println(sol.findMinStep("WWRRBBWW", "WRBRW")); // 2
        System.out.println(sol.findMinStep("G", "GGGGG"));       // 2
    }
}

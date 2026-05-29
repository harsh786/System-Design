/**
 * Problem 47: Maximum Students Taking Exam
 * Seats in m x n grid ('#' broken, '.' available). Students can't see neighbors' answers.
 * 
 * Approach: Row-by-row bitmask DP. For each row, enumerate valid seat configs (no adjacent,
 * no left/right diagonal from previous row). dp[row][mask] = max students.
 * Time: O(m * 2^n * 2^n), Space: O(2^n)
 * 
 * Production Analogy: Maximum concurrent non-interfering processes in a shared-resource grid.
 */
import java.util.*;

public class Problem47_MaxStudentsTakingExam {
    public static int maxStudents(char[][] seats) {
        int m = seats.length, n = seats[0].length;
        int[] avail = new int[m];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (seats[i][j] == '.') avail[i] |= (1 << j);
        
        int[] prev = new int[1 << n];
        Arrays.fill(prev, -1);
        prev[0] = 0;
        
        for (int row = 0; row < m; row++) {
            int[] curr = new int[1 << n];
            Arrays.fill(curr, -1);
            for (int mask = 0; mask < (1 << n); mask++) {
                // Valid: subset of available, no two adjacent
                if ((mask & avail[row]) != mask) continue;
                if ((mask & (mask << 1)) != 0) continue;
                int bits = Integer.bitCount(mask);
                for (int pmask = 0; pmask < (1 << n); pmask++) {
                    if (prev[pmask] == -1) continue;
                    // No left-upper or right-upper diagonal cheating
                    if ((mask & (pmask << 1)) != 0) continue;
                    if ((mask & (pmask >> 1)) != 0) continue;
                    curr[mask] = Math.max(curr[mask], prev[pmask] + bits);
                }
            }
            prev = curr;
        }
        int max = 0;
        for (int v : prev) max = Math.max(max, v);
        return max;
    }

    public static void main(String[] args) {
        char[][] seats = {{'#','.','#','#','.','#'},{'.','#','#','#','#','.'},{'#','.','#','#','.','#'}};
        System.out.println(maxStudents(seats)); // 4
    }
}

/**
 * Problem 36: Minimum Penalty for a Shop (LeetCode 2483)
 * 
 * Pattern: Prefix sum of 'Y' (customers) from right + prefix sum of 'N' from left
 * Penalty at hour j = count of 'N' before j + count of 'Y' from j onwards
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Finding optimal scaling schedule—penalty for being up with
 * no traffic vs. being down when traffic arrives.
 */
public class Problem36_MinPenaltyForShop {

    public static int bestClosingTime(String customers) {
        int n = customers.length();
        // suffix Y count (penalty for closing too early)
        int suffixY = 0;
        for (char c : customers.toCharArray()) if (c == 'Y') suffixY++;

        int minPenalty = suffixY, bestHour = 0;
        int prefixN = 0;
        for (int i = 0; i < n; i++) {
            if (customers.charAt(i) == 'Y') suffixY--;
            else prefixN++;
            int penalty = prefixN + suffixY;
            if (penalty < minPenalty) {
                minPenalty = penalty;
                bestHour = i + 1;
            }
        }
        return bestHour;
    }

    public static void main(String[] args) {
        assert bestClosingTime("YYNY") == 2;
        assert bestClosingTime("NNNNN") == 0;
        assert bestClosingTime("YYYY") == 4;
        System.out.println("All tests passed!");
    }
}

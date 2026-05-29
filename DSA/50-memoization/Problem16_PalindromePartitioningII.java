import java.util.*;

public class Problem16_PalindromePartitioningII {
    private Integer[] memo;

    public int minCut(String s) {
        memo = new Integer[s.length()];
        return helper(s, 0) - 1;
    }

    private int helper(String s, int start) {
        if (start == s.length()) return 0;
        if (memo[start] != null) return memo[start];
        int min = Integer.MAX_VALUE;
        for (int end = start; end < s.length(); end++) {
            if (isPalin(s, start, end)) min = Math.min(min, 1 + helper(s, end + 1));
        }
        memo[start] = min;
        return min;
    }

    private boolean isPalin(String s, int l, int r) {
        while (l < r) { if (s.charAt(l++) != s.charAt(r--)) return false; }
        return true;
    }

    public static void main(String[] args) {
        Problem16_PalindromePartitioningII sol = new Problem16_PalindromePartitioningII();
        System.out.println("minCut 'aab': " + sol.minCut("aab")); // 1
    }
}

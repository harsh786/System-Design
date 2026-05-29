import java.util.*;

public class Problem04_DecodeWays {
    private Map<Integer, Integer> memo = new HashMap<>();

    public int numDecodings(String s) {
        return helper(s, 0);
    }

    private int helper(String s, int i) {
        if (i == s.length()) return 1;
        if (s.charAt(i) == '0') return 0;
        if (memo.containsKey(i)) return memo.get(i);
        int ways = helper(s, i + 1);
        if (i + 1 < s.length() && Integer.parseInt(s.substring(i, i + 2)) <= 26) {
            ways += helper(s, i + 2);
        }
        memo.put(i, ways);
        return ways;
    }

    public static void main(String[] args) {
        Problem04_DecodeWays sol = new Problem04_DecodeWays();
        System.out.println("Decode '226': " + sol.numDecodings("226")); // 3
    }
}

import java.util.*;

public class Problem07_EditDistance {
    private Integer[][] memo;

    public int minDistance(String word1, String word2) {
        memo = new Integer[word1.length() + 1][word2.length() + 1];
        return helper(word1, word2, 0, 0);
    }

    private int helper(String w1, String w2, int i, int j) {
        if (i == w1.length()) return w2.length() - j;
        if (j == w2.length()) return w1.length() - i;
        if (memo[i][j] != null) return memo[i][j];
        if (w1.charAt(i) == w2.charAt(j)) {
            memo[i][j] = helper(w1, w2, i + 1, j + 1);
        } else {
            memo[i][j] = 1 + Math.min(helper(w1, w2, i + 1, j + 1),
                             Math.min(helper(w1, w2, i + 1, j), helper(w1, w2, i, j + 1)));
        }
        return memo[i][j];
    }

    public static void main(String[] args) {
        Problem07_EditDistance sol = new Problem07_EditDistance();
        System.out.println("Edit distance 'horse'->'ros': " + sol.minDistance("horse", "ros")); // 3
    }
}

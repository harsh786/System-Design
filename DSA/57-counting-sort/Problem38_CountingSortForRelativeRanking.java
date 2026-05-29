import java.util.*;

public class Problem38_CountingSortForRelativeRanking {
    public static String[] findRelativeRanks(int[] score) {
        int n = score.length;
        int max = 0; for (int s : score) max = Math.max(max, s);
        int[] scoreToIdx = new int[max + 1];
        Arrays.fill(scoreToIdx, -1);
        for (int i = 0; i < n; i++) scoreToIdx[score[i]] = i;
        String[] result = new String[n];
        String[] medals = {"Gold Medal", "Silver Medal", "Bronze Medal"};
        int rank = 0;
        for (int i = max; i >= 0; i--) {
            if (scoreToIdx[i] == -1) continue;
            result[scoreToIdx[i]] = rank < 3 ? medals[rank] : String.valueOf(rank + 1);
            rank++;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(findRelativeRanks(new int[]{5,4,3,2,1})));
    }
}

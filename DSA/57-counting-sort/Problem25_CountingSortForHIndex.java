import java.util.*;

public class Problem25_CountingSortForHIndex {
    public static int hIndex(int[] citations) {
        int n = citations.length;
        int[] count = new int[n + 1];
        for (int c : citations) count[Math.min(c, n)]++;
        int papers = 0;
        for (int i = n; i >= 0; i--) {
            papers += count[i];
            if (papers >= i) return i;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(hIndex(new int[]{3, 0, 6, 1, 5})); // 3
    }
}

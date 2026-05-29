/**
 * Problem: H-Index (LeetCode 274)
 * Approach: Counting sort with bucket for citation counts
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Threshold-based classification in ranking systems
 */
public class Problem19_HIndex {
    public int hIndex(int[] citations) {
        int n = citations.length;
        int[] buckets = new int[n+1];
        for (int c : citations) buckets[Math.min(c, n)]++;
        int count = 0;
        for (int i = n; i >= 0; i--) {
            count += buckets[i];
            if (count >= i) return i;
        }
        return 0;
    }
    public static void main(String[] args) {
        System.out.println(new Problem19_HIndex().hIndex(new int[]{3,0,6,1,5})); // 3
    }
}

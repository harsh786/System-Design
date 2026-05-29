import java.util.*;

/**
 * Problem 14: H-Index
 * 
 * Given citations array, compute the researcher's h-index.
 * h-index: max h such that h papers have at least h citations.
 * 
 * Approach: Counting sort (bucket by citations capped at n).
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Service reliability scoring - finding the threshold where 
 * at least h services meet h-nines of uptime.
 */
public class Problem14_HIndex {
    
    public int hIndex(int[] citations) {
        int n = citations.length;
        int[] count = new int[n + 1]; // count[i] = papers with exactly i citations (capped at n)
        
        for (int c : citations) {
            count[Math.min(c, n)]++;
        }
        
        int papers = 0;
        for (int h = n; h >= 0; h--) {
            papers += count[h];
            if (papers >= h) return h;
        }
        return 0;
    }
    
    public static void main(String[] args) {
        Problem14_HIndex sol = new Problem14_HIndex();
        
        System.out.println("Test 1: " + sol.hIndex(new int[]{3,0,6,1,5})); // 3
        System.out.println("Test 2: " + sol.hIndex(new int[]{1,3,1})); // 1
        System.out.println("Test 3: " + sol.hIndex(new int[]{0})); // 0
        System.out.println("Test 4: " + sol.hIndex(new int[]{100})); // 1
        System.out.println("Test 5: " + sol.hIndex(new int[]{0,0,0})); // 0
    }
}

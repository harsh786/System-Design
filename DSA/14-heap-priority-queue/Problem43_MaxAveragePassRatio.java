import java.util.*;

/**
 * Problem 43: Maximum Average Pass Ratio (LeetCode 1792)
 * 
 * Approach: Max-heap by marginal gain of adding one passing student to each class.
 * Greedily assign extra students to class with highest improvement.
 * 
 * Time Complexity: O((N + extraStudents) * log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Resource allocation to maximize average SLA - adding capacity
 * where it improves overall metrics the most.
 */
public class Problem43_MaxAveragePassRatio {
    
    public double maxAverageRatio(int[][] classes, int extraStudents) {
        // max-heap by gain: (pass+1)/(total+1) - pass/total
        PriorityQueue<double[]> pq = new PriorityQueue<>((a, b) -> Double.compare(b[2], a[2]));
        
        for (int[] c : classes) {
            double gain = (c[0] + 1.0) / (c[1] + 1.0) - (double) c[0] / c[1];
            pq.offer(new double[]{c[0], c[1], gain});
        }
        
        while (extraStudents-- > 0) {
            double[] top = pq.poll();
            double pass = top[0] + 1, total = top[1] + 1;
            double gain = (pass + 1) / (total + 1) - pass / total;
            pq.offer(new double[]{pass, total, gain});
        }
        
        double sum = 0;
        for (double[] c : pq) sum += c[0] / c[1];
        return sum / classes.length;
    }
    
    public static void main(String[] args) {
        Problem43_MaxAveragePassRatio sol = new Problem43_MaxAveragePassRatio();
        System.out.printf("%.5f%n", sol.maxAverageRatio(new int[][]{{1,2},{3,5},{2,2}}, 2)); // 0.78333
        System.out.printf("%.5f%n", sol.maxAverageRatio(new int[][]{{2,4},{3,9},{4,5},{2,10}}, 4)); // 0.53485
    }
}

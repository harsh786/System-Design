import java.util.*;

/**
 * Problem 3: Find Median from Data Stream (LeetCode 295)
 * 
 * Approach: Two heaps - max-heap for lower half, min-heap for upper half.
 * Balance so max-heap has at most 1 more element.
 * 
 * Time Complexity: O(log N) per addNum, O(1) per findMedian
 * Space Complexity: O(N)
 * 
 * Production Analogy: Real-time percentile monitoring for response times.
 * Streaming median for SLA dashboards without storing all data points.
 */
public class Problem03_FindMedianFromDataStream {
    
    private PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder()); // lower half
    private PriorityQueue<Integer> minHeap = new PriorityQueue<>(); // upper half
    
    public void addNum(int num) {
        maxHeap.offer(num);
        minHeap.offer(maxHeap.poll());
        if (minHeap.size() > maxHeap.size()) {
            maxHeap.offer(minHeap.poll());
        }
    }
    
    public double findMedian() {
        if (maxHeap.size() > minHeap.size()) return maxHeap.peek();
        return (maxHeap.peek() + minHeap.peek()) / 2.0;
    }
    
    public static void main(String[] args) {
        Problem03_FindMedianFromDataStream sol = new Problem03_FindMedianFromDataStream();
        sol.addNum(1);
        System.out.println(sol.findMedian()); // 1.0
        sol.addNum(2);
        System.out.println(sol.findMedian()); // 1.5
        sol.addNum(3);
        System.out.println(sol.findMedian()); // 2.0
        sol.addNum(4);
        System.out.println(sol.findMedian()); // 2.5
        sol.addNum(5);
        System.out.println(sol.findMedian()); // 3.0
    }
}

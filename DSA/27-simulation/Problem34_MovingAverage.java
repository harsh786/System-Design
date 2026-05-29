/**
 * Problem: Moving Average from Data Stream (LeetCode 346)
 * Approach: Circular buffer with running sum
 * Complexity: O(1) per call
 * Production Analogy: Sliding window metrics in time-series monitoring
 */
import java.util.*;
public class Problem34_MovingAverage {
    Queue<Integer> q = new LinkedList<>();
    int maxSize; double sum = 0;
    public Problem34_MovingAverage(int size) { maxSize = size; }
    public double next(int val) {
        q.offer(val); sum += val;
        if (q.size() > maxSize) sum -= q.poll();
        return sum / q.size();
    }
    public static void main(String[] args) {
        Problem34_MovingAverage ma = new Problem34_MovingAverage(3);
        System.out.println(ma.next(1)); // 1.0
        System.out.println(ma.next(10)); // 5.5
        System.out.println(ma.next(3)); // 4.666
        System.out.println(ma.next(5)); // 6.0
    }
}

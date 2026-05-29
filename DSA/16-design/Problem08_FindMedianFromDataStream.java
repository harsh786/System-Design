import java.util.*;

/**
 * Problem 8: Find Median from Data Stream
 * 
 * API Contract:
 * - addNum(num): Add integer from stream
 * - findMedian(): Return current median
 * 
 * Complexity: addNum O(log n), findMedian O(1)
 * Data Structure: Two heaps - max-heap for lower half, min-heap for upper half
 * 
 * Production Analogy: Real-time percentile calculation for latency monitoring (P50),
 * streaming analytics, stock price median tracking
 */
public class Problem08_FindMedianFromDataStream {

    static class MedianFinder {
        private PriorityQueue<Integer> lo; // max-heap (lower half)
        private PriorityQueue<Integer> hi; // min-heap (upper half)

        public MedianFinder() {
            lo = new PriorityQueue<>(Collections.reverseOrder());
            hi = new PriorityQueue<>();
        }

        public void addNum(int num) {
            lo.offer(num);
            hi.offer(lo.poll());
            if (hi.size() > lo.size()) lo.offer(hi.poll());
        }

        public double findMedian() {
            if (lo.size() > hi.size()) return lo.peek();
            return (lo.peek() + hi.peek()) / 2.0;
        }
    }

    public static void main(String[] args) {
        MedianFinder mf = new MedianFinder();
        mf.addNum(1);
        assert mf.findMedian() == 1.0;
        mf.addNum(2);
        assert mf.findMedian() == 1.5;
        mf.addNum(3);
        assert mf.findMedian() == 2.0;

        // Edge: negative numbers
        MedianFinder mf2 = new MedianFinder();
        mf2.addNum(-1);
        mf2.addNum(-2);
        assert mf2.findMedian() == -1.5;

        // Edge: duplicates
        MedianFinder mf3 = new MedianFinder();
        mf3.addNum(5); mf3.addNum(5); mf3.addNum(5);
        assert mf3.findMedian() == 5.0;

        System.out.println("All tests passed!");
    }
}

import java.util.*;

/**
 * Problem 28: Moving Average from Data Stream
 * 
 * API Contract:
 * - next(val): Add value, return average of last `size` values
 * 
 * Complexity: O(1) per call
 * Data Structure: Circular buffer (queue) + running sum
 * 
 * Production Analogy: Stock price moving averages (SMA), network throughput smoothing,
 * sensor data smoothing in IoT, rolling metrics in monitoring
 */
public class Problem28_MovingAverageFromDataStream {

    static class MovingAverage {
        private Queue<Integer> queue;
        private int maxSize;
        private double sum;

        public MovingAverage(int size) {
            queue = new LinkedList<>();
            maxSize = size;
            sum = 0;
        }

        public double next(int val) {
            if (queue.size() == maxSize) sum -= queue.poll();
            queue.offer(val);
            sum += val;
            return sum / queue.size();
        }
    }

    public static void main(String[] args) {
        MovingAverage ma = new MovingAverage(3);
        assert ma.next(1) == 1.0;
        assert ma.next(10) == 5.5;
        assert Math.abs(ma.next(3) - 4.66667) < 0.001;
        assert Math.abs(ma.next(5) - 6.0) < 0.001; // (10+3+5)/3

        System.out.println("All tests passed!");
    }
}

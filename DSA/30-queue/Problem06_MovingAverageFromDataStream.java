import java.util.*;

public class Problem06_MovingAverageFromDataStream {
    static class MovingAverage {
        Queue<Integer> q = new LinkedList<>();
        int size; double sum = 0;
        MovingAverage(int size) { this.size = size; }
        double next(int val) {
            q.offer(val); sum += val;
            if (q.size() > size) sum -= q.poll();
            return sum / q.size();
        }
    }
    public static void main(String[] args) {
        MovingAverage ma = new MovingAverage(3);
        System.out.println(ma.next(1)); // 1.0
        System.out.println(ma.next(10)); // 5.5
        System.out.println(ma.next(3)); // 4.666
        System.out.println(ma.next(5)); // 6.0
    }
}

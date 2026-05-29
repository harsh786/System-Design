import java.util.*;

public class Problem03_MovingAverageFromDataStream {
    // 346. Moving Average from Data Stream.
    
    Queue<Integer> queue = new LinkedList<>();
    int size;
    double sum = 0;
    
    public Problem03_MovingAverageFromDataStream() { this.size = 3; }
    
    public void init(int size) { this.size = size; queue.clear(); sum = 0; }
    
    public double next(int val) {
        queue.offer(val);
        sum += val;
        if (queue.size() > size) sum -= queue.poll();
        return sum / queue.size();
    }
    
    public static void main(String[] args) {
        Problem03_MovingAverageFromDataStream sol = new Problem03_MovingAverageFromDataStream();
        sol.init(3);
        System.out.println(sol.next(1));  // 1.0
        System.out.println(sol.next(10)); // 5.5
        System.out.println(sol.next(3));  // 4.666...
        System.out.println(sol.next(5));  // 6.0
    }
}

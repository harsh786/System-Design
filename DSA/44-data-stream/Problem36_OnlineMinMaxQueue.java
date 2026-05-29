import java.util.*;

public class Problem36_OnlineMinMaxQueue {
    // Min-Max Queue: Queue that supports O(1) getMin and getMax using monotonic deques.
    
    Deque<Integer> queue = new ArrayDeque<>();
    Deque<Integer> minDq = new ArrayDeque<>();
    Deque<Integer> maxDq = new ArrayDeque<>();
    
    public void push(int val) {
        queue.addLast(val);
        while (!minDq.isEmpty() && minDq.peekLast() > val) minDq.pollLast();
        minDq.addLast(val);
        while (!maxDq.isEmpty() && maxDq.peekLast() < val) maxDq.pollLast();
        maxDq.addLast(val);
    }
    
    public int pop() {
        int val = queue.pollFirst();
        if (minDq.peekFirst() == val) minDq.pollFirst();
        if (maxDq.peekFirst() == val) maxDq.pollFirst();
        return val;
    }
    
    public int getMin() { return minDq.peekFirst(); }
    public int getMax() { return maxDq.peekFirst(); }
    
    public static void main(String[] args) {
        Problem36_OnlineMinMaxQueue sol = new Problem36_OnlineMinMaxQueue();
        sol.push(3); sol.push(1); sol.push(5); sol.push(2);
        System.out.println("Min: " + sol.getMin() + ", Max: " + sol.getMax()); // 1, 5
        sol.pop(); // remove 3
        System.out.println("Min: " + sol.getMin() + ", Max: " + sol.getMax()); // 1, 5
        sol.pop(); // remove 1
        System.out.println("Min: " + sol.getMin() + ", Max: " + sol.getMax()); // 2, 5
    }
}

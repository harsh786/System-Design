/**
 * Problem: Thread-safe Stack
 * Stack with synchronized push/pop.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: Undo stack in collaborative editor.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem18_ThreadSafeStack {
    private final LinkedList<Integer> stack = new LinkedList<>();

    public synchronized void push(int val) { stack.push(val); notifyAll(); }

    public synchronized int pop() throws InterruptedException {
        while (stack.isEmpty()) wait();
        return stack.pop();
    }

    public synchronized boolean isEmpty() { return stack.isEmpty(); }

    public static void main(String[] args) throws InterruptedException {
        Problem18_ThreadSafeStack s = new Problem18_ThreadSafeStack();
        new Thread(() -> { for (int i = 0; i < 5; i++) s.push(i); }).start();
        Thread.sleep(100);
        new Thread(() -> { try { for (int i = 0; i < 5; i++) System.out.println("Popped: " + s.pop()); } catch (InterruptedException e) {} }).start();
        Thread.sleep(500);
    }
}

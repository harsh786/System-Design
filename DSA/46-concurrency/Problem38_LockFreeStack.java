import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem38_LockFreeStack {
    /**
     * Problem: Lock-Free Stack (concept using CAS)
     * Stack using AtomicReference for lock-free push/pop.
     * Time: O(1) amortized | Space: O(n)
     * Production Analogy: Memory allocator free-list in high-performance systems.
     */
    private static class Node<T> { final T value; Node<T> next; Node(T v, Node<T> n) { value = v; next = n; } }
    private final AtomicReference<Node<Integer>> top = new AtomicReference<>(null);

    public void push(int val) {
        Node<Integer> newNode, oldTop;
        do { oldTop = top.get(); newNode = new Node<>(val, oldTop); } while (!top.compareAndSet(oldTop, newNode));
    }

    public Integer pop() {
        Node<Integer> oldTop, newTop;
        do { oldTop = top.get(); if (oldTop == null) return null; newTop = oldTop.next; } while (!top.compareAndSet(oldTop, newTop));
        return oldTop.value;
    }

    public static void main(String[] args) throws InterruptedException {
        Problem38_LockFreeStack stack = new Problem38_LockFreeStack();
        Thread t1 = new Thread(() -> { for (int i = 0; i < 5; i++) stack.push(i); });
        t1.start(); t1.join();
        Integer val;
        while ((val = stack.pop()) != null) System.out.println("Popped: " + val);
    }
}

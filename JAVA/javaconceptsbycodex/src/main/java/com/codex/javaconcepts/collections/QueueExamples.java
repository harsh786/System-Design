package com.codex.javaconcepts.collections;

import java.util.ArrayDeque;
import java.util.Comparator;
import java.util.Deque;
import java.util.PriorityQueue;
import java.util.Queue;

public class QueueExamples {
    public static void main(String[] args) {
        queueWithArrayDeque();
        stackWithArrayDeque();
        priorityQueueNaturalOrder();
        priorityQueueWithObjects();
    }

    private static void queueWithArrayDeque() {
        Queue<String> jobs = new ArrayDeque<>();
        jobs.offer("send-email");
        jobs.offer("generate-invoice");
        jobs.offer("sync-ledger");

        System.out.println("Queue peek: " + jobs.peek());
        while (!jobs.isEmpty()) {
            System.out.println("Queue poll: " + jobs.poll());
        }
        System.out.println("poll on empty queue: " + jobs.poll());
    }

    private static void stackWithArrayDeque() {
        Deque<String> undoStack = new ArrayDeque<>();
        undoStack.push("type A");
        undoStack.push("type B");
        undoStack.push("delete B");

        System.out.println("Stack pop: " + undoStack.pop());
        System.out.println("Stack after pop: " + undoStack);
    }

    private static void priorityQueueNaturalOrder() {
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        minHeap.offer(5);
        minHeap.offer(1);
        minHeap.offer(3);

        System.out.println("PriorityQueue internal view is not sorted: " + minHeap);
        while (!minHeap.isEmpty()) {
            System.out.println("PriorityQueue poll: " + minHeap.poll());
        }
    }

    private static void priorityQueueWithObjects() {
        PriorityQueue<Task> tasks = new PriorityQueue<>(
            Comparator.comparingInt(Task::priority)
                .thenComparing(Task::createdAt)
        );

        tasks.offer(new Task("low", 5, 1));
        tasks.offer(new Task("urgent", 1, 3));
        tasks.offer(new Task("urgent-earlier", 1, 2));

        while (!tasks.isEmpty()) {
            System.out.println("Next task: " + tasks.poll());
        }
    }

    private record Task(String name, int priority, long createdAt) {
    }
}


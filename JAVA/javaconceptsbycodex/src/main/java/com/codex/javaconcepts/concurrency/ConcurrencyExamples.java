package com.codex.javaconcepts.concurrency;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class ConcurrencyExamples {
    public static void main(String[] args) throws Exception {
        threadRunnableJoin();
        synchronizedCounter();
        atomicCounter();
        explicitLock();
        futureAndCallable();
        completableFuture();
        concurrentHashMap();
        countDownLatch();
        semaphore();
        volatileStopFlag();
    }

    private static void threadRunnableJoin() throws InterruptedException {
        Thread thread = new Thread(() ->
            System.out.println("Runnable running on " + Thread.currentThread().getName())
        );
        thread.start();
        thread.join();
    }

    private static void synchronizedCounter() throws InterruptedException {
        SafeCounter counter = new SafeCounter();
        ExecutorService executor = Executors.newFixedThreadPool(4);
        for (int i = 0; i < 1_000; i++) {
            executor.submit(counter::increment);
        }
        shutdownAndAwait(executor);
        System.out.println("synchronized counter: " + counter.get());
    }

    private static void atomicCounter() throws InterruptedException {
        AtomicInteger counter = new AtomicInteger();
        ExecutorService executor = Executors.newFixedThreadPool(4);
        for (int i = 0; i < 1_000; i++) {
            executor.submit(counter::incrementAndGet);
        }
        shutdownAndAwait(executor);
        System.out.println("AtomicInteger counter: " + counter.get());
    }

    private static void explicitLock() {
        BankAccount account = new BankAccount(100);
        account.deposit(50);
        account.withdraw(30);
        System.out.println("ReentrantLock account balance: " + account.balance());
    }

    private static void futureAndCallable() throws Exception {
        ExecutorService executor = Executors.newSingleThreadExecutor();
        Callable<Integer> task = () -> 40 + 2;
        Future<Integer> future = executor.submit(task);
        System.out.println("Future result: " + future.get());
        shutdownAndAwait(executor);
    }

    private static void completableFuture() {
        CompletableFuture<String> future = CompletableFuture
            .supplyAsync(() -> "user")
            .thenApply(String::toUpperCase)
            .thenApply(value -> "Loaded " + value)
            .exceptionally(ex -> "fallback");

        System.out.println("CompletableFuture result: " + future.join());
    }

    private static void concurrentHashMap() throws InterruptedException {
        ConcurrentHashMap<String, Integer> counts = new ConcurrentHashMap<>();
        ExecutorService executor = Executors.newFixedThreadPool(4);
        for (int i = 0; i < 500; i++) {
            executor.submit(() -> counts.merge("success", 1, Integer::sum));
        }
        shutdownAndAwait(executor);
        System.out.println("ConcurrentHashMap counts: " + counts);
    }

    private static void countDownLatch() throws InterruptedException {
        int workers = 3;
        CountDownLatch latch = new CountDownLatch(workers);
        ExecutorService executor = Executors.newFixedThreadPool(workers);

        for (int i = 1; i <= workers; i++) {
            int workerId = i;
            executor.submit(() -> {
                try {
                    System.out.println("worker finished: " + workerId);
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await();
        shutdownAndAwait(executor);
        System.out.println("All workers finished");
    }

    private static void semaphore() throws InterruptedException {
        Semaphore semaphore = new Semaphore(2);
        List<String> acquired = new ArrayList<>();

        semaphore.acquire();
        try {
            acquired.add("resource-1");
        } finally {
            semaphore.release();
        }

        System.out.println("Semaphore acquired resources: " + acquired);
    }

    private static void volatileStopFlag() throws InterruptedException {
        StopFlag flag = new StopFlag();
        Thread worker = new Thread(() -> {
            while (!flag.stopped()) {
                Thread.yield();
            }
            System.out.println("Worker observed volatile stop flag");
        });

        worker.start();
        flag.stop();
        worker.join();
    }

    private static void shutdownAndAwait(ExecutorService executor) throws InterruptedException {
        executor.shutdown();
        if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
            executor.shutdownNow();
        }
    }

    private static class SafeCounter {
        private int value;

        synchronized void increment() {
            value++;
        }

        synchronized int get() {
            return value;
        }
    }

    private static class BankAccount {
        private final Lock lock = new ReentrantLock();
        private int balance;

        private BankAccount(int balance) {
            this.balance = balance;
        }

        void deposit(int amount) {
            lock.lock();
            try {
                balance += amount;
            } finally {
                lock.unlock();
            }
        }

        void withdraw(int amount) {
            lock.lock();
            try {
                if (amount > balance) {
                    throw new IllegalArgumentException("insufficient balance");
                }
                balance -= amount;
            } finally {
                lock.unlock();
            }
        }

        int balance() {
            lock.lock();
            try {
                return balance;
            } finally {
                lock.unlock();
            }
        }
    }

    private static class StopFlag {
        private volatile boolean stopped;

        void stop() {
            stopped = true;
        }

        boolean stopped() {
            return stopped;
        }
    }
}


/**
 * Problem: Fizz Buzz Multithreaded
 * Four threads: fizz, buzz, fizzbuzz, number - coordinate to print 1..n correctly.
 * 
 * Approach: Use a shared counter with synchronized/wait-notify or Semaphores.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Event routing - different handlers for different event types,
 * only one handler processes each event.
 */
import java.util.concurrent.*;
import java.util.function.*;

public class Problem05_FizzBuzzMultithreaded {
    private int n;
    private volatile int current = 1;

    public Problem05_FizzBuzzMultithreaded(int n) { this.n = n; }

    public synchronized void fizz() throws InterruptedException {
        while (current <= n) {
            if (current % 3 == 0 && current % 5 != 0) {
                System.out.print("fizz ");
                current++;
                notifyAll();
            } else { wait(); }
        }
    }

    public synchronized void buzz() throws InterruptedException {
        while (current <= n) {
            if (current % 5 == 0 && current % 3 != 0) {
                System.out.print("buzz ");
                current++;
                notifyAll();
            } else { wait(); }
        }
    }

    public synchronized void fizzbuzz() throws InterruptedException {
        while (current <= n) {
            if (current % 15 == 0) {
                System.out.print("fizzbuzz ");
                current++;
                notifyAll();
            } else { wait(); }
        }
    }

    public synchronized void number() throws InterruptedException {
        while (current <= n) {
            if (current % 3 != 0 && current % 5 != 0) {
                System.out.print(current + " ");
                current++;
                notifyAll();
            } else { wait(); }
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem05_FizzBuzzMultithreaded obj = new Problem05_FizzBuzzMultithreaded(15);
        Thread t1 = new Thread(() -> { try { obj.fizz(); } catch (InterruptedException e) {} });
        Thread t2 = new Thread(() -> { try { obj.buzz(); } catch (InterruptedException e) {} });
        Thread t3 = new Thread(() -> { try { obj.fizzbuzz(); } catch (InterruptedException e) {} });
        Thread t4 = new Thread(() -> { try { obj.number(); } catch (InterruptedException e) {} });
        t1.start(); t2.start(); t3.start(); t4.start();
        t1.join(); t2.join(); t3.join(); t4.join();
        System.out.println();
    }
}
